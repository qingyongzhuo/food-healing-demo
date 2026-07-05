"""运动记录（Phase 0 占位）。

- GET /api/sport/records：运动记录列表
- POST /api/sport/records：提交运动记录
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["sport"])


@router.get("/sport/records", response_model=BaseResponse)
async def list_sport_records() -> BaseResponse:
    """运动记录列表。Phase 4 实现。"""
    return not_implemented()


@router.post("/sport/records", response_model=BaseResponse)
async def create_sport_record() -> BaseResponse:
    """提交运动记录。Phase 4 实现。"""
    return not_implemented()
