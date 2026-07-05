"""用户鉴权路由（注册/登录/退出/档案/头像/改密）。

阶段 2 重构：
- nickname 作为登录账号（替代 username）
- 新增 logout 接口
- user_id 改为 int

接口：
- POST /api/auth/register：注册（nickname + password + phone?）
- POST /api/auth/login：登录（nickname + password）
- POST /api/auth/logout：退出登录（需鉴权）
- GET /api/auth/me：查当前用户信息
- PUT /api/auth/profile：改昵称
- POST /api/auth/avatar：上传头像
- PUT /api/auth/password：改密码（需旧密码）

register/login 走中间件白名单不校验 token；其余接口路由内调 get_current_user_id。
"""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel, Field

from app.exceptions import BizError, success
from app.models.schemas import BaseResponse, ERR_PARAM_MISSING
from app.services import auth_service
from app.utils.auth import get_current_user_id

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    nickname: str = Field(description="登录账号，唯一必填，最多 50 字符")
    password: str = Field(description="密码，至少 6 位")
    phone: str | None = Field(default=None, description="手机号，选填")


class LoginRequest(BaseModel):
    nickname: str = Field(description="登录账号")
    password: str = Field(description="密码")


class ProfileUpdateRequest(BaseModel):
    nickname: str = Field(description="新昵称")


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(description="旧密码")
    new_password: str = Field(description="新密码，至少 6 位")


@router.post("/register", response_model=BaseResponse)
async def register(req: RegisterRequest) -> BaseResponse:
    """注册：创建用户 + 初始化身体目标，返回 token + user。"""
    data = await auth_service.register(req.nickname, req.password, req.phone)
    return success(data=data, message="注册成功")


@router.post("/login", response_model=BaseResponse)
async def login(req: LoginRequest) -> BaseResponse:
    """登录：校验密码，返回 token + user。"""
    data = await auth_service.login(req.nickname, req.password)
    return success(data=data, message="登录成功")


@router.post("/logout", response_model=BaseResponse)
async def logout(request: Request) -> BaseResponse:
    """退出登录：删 Redis 会话。需鉴权。"""
    user_id = get_current_user_id(request)
    await auth_service.logout(user_id)
    return success(message="已退出登录")


@router.get("/me", response_model=BaseResponse)
async def get_me(request: Request) -> BaseResponse:
    """查当前用户信息。"""
    user_id = get_current_user_id(request)
    data = await auth_service.get_profile(user_id)
    return success(data=data)


@router.put("/profile", response_model=BaseResponse)
async def update_profile(req: ProfileUpdateRequest, request: Request) -> BaseResponse:
    """改昵称。"""
    if not req.nickname.strip():
        raise BizError(code=ERR_PARAM_MISSING, message="昵称不能为空")
    user_id = get_current_user_id(request)
    user = await auth_service.update_nickname(user_id, req.nickname)
    return success(data={"user": user}, message="昵称已更新")


@router.post("/avatar", response_model=BaseResponse)
async def upload_avatar(
    request: Request, file: UploadFile = File(...)
) -> BaseResponse:
    """上传头像。FormData: file。"""
    user_id = get_current_user_id(request)
    avatar_url = await auth_service.upload_avatar(user_id, file)
    return success(data={"avatar_url": avatar_url}, message="头像已更新")


@router.put("/password", response_model=BaseResponse)
async def change_password(req: PasswordChangeRequest, request: Request) -> BaseResponse:
    """改密码（需旧密码验证）。"""
    user_id = get_current_user_id(request)
    await auth_service.change_password(user_id, req.old_password, req.new_password)
    return success(message="密码已更新")
