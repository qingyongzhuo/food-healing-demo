"""饮食周报（Phase 0 占位）。

GET /api/weekly-report
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["report"])


@router.get("/weekly-report", response_model=BaseResponse)
async def weekly_report() -> BaseResponse:
    """饮食周报。Phase 2 实现。"""
    return not_implemented()
