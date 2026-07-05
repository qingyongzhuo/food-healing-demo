"""鉴权业务服务层。

阶段 2 重构：
- 数据访问层从 MySQL 迁到 PostgreSQL
- user_id 从 str 改为 int（BIGINT）
- nickname 作为登录账号（唯一必填）
- 新增 logout：删 Redis 会话
- 新增 phone 字段（可选）

路由调 service，service 操作 ORM + 文件系统 + Redis 会话。
- register / login：创建/校验用户，签发 token + 写 Redis 会话
- logout：删 Redis 会话
- get_profile：查 User
- update_nickname / change_password：更新用户信息
- upload_avatar：Pillow 压缩 + 本地保存 + 更新 avatar_url
"""

from __future__ import annotations

import io
import os
import time
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import PgSessionLocal
from app.exceptions import BizError
from app.models.pg_orm import User, UserBodyTarget
from app.models.schemas import (
    ERR_PARAM_FORMAT,
    ERR_PASSWORD_WRONG,
    ERR_USER_EXISTS,
    ERR_USER_NOT_FOUND,
)
from app.utils.auth import (
    create_token,
    hash_password,
    remove_session,
    set_session,
    verify_password,
)
from app.utils.logger import logger

AVATAR_MAX_SIZE = 5 * 1024 * 1024  # 5MB
AVATAR_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
AVATAR_TARGET_SIZE = (256, 256)  # 头像压缩目标尺寸


def _user_to_dict(user: User) -> dict:
    """User ORM 转 dict（不暴露 password_hash）。"""
    return {
        "user_id": user.id,
        "nickname": user.nickname,
        "phone": user.phone or "",
        "avatar_url": user.avatar_url or "",
        "theme": user.theme or "light",
        "status": user.status,
        "create_time": user.create_time.isoformat() if user.create_time else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


async def register(nickname: str, password: str, phone: str | None = None) -> dict:
    """注册：创建 User + 初始化 UserBodyTarget，签发 token + 写 Redis 会话。

    Args:
        nickname: 登录账号（唯一必填）
        password: 密码，至少 6 位
        phone: 手机号（可选）

    Returns:
        {"token": str, "user": dict}
    """
    nickname = (nickname or "").strip()
    password = password or ""
    phone = (phone or "").strip() or None

    if not nickname:
        raise BizError(code=ERR_PARAM_FORMAT, message="昵称不能为空")
    if len(nickname) > 50:
        raise BizError(code=ERR_PARAM_FORMAT, message="昵称过长（最多 50 字符）")
    if len(password) < 6:
        raise BizError(code=ERR_PARAM_FORMAT, message="密码至少 6 位")
    if phone and len(phone) > 20:
        raise BizError(code=ERR_PARAM_FORMAT, message="手机号过长")

    password_hash = hash_password(password)

    try:
        async with PgSessionLocal() as session:
            # 查重（nickname 唯一约束）
            stmt = select(User).where(User.nickname == nickname)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                raise BizError(code=ERR_USER_EXISTS, message="昵称已被占用")

            user = User(
                nickname=nickname,
                password_hash=password_hash,
                phone=phone,
            )
            session.add(user)
            await session.flush()  # 拿到自增 id

            # 初始化默认身体目标
            target = UserBodyTarget(user_id=user.id)
            session.add(target)
            await session.commit()
            await session.refresh(user)
            logger.info("user_registered", user_id=user.id, nickname=nickname)
    except BizError:
        raise
    except IntegrityError as exc:
        # 并发场景下 nickname / phone 唯一约束兜底
        raise BizError(code=ERR_USER_EXISTS, message="昵称或手机号已存在") from exc

    token = create_token(user.id)
    await set_session(user.id, token)
    return {"token": token, "user": _user_to_dict(user)}


async def login(nickname: str, password: str) -> dict:
    """登录：校验密码，更新 last_login，签发 token + 写 Redis 会话。

    Args:
        nickname: 登录账号
        password: 密码

    Returns:
        {"token": str, "user": dict}
    """
    nickname = (nickname or "").strip()
    password = password or ""
    if not nickname or not password:
        raise BizError(code=ERR_PARAM_FORMAT, message="昵称和密码不能为空")

    async with PgSessionLocal() as session:
        stmt = select(User).where(User.nickname == nickname)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise BizError(code=ERR_USER_NOT_FOUND, message="用户不存在")
        if user.status != 1:
            raise BizError(code=ERR_USER_NOT_FOUND, message="账号已被禁用")
        if not verify_password(password, user.password_hash or ""):
            raise BizError(code=ERR_PASSWORD_WRONG, message="密码错误")

        # 更新 last_login（PG 列为 TIMESTAMP WITHOUT TIME ZONE，需 naive datetime）
        user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        await session.refresh(user)

    token = create_token(user.id)
    await set_session(user.id, token)
    logger.info("user_login", user_id=user.id, nickname=nickname)
    return {"token": token, "user": _user_to_dict(user)}


async def logout(user_id: int) -> None:
    """退出登录：删 Redis 会话。"""
    await remove_session(user_id)
    logger.info("user_logout", user_id=user_id)


async def get_profile(user_id: int) -> dict:
    """查 User，返回 {user}。"""
    async with PgSessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise BizError(code=ERR_USER_NOT_FOUND, message="用户不存在")
    return {"user": _user_to_dict(user)}


async def update_nickname(user_id: int, nickname: str) -> dict:
    """更新昵称，返回更新后的 user。"""
    nickname = (nickname or "").strip()
    if not nickname:
        raise BizError(code=ERR_PARAM_FORMAT, message="昵称不能为空")
    if len(nickname) > 50:
        raise BizError(code=ERR_PARAM_FORMAT, message="昵称过长（最多 50 字符）")

    async with PgSessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise BizError(code=ERR_USER_NOT_FOUND, message="用户不存在")

        # 查重（排除自己）
        stmt = select(User).where(User.nickname == nickname, User.id != user_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            raise BizError(code=ERR_USER_EXISTS, message="昵称已被占用")

        user.nickname = nickname
        try:
            await session.commit()
        except IntegrityError as exc:
            raise BizError(code=ERR_USER_EXISTS, message="昵称已被占用") from exc
        await session.refresh(user)
        logger.info("user_nickname_updated", user_id=user_id)
    return _user_to_dict(user)


async def upload_avatar(user_id: int, file: UploadFile) -> str:
    """上传头像：校验 → Pillow 压缩到 256x256 → 本地保存 → 更新 avatar_url。

    返回 avatar_url（相对路径 /static/avatars/xxx.jpg）。
    """
    if not file.filename:
        raise BizError(code=ERR_PARAM_FORMAT, message="请上传图片文件")
    if file.content_type and file.content_type not in AVATAR_ALLOWED_TYPES:
        raise BizError(code=ERR_PARAM_FORMAT, message="仅支持 jpg/png/webp 格式")

    image_bytes = await file.read()
    if len(image_bytes) > AVATAR_MAX_SIZE:
        raise BizError(
            code=ERR_PARAM_FORMAT,
            message=f"图片不能超过 {AVATAR_MAX_SIZE // (1024 * 1024)}MB",
        )
    if not image_bytes:
        raise BizError(code=ERR_PARAM_FORMAT, message="图片内容为空")

    try:
        from PIL import Image
    except ImportError as exc:
        raise BizError(code=ERR_PARAM_FORMAT, message="图片处理库未安装") from exc

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail(AVATAR_TARGET_SIZE)
    except Exception as exc:
        logger.warning("avatar_decode_failed", user_id=user_id, error=str(exc))
        raise BizError(code=ERR_PARAM_FORMAT, message="图片解析失败") from exc

    upload_dir = settings.AVATAR_UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{user_id}_{int(time.time())}.jpg"
    filepath = os.path.join(upload_dir, filename)
    img.save(filepath, "JPEG", quality=85)

    avatar_url = f"/static/avatars/{filename}"

    async with PgSessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise BizError(code=ERR_USER_NOT_FOUND, message="用户不存在")
        # 删除旧头像文件（失败不阻塞）
        if user.avatar_url and user.avatar_url.startswith("/static/avatars/"):
            old_filename = user.avatar_url.rsplit("/", 1)[-1]
            old_path = os.path.join(settings.AVATAR_UPLOAD_DIR, old_filename)
            try:
                if os.path.exists(old_path):
                    os.remove(old_path)
            except OSError:
                pass
        user.avatar_url = avatar_url
        await session.commit()
        logger.info("user_avatar_updated", user_id=user_id)

    return avatar_url


async def change_password(
    user_id: int, old_password: str, new_password: str
) -> None:
    """改密码：校验旧密码 → 更新 password_hash。"""
    if not old_password or not new_password:
        raise BizError(code=ERR_PARAM_FORMAT, message="旧密码和新密码不能为空")
    if len(new_password) < 6:
        raise BizError(code=ERR_PARAM_FORMAT, message="新密码至少 6 位")
    if old_password == new_password:
        raise BizError(code=ERR_PARAM_FORMAT, message="新密码不能与旧密码相同")

    async with PgSessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise BizError(code=ERR_USER_NOT_FOUND, message="用户不存在")
        if not verify_password(old_password, user.password_hash or ""):
            raise BizError(code=ERR_PASSWORD_WRONG, message="旧密码错误")
        user.password_hash = hash_password(new_password)
        await session.commit()
        logger.info("user_password_changed", user_id=user_id)

    await remove_session(user_id)
