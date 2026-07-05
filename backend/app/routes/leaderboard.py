"""同学搭配匿名榜（Phase 0 占位）。

GET /api/leaderboard
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard", response_model=BaseResponse)
async def get_leaderboard() -> BaseResponse:
    """同学搭配匿名榜。Phase 3 实现。"""
    return not_implemented()
