"""分享卡片（Phase 0 占位）。

POST /api/share-card
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["share"])


@router.post("/share-card", response_model=BaseResponse)
async def create_share_card() -> BaseResponse:
    """分享卡片。Phase 2 实现。"""
    return not_implemented()
