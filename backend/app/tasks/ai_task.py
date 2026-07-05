"""AI 异步任务消费者（阶段 6 新增）。

- 队列：ai_recognize_queue
- 路由键：task.ai.recognize
- 消费者逻辑：接收 {task_id, user_id, image_url} → 调百炼 recognize_dish → 写 Mongo → 更新 Redis

部署模式：
- 进程内 asyncio 后台任务（main.py lifespan 启动时 spawn）
- RABBITMQ_URL 为空时 graceful 跳过（camera_service fallback 到 asyncio.create_task）

设计原则：
1. 消费者独立 asyncio task，不阻塞 FastAPI 主事件循环
2. 单消息处理失败不退出，记日志后 nack（避免消息丢失）
3. 复用 utils/bailian_client.recognize_dish 调 VL
4. 复用 services/camera_service._save_recognize_log 写 Mongo + 更新 Redis
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aio_pika

from app.constants import AI_RECOGNIZE_QUEUE, AI_RECOGNIZE_ROUTING_KEY
from app.database import redis_client
from app.utils.logger import logger

# 全局消费者任务句柄（main.py lifespan 关闭时取消）
_consumer_task: asyncio.Task | None = None
# 消费者连接（关闭时释放）
_consumer_connection: aio_pika.abc.AbstractRobustConnection | None = None


async def start_recognize_consumer() -> bool:
    """启动识菜 MQ 消费者（进程内 asyncio 后台任务）。

    RABBITMQ_URL 为空或连接失败时返回 False（graceful 跳过，
    camera_service 会 fallback 到 asyncio.create_task）。

    Returns:
        True 已启动；False 未配置或失败。
    """
    global _consumer_task, _consumer_connection

    from app.config import settings
    if not settings.RABBITMQ_URL:
        logger.info("recognize_consumer_skip_no_url")
        return False

    try:
        _consumer_connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL, timeout=5
        )
        channel = await _consumer_connection.channel()
        # 公平分发：同一时间只处理 1 条消息（避免单进程 OOM）
        await channel.set_qos(prefetch_count=1)

        # 声明持久化队列（与生产者路由键绑定）
        exchange = await channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        queue = await channel.declare_queue(AI_RECOGNIZE_QUEUE, durable=True)
        await queue.bind(exchange, routing_key=AI_RECOGNIZE_ROUTING_KEY)

        async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
            """单条消息处理：解析 → 调 VL → 写 Mongo → 更新 Redis。"""
            async with message.process(ignore_processing_fail=True):
                try:
                    body = json.loads(message.body.decode("utf-8"))
                    await _handle_recognize_task(body)
                except Exception as exc:
                    # 处理失败不抛（避免无限重投），记日志后 ack
                    # 任务最终状态由 _handle_recognize_task 内部更新为 failed
                    logger.error(
                        "recognize_consumer_msg_failed",
                        error=str(exc),
                        body_preview=message.body[:200],
                    )

        await queue.consume(_on_message)
        _consumer_task = asyncio.current_task()
        logger.info(
            "recognize_consumer_started",
            queue=AI_RECOGNIZE_QUEUE,
            routing_key=AI_RECOGNIZE_ROUTING_KEY,
        )
        return True
    except Exception as exc:
        logger.warning("recognize_consumer_init_failed", error=str(exc))
        _consumer_connection = None
        return False


async def stop_recognize_consumer() -> None:
    """关闭消费者连接（main.py lifespan 关闭时调用）。"""
    global _consumer_connection
    if _consumer_connection is None:
        return
    try:
        await _consumer_connection.close()
        logger.info("recognize_consumer_stopped")
    except Exception as exc:
        logger.warning("recognize_consumer_stop_failed", error=str(exc))
    finally:
        _consumer_connection = None


async def _handle_recognize_task(body: dict[str, Any]) -> None:
    """处理单条识菜任务消息。

    流程：
    1. 从 body 取 task_id / user_id / image_url
    2. 更新 Redis 任务状态为 processing
    3. 读取图片字节 → 调 recognize_dish → 解析 dishes
    4. 写 Mongo camera_recognize_log 集合
    5. 更新 Redis 任务状态为 done（含 dishes 数据）

    失败时更新 Redis 任务状态为 failed（含 error 信息）。
    """
    from app.constants import CAMERA_TASK_KEY_PREFIX, CAMERA_TASK_TTL
    from app.services.camera_service import _save_recognize_log, _update_task_state
    from app.utils.bailian_client import recognize_dish
    from app.utils.file_upload import fetch_image_bytes

    task_id = body.get("task_id")
    user_id = body.get("user_id")
    image_url = body.get("image_url")

    if not task_id or not image_url:
        logger.warning("recognize_consumer_invalid_body", body=body)
        return

    logger.info("recognize_consumer_handle", task_id=task_id, user_id=user_id)

    # 更新状态为 processing
    await _update_task_state(task_id, status="processing", progress=30)

    try:
        # 读取本地图片字节
        image_bytes = await fetch_image_bytes(image_url)

        # 调 VL 识别
        dishes = await recognize_dish(image_bytes)
        if not dishes:
            await _update_task_state(
                task_id, status="failed", progress=100, error="未识别到菜品"
            )
            return

        # 写 Mongo + 更新 Redis 任务状态为 done
        await _save_recognize_log(
            task_id=task_id,
            user_id=user_id,
            image_url=image_url,
            dishes=dishes,
        )

        logger.info(
            "recognize_consumer_done",
            task_id=task_id,
            dish_count=len(dishes),
            primary=dishes[0].get("name") if dishes else None,
        )
    except Exception as exc:
        logger.error(
            "recognize_consumer_failed",
            task_id=task_id,
            error=str(exc),
        )
        await _update_task_state(
            task_id, status="failed", progress=100, error=str(exc)[:200]
        )


async def publish_recognize_task(task_data: dict[str, Any]) -> bool:
    """发送识菜任务到 MQ（camera_service 调用）。

    Args:
        task_data: {task_id, user_id, image_url}

    Returns:
        True 发送成功；False MQ 未就绪（调用方应 fallback 到 asyncio.create_task）。
    """
    from app.db.rabbitmq_producer import publish
    return await publish(
        routing_key=AI_RECOGNIZE_ROUTING_KEY,
        body=task_data,
    )


# ============================================================
# Phase 3 新增：每日 AI 营养简报消费者
# ============================================================

# 每日简报消费者独立连接（与识菜消费者隔离，避免互相影响）
_daily_consumer_task: asyncio.Task | None = None
_daily_consumer_connection: aio_pika.abc.AbstractRobustConnection | None = None


async def start_daily_summary_consumer() -> bool:
    """启动每日 AI 简报 MQ 消费者（进程内 asyncio 后台任务）。

    监听 ai_daily_summary_queue，收到 {user_id, report_date} 后：
    1. 读取用户当日饮食数据
    2. 调百炼生成每日营养简报
    3. 写入 Mongo ai_daily_report 集合
    4. 推送一条 AI 类型系统消息通知用户

    RABBITMQ_URL 为空或连接失败时返回 False（graceful 跳过）。

    Returns:
        True 已启动；False 未配置或失败。
    """
    global _daily_consumer_task, _daily_consumer_connection

    from app.config import settings
    if not settings.RABBITMQ_URL:
        logger.info("daily_summary_consumer_skip_no_url")
        return False

    _daily_consumer_task = asyncio.create_task(_run_daily_summary_consumer())
    logger.info("daily_summary_consumer_started")
    return True


async def stop_daily_summary_consumer() -> None:
    """关闭每日简报消费者连接。"""
    global _daily_consumer_task, _daily_consumer_connection

    if _daily_consumer_task is not None:
        _daily_consumer_task.cancel()
        try:
            await _daily_consumer_task
        except asyncio.CancelledError:
            pass
        _daily_consumer_task = None

    if _daily_consumer_connection is not None:
        try:
            await _daily_consumer_connection.close()
        except Exception:
            pass
        _daily_consumer_connection = None

    logger.info("daily_summary_consumer_stopped")


async def _run_daily_summary_consumer() -> None:
    """每日简报消费者主循环（后台 task 跑）。"""
    global _daily_consumer_connection

    from app.config import settings
    from app.constants import AI_DAILY_SUMMARY_QUEUE, AI_DAILY_SUMMARY_ROUTING_KEY

    try:
        _daily_consumer_connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL, timeout=5
        )
        async with _daily_consumer_connection:
            channel = await _daily_consumer_connection.channel()
            await channel.set_qos(prefetch_count=1)

            exchange = await channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )
            queue = await channel.declare_queue(AI_DAILY_SUMMARY_QUEUE, durable=True)
            await queue.bind(exchange, routing_key=AI_DAILY_SUMMARY_ROUTING_KEY)

            logger.info(
                "daily_summary_consumer_ready",
                queue=AI_DAILY_SUMMARY_QUEUE,
                routing_key=AI_DAILY_SUMMARY_ROUTING_KEY,
            )
            await queue.consume(_on_daily_summary_message, no_ack=False)
            await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("daily_summary_consumer_cancelled")
        raise
    except Exception as exc:
        logger.error("daily_summary_consumer_crashed", error=str(exc))


async def _on_daily_summary_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """处理单条每日简报任务消息。"""
    async with message.process(ignore_processed=True):
        try:
            body = json.loads(message.body.decode("utf-8"))
            await _handle_daily_summary_task(body)
        except Exception as exc:
            logger.error(
                "daily_summary_consumer_msg_failed",
                error=str(exc),
                body_preview=message.body[:200],
            )


async def _handle_daily_summary_task(body: dict[str, Any]) -> None:
    """处理单条每日简报任务。

    流程：
    1. 从 body 取 user_id / report_date
    2. 调 ai_service.generate_daily_summary 生成简报
    3. 推送 AI 类型系统消息通知用户

    失败时仅记日志，不抛（避免消息重投造成重复生成）。
    """
    from app.services.ai_service import generate_daily_summary
    from app.services.message_service import create_message
    from app.constants import MSG_TYPE_AI

    user_id = body.get("user_id")
    report_date = body.get("report_date")

    if not user_id or not report_date:
        logger.warning("daily_summary_invalid_body", body=body)
        return

    logger.info("daily_summary_handle_start", user_id=user_id, report_date=report_date)

    try:
        report_content = await generate_daily_summary(
            user_id=int(user_id),
            report_date=str(report_date),
        )
        if not report_content:
            logger.warning(
                "daily_summary_empty",
                user_id=user_id,
                report_date=report_date,
            )
            return

        # 推送一条 AI 类型系统消息
        await create_message(
            user_id=int(user_id),
            msg_type=MSG_TYPE_AI,
            title=f"你的 {report_date} 营养简报已生成",
            content="点击查看今日 AI 营养分析与明日食谱推荐",
        )

        logger.info(
            "daily_summary_handle_done",
            user_id=user_id,
            report_date=report_date,
            content_chars=len(report_content),
        )
    except Exception as exc:
        logger.error(
            "daily_summary_handle_failed",
            user_id=user_id,
            report_date=report_date,
            error=str(exc),
        )


async def publish_daily_summary_task(user_id: int, report_date: str) -> bool:
    """发送每日简报任务到 MQ（ai_service 触发）。

    Args:
        user_id: 目标用户 ID
        report_date: 报告日期 YYYY-MM-DD

    Returns:
        True 发送成功；False MQ 未就绪（调用方应 fallback 到 asyncio.create_task）。
    """
    from app.constants import AI_DAILY_SUMMARY_ROUTING_KEY
    from app.db.rabbitmq_producer import publish

    return await publish(
        routing_key=AI_DAILY_SUMMARY_ROUTING_KEY,
        body={"user_id": user_id, "report_date": report_date},
    )

