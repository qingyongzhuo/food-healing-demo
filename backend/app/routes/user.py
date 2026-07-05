"""用户中心路由（Phase 3）。

接口全部需要鉴权依赖（中间件已校验，路由内调 get_current_user_id 取 user_id）。

- GET    /api/user/profile              获取个人全部信息
- PUT    /api/user/profile              编辑基础资料（昵称、头像、手机号、主题）
- PUT    /api/user/body                 调整身高体重（含性别、年龄）
- PUT    /api/user/target               修改每日营养目标
- GET    /api/user/collect              获取收藏食材列表（含详情）
- POST   /api/user/collect/{food_id}    收藏 / 取消收藏食材（toggle）
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.exceptions import success
from app.models.schemas import BaseResponse
from app.schemas.user import (
    BodyUpdateRequest,
    ProfileUpdateRequest,
    TargetUpdateRequest,
)
from app.services import user_service
from app.utils.auth import get_current_user_id

router = APIRouter(prefix="/user", tags=["user"])


class ToggleCollectResponse(BaseModel):
    """收藏 toggle 操作响应。"""

    collected: bool
    food_id: str


@router.get("/profile", response_model=BaseResponse)
async def get_profile(request: Request) -> BaseResponse:
    """获取个人全部信息（user + body_target + collect_food_ids）。"""
    user_id = get_current_user_id(request)
    data = await user_service.get_full_profile(user_id)
    return success(data=data)


@router.put("/profile", response_model=BaseResponse)
async def update_profile(
    req: ProfileUpdateRequest, request: Request
) -> BaseResponse:
    """编辑基础资料（昵称、头像、手机号、主题）。

    部分更新：仅传需要修改的字段。theme 字段归属个人中心设置，存 user_body_target 表。
    """
    user_id = get_current_user_id(request)
    data = await user_service.update_profile(
        user_id=user_id,
        nickname=req.nickname,
        avatar_url=req.avatar_url,
        phone=req.phone,
        theme=req.theme,
    )
    return success(data=data, message="资料已更新")


@router.put("/body", response_model=BaseResponse)
async def update_body(
    req: BodyUpdateRequest, request: Request
) -> BaseResponse:
    """调整身体数据（身高、体重、性别、年龄）。

    部分更新：仅传需要修改的字段。upsert user_body_target 表。
    """
    user_id = get_current_user_id(request)
    data = await user_service.update_body(
        user_id=user_id,
        height_cm=req.height_cm,
        weight_kg=req.weight_kg,
        gender=req.gender,
        age=req.age,
    )
    return success(data=data, message="身体数据已更新")


@router.put("/target", response_model=BaseResponse)
async def update_target(
    req: TargetUpdateRequest, request: Request
) -> BaseResponse:
    """修改每日营养目标（每日热量、蛋白、碳水、脂肪、目标类型）。"""
    user_id = get_current_user_id(request)
    data = await user_service.update_target(
        user_id=user_id,
        daily_kcal=req.daily_kcal,
        protein_g=req.protein_g,
        carb_g=req.carb_g,
        fat_g=req.fat_g,
        target_type=req.target_type,
    )
    return success(data=data, message="营养目标已更新")


@router.get("/collect", response_model=BaseResponse)
async def list_collect(request: Request) -> BaseResponse:
    """获取收藏食材列表（含食物详情）。"""
    user_id = get_current_user_id(request)
    data = await user_service.list_collect_foods(user_id)
    return success(data={"list": data, "total": len(data)})


@router.post("/collect/{food_id}", response_model=BaseResponse)
async def toggle_collect(food_id: str, request: Request) -> BaseResponse:
    """收藏 / 取消收藏食材（toggle 语义）。

    - 已收藏 → 取消
    - 未收藏 → 收藏
    返回 { collected: bool, food_id: str }。
    """
    user_id = get_current_user_id(request)
    data = await user_service.toggle_collect_food(user_id, food_id)
    return success(
        data=data,
        message="已收藏" if data.get("collected") else "已取消收藏",
    )
