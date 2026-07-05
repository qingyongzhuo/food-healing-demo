"""语音转菜盘（Phase 0 占位）。

POST /api/voice-to-tray
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["voice"])


@router.post("/voice-to-tray", response_model=BaseResponse)
async def voice_to_tray() -> BaseResponse:
    """语音转菜盘。Phase 2 实现。"""
    return not_implemented()
