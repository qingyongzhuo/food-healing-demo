"""拍照识菜业务服务（阶段 6 新增）。

职责：
- 接收前端图片，调用上传工具存储 → 生成可访问 URL
- 组装任务数据，发送至 RabbitMQ 异步识别队列
- MQ 未就绪时 fallback 到 asyncio.create_task（直接调 VL）
- 识别结果写入 Mongo camera_recognize_log 集合
- 任务状态写入 Redis（CAMERA_TASK_KEY_PREFIX，TTL 10 分钟）
- 根据用户 ID 查询历史识别记录（Mongo）

任务状态机：
    pending → processing → done
                       └→ failed
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.constants import (
    CAMERA_RECOGNIZE_LOG_COLLECTION,
    CAMERA_TASK_KEY_PREFIX,
    CAMERA_TASK_TTL,
)
from app.database import mongo_db, redis_client
from app.exceptions import BizError
from app.models.schemas import ERR_DB_QUERY, ERR_NOT_FOUND
from app.schemas.camera import CATEGORY_COLOR_MAP, RecognizedDish
from app.utils.file_upload import save_camera_image
from app.utils.logger import logger
from fastapi import UploadFile


def _task_key(task_id: str) -> str:
    return f"{CAMERA_TASK_KEY_PREFIX}{task_id}"


def _generate_task_id() -> str:
    return f"cam_{uuid.uuid4().hex[:12]}"


def _enrich_dish(dish: dict) -> dict:
    """给 dish dict 补 category_color 字段。"""
    category = dish.get("category", "其他")
    dish["category_color"] = CATEGORY_COLOR_MAP.get(category, CATEGORY_COLOR_MAP["其他"])
    return dish


async def _update_task_state(
    task_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    error: str | None = None,
    dishes: list[dict] | None = None,
    image_url: str | None = None,
) -> None:
    """部分更新 Redis 任务状态。"""
    raw = await redis_client.get(_task_key(task_id))
    if raw is None:
        logger.warning("camera_task_state_missing", task_id=task_id)
        return
    data = json.loads(raw)
    if status is not None:
        data["status"] = status
    if progress is not None:
        data["progress"] = progress
    if error is not None:
        data["error"] = error
    if dishes is not None:
        data["dishes"] = dishes
    if image_url is not None:
        data["image_url"] = image_url
    await redis_client.set(
        _task_key(task_id), json.dumps(data, ensure_ascii=False), ex=CAMERA_TASK_TTL
    )


async def submit_camera_task(
    file: UploadFile,
    user_id: int | str | None,
) -> dict[str, Any]:
    """提交拍照识菜任务：保存图片 → 写 Redis 任务 → 发 MQ / fallback。

    Returns:
        { task_id, image_url, status: "pending" }
    """
    # 1. 保存图片（压缩 + 本地存储）
    image_info = await save_camera_image(file, user_id)
    image_url = image_info["url"]

    # 2. 生成任务 ID + 写 Redis 初始状态
    task_id = _generate_task_id()
    initial_state = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "user_id": user_id,
        "image_url": image_url,
        "dishes": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis_client.set(
        _task_key(task_id),
        json.dumps(initial_state, ensure_ascii=False),
        ex=CAMERA_TASK_TTL,
    )
    logger.info("camera_task_created", task_id=task_id, user_id=user_id, image_url=image_url)

    # 3. 发送 MQ 任务；失败 fallback 到 asyncio.create_task
    from app.tasks.ai_task import publish_recognize_task

    task_data = {"task_id": task_id, "user_id": user_id, "image_url": image_url}
    published = await publish_recognize_task(task_data)
    if published:
        logger.info("camera_task_published_to_mq", task_id=task_id)
    else:
        logger.info("camera_task_fallback_to_create_task", task_id=task_id)
        asyncio.create_task(_process_recognize_fallback(task_id, user_id, image_url))

    return {"task_id": task_id, "image_url": image_url, "status": "pending"}


async def _process_recognize_fallback(
    task_id: str,
    user_id: int | str | None,
    image_url: str,
) -> None:
    """MQ 未就绪时的 fallback：进程内 asyncio 直接调 VL。

    流程与 tasks/ai_task._handle_recognize_task 一致：
    1. 更新状态为 processing
    2. 读取图片字节 → 调 recognize_dish
    3. 写 Mongo + 更新 Redis 为 done
    """
    try:
        from app.utils.bailian_client import recognize_dish
        from app.utils.file_upload import fetch_image_bytes

        await _update_task_state(task_id, status="processing", progress=30)

        image_bytes = await fetch_image_bytes(image_url)
        dishes = await recognize_dish(image_bytes)
        if not dishes:
            await _update_task_state(
                task_id, status="failed", progress=100, error="未识别到菜品"
            )
            return

        await _save_recognize_log(
            task_id=task_id,
            user_id=user_id,
            image_url=image_url,
            dishes=dishes,
        )
        logger.info("camera_task_fallback_done", task_id=task_id, dish_count=len(dishes))
    except Exception as exc:
        logger.error("camera_task_fallback_failed", task_id=task_id, error=str(exc))
        await _update_task_state(
            task_id, status="failed", progress=100, error=str(exc)[:200]
        )


async def _save_recognize_log(
    task_id: str,
    user_id: int | str | None,
    image_url: str,
    dishes: list[dict],
) -> None:
    """识别结果写 Mongo + 更新 Redis 任务状态为 done。

    Mongo 文档结构：
    {
        task_id, user_id, image_url, dishes: [...],
        created_at: ISO8601
    }
    """
    # 补 category_color
    enriched_dishes = [_enrich_dish(d) for d in dishes]
    now_iso = datetime.now(timezone.utc).isoformat()

    # 写 Mongo（motor 异步）
    if mongo_db is not None:
        try:
            await mongo_db[CAMERA_RECOGNIZE_LOG_COLLECTION].insert_one(
                {
                    "task_id": task_id,
                    "user_id": str(user_id) if user_id is not None else None,
                    "image_url": image_url,
                    "dishes": enriched_dishes,
                    "created_at": now_iso,
                }
            )
            logger.info("camera_log_saved_to_mongo", task_id=task_id)
        except Exception as exc:
            # Mongo 写失败不阻断 Redis 状态更新（用户仍能拿到本次结果）
            logger.warning("camera_log_mongo_failed", task_id=task_id, error=str(exc))
    else:
        logger.warning("camera_log_mongo_skip_no_client", task_id=task_id)

    # 更新 Redis 任务状态为 done
    await _update_task_state(
        task_id,
        status="done",
        progress=100,
        dishes=enriched_dishes,
    )


async def get_task_result(task_id: str) -> dict | None:
    """查询任务结果。返回 None 表示任务不存在或已过期。"""
    raw = await redis_client.get(_task_key(task_id))
    if raw is None:
        return None
    return json.loads(raw)


async def list_user_logs(
    user_id: int | str,
    *,
    limit: int = 50,
    skip: int = 0,
) -> list[dict[str, Any]]:
    """查询用户历史识别记录（Mongo，按时间倒序）。

    Mongo 未配置时返回空列表。
    """
    if mongo_db is None:
        return []

    try:
        cursor = (
            mongo_db[CAMERA_RECOGNIZE_LOG_COLLECTION]
            .find({"user_id": str(user_id)})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        # 转 ObjectId 为字符串、剔除内部字段
        for doc in docs:
            doc.pop("_id", None)
        return docs
    except Exception as exc:
        logger.warning("camera_log_query_failed", user_id=user_id, error=str(exc))
        return []
