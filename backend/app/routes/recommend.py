"""智能推荐补菜（Phase 0 占位）。

GET /api/recommend
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["recommend"])


@router.get("/recommend", response_model=BaseResponse)
async def recommend() -> BaseResponse:
    """智能推荐补菜。Phase 2 实现。"""
    return not_implemented()
