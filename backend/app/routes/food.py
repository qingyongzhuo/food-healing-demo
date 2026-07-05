"""食材库 + 每日饮食记录路由（Phase 4）。

全部接口走中间件鉴权（白名单外的 /api/* 默认校验 token），
路由内通过 get_current_user_id(request) 取当前用户。

接口分组：
- 食材相关 /food/*
  - GET    /food/list             食材列表（搜索 + 分类筛选）
  - POST   /food/custom           新增自定义食材
  - PUT    /food/custom/{id}       编辑自定义食材
  - DELETE /food/custom/{id}       删除自定义食材
- 餐食相关 /diet/*
  - POST   /diet/add               添加食材到当前日期某一餐（支持多选）
  - PUT    /diet/item/{item_id}    修改餐食重量
  - DELETE /diet/item/{item_id}    删除单条餐食
  - GET    /diet/today             获取今日全部饮食 + 总营养（首页核心接口）
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.exceptions import success
from app.models.schemas import BaseResponse
from app.schemas.food import (
    CustomFoodCreateRequest,
    CustomFoodUpdateRequest,
    DietAddRequest,
    DietItemUpdateRequest,
)
from app.services import food_service
from app.utils.auth import get_current_user_id

router = APIRouter(tags=["food"])


# ============================================================
# 食材相关
# ============================================================
@router.get("/food/list", response_model=BaseResponse)
async def list_foods(
    request: Request,
    keyword: str | None = Query(default=None, max_length=64),
    category: str | None = Query(default=None, max_length=16),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BaseResponse:
    """食材列表（标准 + 当前用户自定义）。

    命中 Redis 热门搜索缓存时响应 from_cache=True。
    """
    user_id = get_current_user_id(request)
    data = await food_service.list_foods(
        user_id=user_id,
        keyword=keyword,
        category=category,
        page=page,
        page_size=page_size,
    )
    return success(data=data, message="ok")


@router.post("/food/custom", response_model=BaseResponse)
async def create_custom_food(
    req: CustomFoodCreateRequest,
    request: Request,
) -> BaseResponse:
    """新增自定义食材。归属当前登录用户。"""
    user_id = get_current_user_id(request)
    data = await food_service.create_custom_food(
        user_id=user_id,
        name=req.name,
        category=req.category,
        kcal_per_100g=req.kcal_per_100g,
        protein_per_100g=req.protein_per_100g,
        carb_per_100g=req.carb_per_100g,
        fat_per_100g=req.fat_per_100g,
    )
    return success(data=data, message="自定义食材已添加")


@router.put("/food/custom/{custom_food_id}", response_model=BaseResponse)
async def update_custom_food(
    custom_food_id: int,
    req: CustomFoodUpdateRequest,
    request: Request,
) -> BaseResponse:
    """编辑自定义食材。仅 owner 可改。"""
    user_id = get_current_user_id(request)
    # 只取非 None 字段做部分更新
    updates = req.model_dump(exclude_none=True)
    data = await food_service.update_custom_food(
        user_id=user_id,
        custom_food_id=custom_food_id,
        updates=updates,
    )
    return success(data=data, message="自定义食材已更新")


@router.delete("/food/custom/{custom_food_id}", response_model=BaseResponse)
async def delete_custom_food(
    custom_food_id: int,
    request: Request,
) -> BaseResponse:
    """删除自定义食材。仅 owner 可删。"""
    user_id = get_current_user_id(request)
    await food_service.delete_custom_food(
        user_id=user_id, custom_food_id=custom_food_id
    )
    return success(data={"deleted_id": custom_food_id}, message="自定义食材已删除")


# ============================================================
# 餐食相关
# ============================================================
@router.post("/diet/add", response_model=BaseResponse)
async def add_diet_items(
    req: DietAddRequest,
    request: Request,
) -> BaseResponse:
    """向当日某一餐添加食材（支持多选）。

    请求体示例：
    {
      "meal_type": "lunch",
      "items": [
        {"food_id": 1, "grams": 200},
        {"custom_food_id": 5, "grams": 150}
      ]
    }
    """
    user_id = get_current_user_id(request)
    items_payload = [item.model_dump() for item in req.items]
    data = await food_service.add_diet_items(
        user_id=user_id,
        meal_type=req.meal_type,
        items=items_payload,
    )
    return success(data=data, message=f"已添加 {len(data.get('added', []))} 条记录")


@router.put("/diet/item/{item_id}", response_model=BaseResponse)
async def update_diet_item(
    item_id: int,
    req: DietItemUpdateRequest,
    request: Request,
) -> BaseResponse:
    """修改单条餐食条目重量，自动重算该条营养 + 当日汇总。"""
    user_id = get_current_user_id(request)
    data = await food_service.update_meal_item_grams(
        user_id=user_id,
        item_id=item_id,
        grams=req.grams,
    )
    return success(data=data, message="餐食记录已更新")


@router.delete("/diet/item/{item_id}", response_model=BaseResponse)
async def delete_diet_item(
    item_id: int,
    request: Request,
) -> BaseResponse:
    """删除单条餐食条目，自动重算当日汇总。"""
    user_id = get_current_user_id(request)
    data = await food_service.delete_meal_item(
        user_id=user_id, item_id=item_id
    )
    return success(data=data, message="餐食记录已删除")


@router.get("/diet/today", response_model=BaseResponse)
async def get_today_diet(request: Request) -> BaseResponse:
    """获取今日全部饮食 + 总营养数据。

    首页核心接口，返回结构：
    {
      "record_id": 123,
      "record_date": "2026-07-04",
      "summary": {"kcal": 800, "protein": 40, "carb": 100, "fat": 25},
      "groups": [
        {"meal_type": "breakfast", "items": [...], "subtotal_kcal": 400},
        {"meal_type": "lunch", "items": [...], "subtotal_kcal": 400},
        {"meal_type": "dinner", "items": [], "subtotal_kcal": 0},
        {"meal_type": "snack", "items": [], "subtotal_kcal": 0}
      ]
    }
    """
    user_id = get_current_user_id(request)
    data = await food_service.get_today_diet(user_id=user_id)
    return success(data=data, message="ok")
