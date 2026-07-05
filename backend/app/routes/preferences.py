"""过敏/忌口/人设管理（Phase 0 占位）。

POST /api/preferences
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(tags=["preferences"])


@router.post("/preferences", response_model=BaseResponse)
async def update_preferences() -> BaseResponse:
    """过敏/忌口/人设管理。Phase 2 实现。"""
    return not_implemented()
