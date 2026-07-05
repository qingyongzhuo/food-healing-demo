"""食堂今日菜单（Phase 0 占位）。

GET /api/menu
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["menu"])


@router.get("/menu", response_model=BaseResponse)
async def get_menu() -> BaseResponse:
    """食堂今日菜单。Phase 3 实现。"""
    return not_implemented()
