"""B 端管理后台（Phase 0 占位）。

所有 /api/admin/* 接口除 /api/admin/login 外均需 admin_token 鉴权。
Phase 0 全部占位返回 50100。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import not_implemented
from app.models.schemas import BaseResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=BaseResponse)
async def admin_login() -> BaseResponse:
    """管理员登录。Phase 4 实现。"""
    return not_implemented()


@router.get("/overview", response_model=BaseResponse)
async def admin_overview() -> BaseResponse:
    """概览。Phase 4 实现。"""
    return not_implemented()


@router.get("/dish-heat", response_model=BaseResponse)
async def admin_dish_heat() -> BaseResponse:
    """菜品热度。Phase 4 实现。"""
    return not_implemented()


@router.get("/unsold", response_model=BaseResponse)
async def admin_unsold() -> BaseResponse:
    """滞销菜。Phase 4 实现。"""
    return not_implemented()


@router.get("/nutrition-stats", response_model=BaseResponse)
async def admin_nutrition_stats() -> BaseResponse:
    """营养统计。Phase 4 实现。"""
    return not_implemented()


@router.get("/canteen-stats", response_model=BaseResponse)
async def admin_canteen_stats() -> BaseResponse:
    """食堂统计。Phase 4 实现。"""
    return not_implemented()


@router.post("/menu", response_model=BaseResponse)
async def admin_publish_menu() -> BaseResponse:
    """菜单下发到 Nacos。Phase 4 实现。"""
    return not_implemented()


@router.get("/reviews", response_model=BaseResponse)
async def admin_list_reviews() -> BaseResponse:
    """评价列表。Phase 4 实现。"""
    return not_implemented()


@router.post("/reviews/{review_id}/reply", response_model=BaseResponse)
async def admin_reply_review(review_id: str) -> BaseResponse:
    """评价回复。Phase 4 实现。"""
    return not_implemented()


@router.delete("/reviews/{review_id}", response_model=BaseResponse)
async def admin_hide_review(review_id: str) -> BaseResponse:
    """隐藏不当评价。Phase 4 实现。"""
    return not_implemented()
