"""AI 对话 SSE 服务。

流程：
1. 取 user_habits（MySQL 长期记忆：口味/过敏/不喜欢/饮食目标/健康档案/对话摘要）
2. 取 Redis 短期对话历史（1h TTL，最近 20 轮）
3. 拼 system prompt（人格 + 记忆 + 偏好）
4. 路由模型 get_route('chat') → qwen3.7-plus（fallback qwen3.7-flash）
5. 调百练 SSE 流式（openai SDK, stream=True）
6. 推回标准 SSE 多事件协议（delta / memory_hint / done）
7. 完成后写入 Redis 短期对话历史

SSE 事件协议（与 frontend/js/api.js parseSseChunk 对齐）：
  event: delta
  data: {"delta":"今","done":false}

  event: memory_hint
  data: {"hint":"你上周说胃不舒服"}

  event: done
  data: {"delta":"","done":true}
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.ai.router import get_route
from app.config import settings
from app.database import redis_client
from app.utils.logger import logger

# 阶段 2 重构备注：
# user_habits 表已废弃（MySQL 迁 PG），长期记忆后续阶段改用 user_body_target + MongoDB。
# 当前 _load_user_habits 返回 {}，AI 仍能正常对话，仅缺少个性化记忆。


CHAT_HISTORY_PREFIX = f"{settings.REDIS_KEY_PREFIX}chat_history:"
CHAT_HISTORY_TTL = 3600
CHAT_HISTORY_MAX_TURNS = 20

PERSONAS = {
    "canteen_aunt": {
        "name": "食堂阿姨",
        "style": "热情、关切、像妈妈一样叮嘱吃饭。语气亲切接地气，会唠两句家常。",
    },
    "nutritionist": {
        "name": "营养师",
        "style": "专业、温和、用通俗语言解释营养知识，关注均衡搭配。",
    },
    "fitness_coach": {
        "name": "健身教练",
        "style": "积极、鼓励、关注蛋白质摄入和运动消耗。",
    },
}

GOAL_LABELS = {"daily": "日常均衡", "fitness": "健身增肌", "weight_loss": "减脂控卡"}


def _history_key(user_id: int) -> str:
    return f"{CHAT_HISTORY_PREFIX}{user_id}"


def _format_event(event: str, data: dict) -> str:
    """格式化标准 SSE 事件（event + data + 空行结束）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _load_user_habits(user_id: int) -> dict:
    """取用户长期记忆。

    阶段 2 重构：user_habits 表已废弃，返回 {}。
    后续阶段改用 user_body_target + MongoDB ai_chat_history.daily_summary。
    """
    return {}


async def _load_chat_history(user_id: int) -> list[dict]:
    """从 Redis 取短期对话历史。"""
    try:
        raw = await redis_client.get(_history_key(user_id))
        if raw is None:
            return []
        return json.loads(raw)
    except Exception as exc:
        logger.warning("load_chat_history_failed", user_id=user_id, error=str(exc))
        return []


async def _save_chat_history(user_id: int, history: list[dict]) -> None:
    """写入 Redis 短期对话历史，保留最近 N 轮。"""
    try:
        max_msgs = CHAT_HISTORY_MAX_TURNS * 2
        if len(history) > max_msgs:
            history = history[-max_msgs:]
        await redis_client.set(
            _history_key(user_id),
            json.dumps(history, ensure_ascii=False),
            ex=CHAT_HISTORY_TTL,
        )
    except Exception as exc:
        logger.warning("save_chat_history_failed", user_id=user_id, error=str(exc))


def _build_system_prompt(habits: dict, persona: str) -> str:
    """拼接 system prompt：人格 + 记忆 + 偏好 + 约束。"""
    persona_def = PERSONAS.get(persona, PERSONAS["canteen_aunt"])

    parts = [
        f"你是「食愈校园」的 AI 食堂搭子，人格设定：{persona_def['name']}。",
        f"说话风格：{persona_def['style']}",
        "",
        "你的职责：",
        "1. 根据用户的口味偏好、健康档案、饮食目标，给出个性化的食堂点餐建议",
        "2. 关心用户的情绪和饮食状态，像朋友一样陪伴",
        "3. 回答简洁温暖，控制在 100 字以内（除非用户要求详细）",
        "4. 涉及具体菜品时，结合食堂常见菜（红烧鸡、酸辣土豆丝、番茄炒蛋、宫保鸡丁等）",
        "",
    ]

    if habits.get("taste_preferences"):
        parts.append(
            f"用户口味偏好：{json.dumps(habits['taste_preferences'], ensure_ascii=False)}"
        )

    if habits.get("allergies"):
        parts.append(
            f"⚠️ 过敏原：{json.dumps(habits['allergies'], ensure_ascii=False)}（必须避免推荐含过敏原的菜）"
        )

    if habits.get("dislikes"):
        parts.append(
            f"不喜欢的菜：{json.dumps(habits['dislikes'], ensure_ascii=False)}"
        )

    if habits.get("dietary_goal"):
        goal_label = GOAL_LABELS.get(habits["dietary_goal"], habits["dietary_goal"])
        parts.append(f"饮食目标：{goal_label}")

    if habits.get("health_profile"):
        parts.append(
            f"健康档案：{json.dumps(habits['health_profile'], ensure_ascii=False)}"
        )

    if habits.get("conversation_summary"):
        parts.append(f"历史记忆摘要：{habits['conversation_summary']}")

    return "\n".join(parts)


def _extract_memory_hint(habits: dict) -> str | None:
    """从长期记忆中提取一条提示给前端展示（蓝色记忆气泡）。

    优先级：conversation_summary > dislikes > allergies
    """
    summary = habits.get("conversation_summary")
    if summary:
        first_sentence = summary.split("。")[0]
        if first_sentence:
            text = first_sentence + "。" if not first_sentence.endswith("。") else first_sentence
            return text[:50]

    dislikes = habits.get("dislikes")
    if dislikes:
        items = dislikes if isinstance(dislikes, list) else list(dislikes.values())
        if items:
            first = items[0] if not isinstance(items[0], dict) else str(items[0])
            return f"你不喜欢 {first}，给你换个别的～"

    allergies = habits.get("allergies")
    if allergies:
        items = allergies if isinstance(allergies, list) else list(allergies.values())
        if items:
            first = items[0] if not isinstance(items[0], dict) else str(items[0])
            return f"⚠️ 你对 {first} 过敏，已避开"

    return None


def _build_client() -> AsyncOpenAI:
    """构建百练 OpenAI 兼容客户端。"""
    return AsyncOpenAI(
        api_key=settings.BAILIAN_API_KEY,
        base_url=settings.BAILIAN_BASE_URL,
    )


async def chat_stream_generator(
    user_id: int,
    persona: str,
    messages: list[dict],
    context: dict | None,
) -> AsyncGenerator[str, None]:
    """生成标准 SSE 多事件协议事件流。

    事件顺序：
    1. memory_hint（可选，开头一次）
    2. delta（多次，文本增量）
    3. done（结束标记）
    """
    # 1. 加载长期记忆
    habits = await _load_user_habits(user_id)

    # 2. 推送 memory_hint（如果有）
    hint = _extract_memory_hint(habits)
    if hint:
        yield _format_event("memory_hint", {"hint": hint})

    # 3. 加载短期对话历史
    history = await _load_chat_history(user_id)

    # 4. 拼 system prompt
    system_prompt = _build_system_prompt(habits, persona)

    # 5. 构建完整消息列表
    full_messages = [{"role": "system", "content": system_prompt}] + history + messages

    # 6. 调百练 SSE 流式
    route = get_route("chat")
    client = _build_client()

    accumulated_text = ""

    try:
        stream = await asyncio.wait_for(
            client.chat.completions.create(
                model=route.model,
                messages=full_messages,
                max_tokens=route.max_tokens,
                temperature=0.7,
                stream=True,
            ),
            timeout=route.timeout,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                accumulated_text += delta.content
                yield _format_event("delta", {"delta": delta.content, "done": False})

        # 推送 done
        yield _format_event("done", {"delta": "", "done": True})

        # 7. 保存对话历史
        history.extend(messages)
        history.append({"role": "assistant", "content": accumulated_text})
        await _save_chat_history(user_id, history)

        logger.info(
            "chat_stream_done",
            user_id=user_id,
            persona=persona,
            chars=len(accumulated_text),
        )

    except asyncio.TimeoutError:
        logger.error("chat_stream_timeout", user_id=user_id)
        yield _format_event("delta", {"delta": "（AI 思考超时了，稍等再问～）", "done": False})
        yield _format_event("done", {"delta": "", "done": True})
    except Exception as exc:
        logger.error("chat_stream_failed", user_id=user_id, error=str(exc))
        # 尝试降级模型
        if route.fallback:
            try:
                stream = await client.chat.completions.create(
                    model=route.fallback,
                    messages=full_messages,
                    max_tokens=route.max_tokens,
                    temperature=0.7,
                    stream=True,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        accumulated_text += delta.content
                        yield _format_event(
                            "delta", {"delta": delta.content, "done": False}
                        )
                yield _format_event("done", {"delta": "", "done": True})
                history.extend(messages)
                history.append({"role": "assistant", "content": accumulated_text})
                await _save_chat_history(user_id, history)
                logger.info("chat_stream_fallback_ok", user_id=user_id, model=route.fallback)
                return
            except Exception as fallback_exc:
                logger.error("chat_stream_fallback_failed", error=str(fallback_exc))
        yield _format_event("delta", {"delta": "AI 搭子走神了，稍等再问～", "done": False})
        yield _format_event("done", {"delta": "", "done": True})


async def chat_non_stream(
    user_id: int,
    persona: str,
    messages: list[dict],
    context: dict | None,
) -> dict:
    """非流式对话（降级模式，一次性返回）。

    Returns:
        {"reply": str, "memoryHint": str | None}
    """
    habits = await _load_user_habits(user_id)
    hint = _extract_memory_hint(habits)
    history = await _load_chat_history(user_id)
    system_prompt = _build_system_prompt(habits, persona)
    full_messages = [{"role": "system", "content": system_prompt}] + history + messages

    route = get_route("chat")
    client = _build_client()

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=route.model,
                messages=full_messages,
                max_tokens=route.max_tokens,
                temperature=0.7,
            ),
            timeout=route.timeout,
        )
        reply = response.choices[0].message.content or ""
    except Exception:
        if not route.fallback:
            raise
        logger.warning("chat_non_stream_fallback", user_id=user_id)
        response = await client.chat.completions.create(
            model=route.fallback,
            messages=full_messages,
            max_tokens=route.max_tokens,
            temperature=0.7,
        )
        reply = response.choices[0].message.content or ""

    history.extend(messages)
    history.append({"role": "assistant", "content": reply})
    await _save_chat_history(user_id, history)

    logger.info("chat_non_stream_done", user_id=user_id, chars=len(reply))
    return {"reply": reply, "memoryHint": hint}
