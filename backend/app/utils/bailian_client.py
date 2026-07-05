"""阿里百炼统一客户端（OpenAI 兼容模式）。

从 services/chat_service.py + services/recognize_service.py 抽取通用入口：
- chat_text()：文本对话（非流式，一次性返回完整文本）
- chat_multimodal()：图片多模态识别（图片 + 文本 prompt → 文本结果）
- recognize_dish()：菜品识别专用封装（阶段 6 新增，返回结构化 dishes 列表）

设计原则：
1. 复用 app/ai/router.py 的 get_route() 路由，业务代码只传 scene
2. 携带统一请求头（Authorization: Bearer + api_key）
3. 内置超时 + 降级模型 fallback（route.fallback）
4. 失败 graceful 抛异常，由调用方决定降级策略

注意：
- 流式 SSE 对话（chat_stream_generator）逻辑复杂，仍保留在 services/chat_service.py
- 本文件只做同步入口，供 health/mood/summary/report 等非流式场景使用
- VL 识图用 DASHSCOPE_API_KEY，文本对话用 BAILIAN_API_KEY（双平台）
- recognize_dish() 内置 prompt + JSON 解析，业务层无需关心 prompt 细节

用法：
    from app.utils.bailian_client import chat_text, chat_multimodal, recognize_dish

    # 文本对话
    reply = await chat_text("chat", [
        {"role": "system", "content": "你是食堂阿姨"},
        {"role": "user", "content": "今天吃啥"},
    ])

    # 图片多模态
    result = await chat_multimodal("recognize", image_bytes, "识别菜品", "image/jpeg")

    # 菜品识别（阶段 6 推荐，自带 prompt + JSON 解析）
    dishes = await recognize_dish(image_bytes, content_type="image/jpeg")
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any

from openai import AsyncOpenAI

from app.ai.router import get_route
from app.config import settings
from app.utils.logger import ai_logger


def _build_client(platform: str) -> AsyncOpenAI:
    """构建百炼 OpenAI 兼容客户端。

    Args:
        platform: "bailian" 用 BAILIAN_API_KEY（对话/周报/情绪）
                  "vl" 用 DASHSCOPE_API_KEY（识图，独立计费）
    """
    if platform == "vl":
        api_key = settings.DASHSCOPE_API_KEY
    else:
        api_key = settings.BAILIAN_API_KEY
    # 统一 base_url（百炼兼容 OpenAI 接口）
    return AsyncOpenAI(
        api_key=api_key,
        base_url=settings.BAILIAN_BASE_URL,
        # 默认请求头：统一鉴权 + 来源标识
        default_headers={
            "Authorization": f"Bearer {api_key}",
            "X-Source": "food-healing-backend",
        },
    )


async def chat_text(
    scene: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> str:
    """文本对话（非流式）。

    Args:
        scene: AI 场景，如 "chat" / "report" / "mood" / "summary"。
               必须在 ai/router.py ROUTES 中已注册。
        messages: OpenAI 消息格式，如 [{"role": "user", "content": "..."}]。
        temperature: 温度，默认 0.7。
        max_tokens: 最大 token，None 则用 route 配置。
        timeout: 超时秒数，None 则用 route 配置。

    Returns:
        模型回复文本。

    Raises:
        Exception: 主模型 + 降级模型均失败时抛出。
    """
    route = get_route(scene)
    client = _build_client(route.platform)
    effective_timeout = timeout or route.timeout
    effective_max_tokens = max_tokens or route.max_tokens

    # 主模型尝试
    try:
        ai_logger.info(
            "bailian_chat_text_call",
            scene=scene,
            model=route.model,
            platform=route.platform,
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=route.model,
                messages=messages,
                max_tokens=effective_max_tokens,
                temperature=temperature,
            ),
            timeout=effective_timeout,
        )
        reply = response.choices[0].message.content or ""
        ai_logger.info(
            "bailian_chat_text_ok",
            scene=scene,
            model=route.model,
            chars=len(reply),
        )
        return reply
    except Exception as exc:
        ai_logger.warning(
            "bailian_chat_text_failed",
            scene=scene,
            model=route.model,
            error=str(exc),
        )
        # 无降级模型，直接抛
        if not route.fallback:
            raise

    # 降级模型尝试
    try:
        ai_logger.info(
            "bailian_chat_text_fallback",
            scene=scene,
            model=route.fallback,
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=route.fallback,
                messages=messages,
                max_tokens=effective_max_tokens,
                temperature=temperature,
            ),
            timeout=effective_timeout,
        )
        reply = response.choices[0].message.content or ""
        ai_logger.info(
            "bailian_chat_text_fallback_ok",
            scene=scene,
            model=route.fallback,
            chars=len(reply),
        )
        return reply
    except Exception as exc:
        ai_logger.error(
            "bailian_chat_text_fallback_failed",
            scene=scene,
            model=route.fallback,
            error=str(exc),
        )
        raise


async def chat_multimodal(
    scene: str,
    image_bytes: bytes,
    text_prompt: str,
    content_type: str = "image/jpeg",
    *,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> str:
    """图片多模态识别。

    Args:
        scene: AI 场景，如 "recognize" / "recognize_receipt"。
        image_bytes: 图片二进制数据。
        text_prompt: 用户文本 prompt，如 "请识别这张图片中的菜品"。
        content_type: 图片 MIME 类型，默认 image/jpeg。
        system_prompt: 系统 prompt（可选），如识菜 JSON 格式要求。
        temperature: 温度，识图默认 0.1（确定性更强）。
        max_tokens: 最大 token，None 则用 route 配置。
        timeout: 超时秒数，None 则用 route 配置。

    Returns:
        模型回复文本（通常是 JSON 字符串，由调用方解析）。

    Raises:
        Exception: 主模型 + 降级模型均失败时抛出。
    """
    route = get_route(scene)
    client = _build_client(route.platform)
    effective_timeout = timeout or route.timeout
    effective_max_tokens = max_tokens or route.max_tokens

    # 图片转 base64 data URL
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    img_url = f"data:{content_type};base64,{img_b64}"

    # 构建多模态消息
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": img_url}},
            {"type": "text", "text": text_prompt},
        ],
    })

    # 主模型尝试
    try:
        ai_logger.info(
            "bailian_chat_multimodal_call",
            scene=scene,
            model=route.model,
            platform=route.platform,
            image_size=len(image_bytes),
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=route.model,
                messages=messages,
                max_tokens=effective_max_tokens,
                temperature=temperature,
            ),
            timeout=effective_timeout,
        )
        content = response.choices[0].message.content or ""
        ai_logger.info(
            "bailian_chat_multimodal_ok",
            scene=scene,
            model=route.model,
            chars=len(content),
        )
        return content
    except Exception as exc:
        ai_logger.warning(
            "bailian_chat_multimodal_failed",
            scene=scene,
            model=route.model,
            error=str(exc),
        )
        if not route.fallback:
            raise

    # 降级模型尝试
    try:
        ai_logger.info(
            "bailian_chat_multimodal_fallback",
            scene=scene,
            model=route.fallback,
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=route.fallback,
                messages=messages,
                max_tokens=effective_max_tokens,
                temperature=temperature,
            ),
            timeout=effective_timeout,
        )
        content = response.choices[0].message.content or ""
        ai_logger.info(
            "bailian_chat_multimodal_fallback_ok",
            scene=scene,
            model=route.fallback,
            chars=len(content),
        )
        return content
    except Exception as exc:
        ai_logger.error(
            "bailian_chat_multimodal_fallback_failed",
            scene=scene,
            model=route.fallback,
            error=str(exc),
        )
        raise


# ===== 菜品识别专用封装（阶段 6 新增）=====

async def recognize_dish(
    image_bytes: bytes,
    content_type: str = "image/jpeg",
    *,
    timeout: int | None = None,
) -> list[dict]:
    """菜品识别专用接口（阶段 6 推荐）。

    内置识菜 prompt + JSON 解析，业务层无需关心 prompt 细节。
    复用 chat_multimodal 的主模型 + 降级模型双 try 机制。

    Args:
        image_bytes: 图片二进制。
        content_type: 图片 MIME，默认 image/jpeg。
        timeout: 超时秒数，None 用 route 配置（40s）。

    Returns:
        dishes 列表，每项结构：
        {
            "name": "红烧鸡",
            "category": "肉类",
            "unit": "份(150g)",
            "kcal": 250,
            "protein": 22,
            "carb": 8,
            "fat": 15,
            "confidence": 0.92
        }

    Raises:
        Exception: 主模型 + 降级模型均失败，或返回内容无法解析为 JSON。
    """
    from app.constants import RECOGNIZE_DISH_SYSTEM_PROMPT, RECOGNIZE_DISH_USER_PROMPT

    raw = await chat_multimodal(
        scene="recognize",
        image_bytes=image_bytes,
        text_prompt=RECOGNIZE_DISH_USER_PROMPT,
        content_type=content_type,
        system_prompt=RECOGNIZE_DISH_SYSTEM_PROMPT,
        temperature=0.1,
        timeout=timeout,
    )

    return _parse_dishes_json(raw)


def _parse_dishes_json(content: str) -> list[dict]:
    """从 Qwen-VL 返回文本中解析 dishes 数组。

    容错策略：
    1. 去除 markdown 代码块包裹
    2. 直接 json.loads
    3. 失败则正则提取 {...} 部分再解析
    4. dishes 字段可能是 dict 或 list，统一转 list
    """
    import json
    import re

    content = (content or "").strip()
    # 去除 markdown 代码块
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.endswith("```"):
            content = content[:-3]
    content = content.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            ai_logger.error("recognize_dish_parse_failed", content=content[:500])
            raise
        data = json.loads(match.group())

    dishes = data.get("dishes", [])
    if isinstance(dishes, dict):
        dishes = [dishes]
    if not isinstance(dishes, list):
        dishes = []
    return dishes


# ===== 营养师对话专用封装（Phase 3 新增）=====

async def chat_with_diet_context(
    user_question: str,
    diet_context: str,
    history_messages: list[dict[str, str]] | None = None,
    *,
    system_prompt: str | None = None,
    scene: str = "chat",
    temperature: float = 0.7,
    timeout: int | None = None,
) -> str:
    """携带用户当日饮食上下文的营养师对话（非流式）。

    与 chat_text 的差异：
    1. 自动拼接 system_prompt（默认营养师角色）
    2. 自动将 diet_context 作为 system 消息追加（让 AI 看到当日三餐数据）
    3. 支持传入历史对话记录 history_messages，保持上下文连贯
    4. 业务层无需手动构造 messages 数组

    Args:
        user_question: 用户本次提问内容
        diet_context: 用户当日饮食数据拼接的上下文字符串（可为空）
        history_messages: 历史对话记录，格式 [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}]
        system_prompt: 自定义系统提示词，None 则用 NUTRITIONIST_SYSTEM_PROMPT
        scene: AI 场景，默认 "chat"
        temperature: 温度，默认 0.7
        timeout: 超时秒数，None 用 route 配置

    Returns:
        AI 回复文本

    Raises:
        Exception: 主模型 + 降级模型均失败时抛出。
    """
    from app.constants import NUTRITIONIST_SYSTEM_PROMPT

    # 1. 构造 messages：system_prompt + diet_context + history + user
    messages: list[dict[str, str]] = []

    # 系统 prompt（营养师角色）
    effective_system = system_prompt or NUTRITIONIST_SYSTEM_PROMPT
    messages.append({"role": "system", "content": effective_system})

    # 当日饮食上下文（作为 system 消息追加，让 AI 始终看到当日数据）
    if diet_context:
        messages.append({
            "role": "system",
            "content": f"【用户当日饮食记录】\n{diet_context}",
        })

    # 历史对话记录（保持上下文连贯）
    if history_messages:
        for msg in history_messages:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # 本次提问
    messages.append({"role": "user", "content": user_question})

    return await chat_text(
        scene=scene,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )

