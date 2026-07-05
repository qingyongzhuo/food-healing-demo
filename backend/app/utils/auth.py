"""鉴权工具：JWT 签发/校验 + bcrypt 密码哈希 + Redis 会话 + 依赖注入。

阶段 2 重构：
- user_id 从 str 改为 int（BIGINT）
- Redis 会话存储：登录写、退出删、改密删、中间件校验 token 一致
- Redis key 格式：user:token:{user_id}，TTL 7 天

密码：bcrypt（salt 自动生成，hash 存 VARCHAR(255)）
token：JWT HS256，payload 含 sub=user_id(str) / exp / iat
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import Request

from app.config import settings
from app.database import redis_client
from app.exceptions import BizError
from app.models.schemas import ERR_TOKEN_INVALID, ERR_UNAUTHORIZED


# ===== Redis 会话 Key =====
SESSION_KEY_PREFIX = "user:token:"
SESSION_TTL_SECONDS = settings.JWT_EXPIRE_HOURS * 3600
"""会话 TTL，与 JWT 过期时间一致（7 天）。"""


def _session_key(user_id: int) -> str:
    """构造 Redis 会话 key。"""
    return f"{SESSION_KEY_PREFIX}{user_id}"


async def set_session(user_id: int, token: str) -> None:
    """登录成功后写入 Redis 会话。失败 graceful 不阻塞登录。"""
    try:
        await redis_client.set(_session_key(user_id), token, ex=SESSION_TTL_SECONDS)
    except Exception:
        pass


async def remove_session(user_id: int) -> None:
    """退出登录删除 Redis 会话。失败 graceful。"""
    try:
        await redis_client.delete(_session_key(user_id))
    except Exception:
        pass


async def get_session(user_id: int) -> str | None:
    """查 Redis 会话（弱校验模式中间件不调用，仅 logout/调试用）。"""
    try:
        return await redis_client.get(_session_key(user_id))
    except Exception:
        return None


async def validate_session(user_id: int, token: str) -> bool:
    """校验 Redis 会话与 token 是否一致。Redis 异常时 fail-open 返回 True 以保可用。"""
    try:
        stored = await redis_client.get(_session_key(user_id))
    except Exception:
        return True
    return stored == token


# ===== 密码哈希 =====
def hash_password(password: str) -> str:
    """bcrypt 哈希密码，返回 str（可存 VARCHAR(255)）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码与哈希是否匹配。空哈希直接返回 False。"""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ===== JWT =====
def create_token(user_id: int) -> str:
    """签发 JWT。payload: sub=str(user_id), exp, iat。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.JWT_EXPIRE_HOURS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> int | None:
    """解码 JWT，返回 user_id(int) 或 None（过期/无效均返回 None）。"""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.JWT_SECRET, algorithms=["HS256"]
        )
        sub = payload.get("sub")
        return int(sub) if sub else None
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, TypeError):
        return None


# ===== 依赖注入 =====
def _extract_bearer_token(request: Request) -> str | None:
    """从 Authorization: Bearer xxx 头取 token。"""
    auth_header = request.headers.get("Authorization") or request.headers.get(
        "authorization"
    )
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def get_current_user_id(request: Request) -> int:
    """FastAPI 依赖注入：从 Authorization 头取 token 解码返回 user_id(int)。

    失败抛 BizError(401)。中间件已校验过会注入 request.state.user_id，
    此函数优先用中间件结果，避免重复解码。

    弱校验模式：不查 Redis，只校验 JWT 签名 + 过期。
    logout 删 Redis 会话仅用于踢下线（需强校验场景另调 get_session）。
    """
    cached = getattr(request.state, "user_id", None)
    if cached:
        return int(cached)
    token = _extract_bearer_token(request)
    if not token:
        raise BizError(code=ERR_UNAUTHORIZED, message="未登录", http_status=401)
    user_id = decode_token(token)
    if user_id is None:
        raise BizError(
            code=ERR_TOKEN_INVALID, message="登录已过期，请重新登录", http_status=401
        )
    return user_id
