"""识菜识别服务。

异步链路：提交任务 → Redis 存状态 → 后台调 Qwen-VL → 入库 PG → Redis 更新结果。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import date, datetime

from openai import AsyncOpenAI

from app.ai.router import get_route
from app.config import settings
from app.database import redis_client
from app.utils.logger import logger

# 阶段 2 重构备注：
# NutritionLog 表已废弃，识菜结果入库改用 meal_item + daily_diet_record。
# 当前 _save_nutrition_log 跳过入库，仅保留 Redis 任务状态。
# 后续阶段实现 meal_item 入库逻辑。

# Redis key 前缀
TASK_KEY_PREFIX = f"{settings.REDIS_KEY_PREFIX}recognize_task:"
TASK_TTL = 600  # 任务状态保留 10 分钟

# Qwen-VL 识菜 Prompt：食材 → 菜品推荐 → 营养搭配
RECOGNIZE_SYSTEM_PROMPT = """你是校园食堂的营养搭配助手。用户拍了一张食材照片，请按以下步骤分析：

1. 识别图片中的所有食材（生食材）
2. 根据食材组合，推荐一道食堂能做的成品菜（如：鸡蛋+西红柿 → 西红柿炒鸡蛋）
3. 估算这道成品菜每份的营养成分
4. 根据营养均衡原则，建议还需要搭配什么类别的食物

严格按以下 JSON 返回，不要包含其他文字：
{
  "ingredients": [
    { "name": "鸡蛋", "confidence": 0.95 },
    { "name": "西红柿", "confidence": 0.90 }
  ],
  "suggested_dish": {
    "name": "西红柿炒鸡蛋",
    "category": "蔬菜",
    "unit": "份(200g)",
    "kcal": 140,
    "protein": 8,
    "carb": 8,
    "fat": 8,
    "reason": "西红柿炒鸡蛋是食堂经典搭配，酸甜开胃，蛋白质和维生素均衡"
  },
  "pairing": {
    "missing": "主食",
    "tip": "建议搭配一份米饭或馒头，再加一碗汤就更完美了",
    "recommend_pair": ["白米饭", "紫菜蛋花汤"]
  }
}

注意：
- suggested_dish.name 必须是食堂常见的成品菜名，不能是生食材名
- category 从以下选：主食、肉类、蔬菜、蛋奶、汤品、水果、豆制品、水产
- 营养成分要符合常识，不能偏差太大
- pairing.missing 指出当前搭配缺少的类别
"""


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def _generate_task_id() -> str:
    return f"rec_{uuid.uuid4().hex[:12]}"


async def submit_recognize_task(
    image_bytes: bytes,
    content_type: str,
    user_id: int | None = None,
    meal_hint: str | None = None,
) -> str:
    """提交识菜任务，返回 task_id。

    1. 生成 task_id，写 Redis（status=pending）
    2. 启动后台 asyncio task 调用 Qwen-VL
    3. 立即返回 task_id
    """
    task_id = _generate_task_id()
    initial_state = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "user_id": user_id,
        "meal_hint": meal_hint,
        "created_at": datetime.utcnow().isoformat(),
    }
    await redis_client.set(
        _task_key(task_id), json.dumps(initial_state, ensure_ascii=False), ex=TASK_TTL
    )
    logger.info("recognize_task_created", task_id=task_id)

    # 后台处理
    asyncio.create_task(
        _process_recognize(task_id, image_bytes, content_type, user_id, meal_hint)
    )

    return task_id


async def get_task_result(task_id: str) -> dict | None:
    """查询任务结果。返回 None 表示任务不存在。"""
    raw = await redis_client.get(_task_key(task_id))
    if raw is None:
        return None
    return json.loads(raw)


async def _process_recognize(
    task_id: str,
    image_bytes: bytes,
    content_type: str,
    user_id: int | None,
    meal_hint: str | None,
) -> None:
    """后台处理：调 Qwen-VL → 解析 → 入库 → 更新 Redis。"""
    try:
        # 更新进度
        await _update_task(task_id, status="processing", progress=30)

        # 调 Qwen-VL
        result = await _call_qwen_vl(image_bytes, content_type)
        if not result or not result.get("suggested_dish"):
            await _update_task(
                task_id, status="failed", progress=100, error="未识别到食材"
            )
            return

        await _update_task(task_id, progress=70)

        dish = result["suggested_dish"]
        ingredients = result.get("ingredients", [])
        pairing = result.get("pairing", {})

        result_data = {
            "task_id": task_id,
            "status": "done",
            "progress": 100,
            "ingredients": ingredients,
            "dish": {
                "id": f"r{int(time.time() * 1000)}",
                "name": dish["name"],
                "category": dish.get("category", "其他"),
                "unit": dish.get("unit", "份"),
                "kcal": dish.get("kcal", 0),
                "protein": dish.get("protein", 0),
                "carb": dish.get("carb", 0),
                "fat": dish.get("fat", 0),
                "reason": dish.get("reason", ""),
                "matched": True,
            },
            "pairing": pairing,
        }
        await redis_client.set(
            _task_key(task_id),
            json.dumps(result_data, ensure_ascii=False),
            ex=TASK_TTL,
        )
        logger.info("recognize_task_done", task_id=task_id, dish=dish["name"])

    except json.JSONDecodeError as exc:
        # VL 响应被 max_tokens 截断 / 模型返回非标准 JSON
        logger.error(
            "recognize_vl_parse_failed",
            task_id=task_id,
            error=str(exc),
        )
        await _update_task(
            task_id,
            status="failed",
            progress=100,
            error="AI 识别结果解析失败，请重新拍摄或换张清晰照片",
        )
    except Exception as exc:
        logger.error("recognize_task_failed", task_id=task_id, error=str(exc))
        await _update_task(
            task_id, status="failed", progress=100, error=str(exc)[:200]
        )


async def _update_task(
    task_id: str,
    status: str | None = None,
    progress: int | None = None,
    error: str | None = None,
) -> None:
    """部分更新任务状态字段。"""
    raw = await redis_client.get(_task_key(task_id))
    if raw is None:
        return
    data = json.loads(raw)
    if status is not None:
        data["status"] = status
    if progress is not None:
        data["progress"] = progress
    if error is not None:
        data["error"] = error
    await redis_client.set(
        _task_key(task_id), json.dumps(data, ensure_ascii=False), ex=TASK_TTL
    )


async def _call_qwen_vl(image_bytes: bytes, content_type: str) -> dict:
    """调用 Qwen-VL 模型识别菜品。

    使用 DashScope 兼容 OpenAI 接口。
    VL 走 dashscope，用 DASHSCOPE_API_KEY（不是 BAILIAN_API_KEY）。
    超时与 max_tokens 由 ai.router.get_route('recognize') 集中配置，
    业务代码不硬编码。
    """
    import base64

    route = get_route("recognize")

    client = AsyncOpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.BAILIAN_BASE_URL,
    )

    # 图片转 base64 data URL
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    img_url = f"data:{content_type};base64,{img_b64}"

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=route.model,
                messages=[
                    {"role": "system", "content": RECOGNIZE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": img_url},
                            },
                            {
                                "type": "text",
                                "text": "请识别这张图片中的菜品，返回 JSON。",
                            },
                        ],
                    },
                ],
                max_tokens=route.max_tokens,
                temperature=0.1,
            ),
            timeout=route.timeout,
        )

        content = response.choices[0].message.content or ""
        logger.info("qwen_vl_response", raw=content[:300])

        # 解析 JSON 响应
        result = _parse_vl_response(content)
        return result

    except asyncio.TimeoutError:
        logger.error("qwen_vl_timeout")
        # 尝试降级模型
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=route.fallback or settings.QWEN_VL_MODEL_FALLBACK,
                    messages=[
                        {"role": "system", "content": RECOGNIZE_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": img_url}},
                                {"type": "text", "text": "请识别这张图片中的菜品，返回 JSON。"},
                            ],
                        },
                    ],
                    max_tokens=route.max_tokens,
                    temperature=0.1,
                ),
                timeout=route.timeout,
            )
            content = response.choices[0].message.content or ""
            return _parse_vl_response(content)
        except Exception as e:
            logger.error("qwen_vl_fallback_failed", error=str(e))
            raise


def _parse_vl_response(content: str) -> dict:
    """从 Qwen-VL 返回中提取完整结果（ingredients + suggested_dish + pairing）。"""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.endswith("```"):
            content = content[:-3]
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            data = json.loads(match.group())
        else:
            logger.error("vl_parse_failed", content=content[:500])
            raise
    return data


async def _save_nutrition_log(
    user_id: int | None,
    meal_hint: str | None,
    dishes: list[dict],
) -> None:
    """将识菜结果写入数据库。

    阶段 2 重构：NutritionLog 表已废弃，后续阶段改用 meal_item + daily_diet_record。
    当前跳过入库，仅记录日志。
    """
    if not user_id:
        return
    total_kcal = sum(d.get("kcal", 0) for d in dishes)
    logger.info(
        "nutrition_log_skipped_phase2",
        user_id=user_id,
        meal=meal_hint or "lunch",
        kcal=total_kcal,
        dish_count=len(dishes),
    )
