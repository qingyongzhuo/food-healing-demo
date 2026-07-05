"""情绪日记（Phase 0 占位）。

POST /api/mood
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["mood"])


@router.post("/mood", response_model=BaseResponse)
async def create_mood() -> BaseResponse:
    """情绪日记。Phase 3 实现。"""
    return not_implemented()
