"""多模型路由表。

按后端技术规范 §7.2：
- 场景 → 平台 → 模型 → 超时 → 重试 → 降级模型
- 业务代码只传 scene 字符串，不直接传模型名
- 模型名集中在 app/config.py

Phase 0 仅声明路由表，实际调用在 Phase 1+ 实现。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.config import settings


Platform = Literal["vl", "bailian"]


class RouteSpec(BaseModel):
    """单条路由规则。"""

    platform: Platform
    model: str
    fallback: str | None = None
    timeout: int = 20
    retry: int = 2
    max_tokens: int = 512


ROUTES: dict[str, RouteSpec] = {
    "recognize": RouteSpec(
        platform="vl",
        model=settings.QWEN_VL_MODEL,
        fallback=settings.QWEN_VL_MODEL_FALLBACK,
        timeout=40,
        retry=2,
        max_tokens=800,
    ),
    "recognize_receipt": RouteSpec(
        platform="vl",
        model=settings.QWEN_VL_MODEL,
        fallback=settings.QWEN_VL_MODEL_FALLBACK,
        timeout=40,
        retry=2,
        max_tokens=800,
    ),
    "chat": RouteSpec(
        platform="bailian",
        model=settings.QWEN_PLUS_MODEL,
        fallback=settings.QWEN_FLASH_MODEL,
        timeout=20,
        retry=2,
        max_tokens=512,
    ),
    "report": RouteSpec(
        platform="bailian",
        model=settings.QWEN_MAX_MODEL,
        fallback=settings.QWEN_PLUS_MODEL,
        timeout=30,
        retry=2,
        max_tokens=300,
    ),
    "mood": RouteSpec(
        platform="bailian",
        model=settings.QWEN_FLASH_MODEL,
        fallback=None,
        timeout=10,
        retry=1,
        max_tokens=80,
    ),
    "summary": RouteSpec(
        platform="bailian",
        model=settings.QWEN_FLASH_MODEL,
        fallback=None,
        timeout=10,
        retry=1,
        max_tokens=150,
    ),
    "voice": RouteSpec(
        platform="bailian",
        model=settings.QWEN_PLUS_MODEL,
        fallback=settings.QWEN_FLASH_MODEL,
        timeout=20,
        retry=2,
        max_tokens=300,
    ),
    "share_card": RouteSpec(
        platform="bailian",
        model=settings.QWEN_FLASH_MODEL,
        fallback=None,
        timeout=10,
        retry=1,
        max_tokens=80,
    ),
}


def get_route(scene: str) -> RouteSpec:
    """取场景对应的路由规则，业务代码只传 scene。"""
    if scene not in ROUTES:
        raise KeyError(f"Unknown AI scene: {scene}")
    return ROUTES[scene]
