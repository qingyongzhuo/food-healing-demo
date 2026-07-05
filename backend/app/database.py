"""数据库连接。

- PostgreSQL async engine（SQLAlchemy + asyncpg）
- Redis async client（redis.asyncio）
- MongoDB async client（motor）

阶段 2 重构：废弃 MySQL，用户表迁到 PG，新增 MongoDB。
连接失败时 graceful 降级（不阻塞应用启动）。
所有 ping 均带 5s 超时，避免被防火墙挡住 SYN 时阻塞 ~60s。
"""

from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.utils.logger import logger


PING_TIMEOUT: float = 5.0
"""单个组件 ping 超时秒数，避免被防火墙挡 SYN 时阻塞过久。"""


# ===== PostgreSQL =====
pg_engine: AsyncEngine = create_async_engine(
    settings.PG_DSN,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=3600,
)
"""PostgreSQL 异步 engine。"""

PgSessionLocal = async_sessionmaker(
    pg_engine, expire_on_commit=False, class_=AsyncSession
)
"""PostgreSQL 异步 session 工厂。"""


async def get_pg_session() -> Any:
    """PostgreSQL session 依赖注入。"""
    async with PgSessionLocal() as session:
        yield session


# ===== Redis =====
redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=50,
    decode_responses=True,
)
"""Redis 连接池。"""

redis_client: aioredis.Redis = aioredis.Redis(connection_pool=redis_pool)
"""Redis 异步客户端。所有 key 必须带 food_healing: 前缀 + TTL。"""


# ===== MongoDB（可选，MONGO_URL 空则跳过）=====
mongo_client = None
mongo_db = None

if settings.MONGO_URL:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        mongo_client = AsyncIOMotorClient(settings.MONGO_URL, serverSelectionTimeoutMS=5000)
        mongo_db = mongo_client[settings.MONGO_DB]
        """MongoDB 异步数据库实例（ai_chat_history / camera_recognize_log / ai_daily_report）。"""
    except ImportError:
        logger.warning("motor not installed, MongoDB disabled")


# ===== 连通性 ping（均带 PING_TIMEOUT 超时）=====
async def ping_pg() -> bool:
    """检查 PostgreSQL 连通性，失败/超时 graceful 返回 False。"""
    try:
        async with asyncio.timeout(PING_TIMEOUT):
            async with pg_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("PostgreSQL ping failed", error=str(exc))
        return False


async def ping_redis() -> bool:
    """检查 Redis 连通性，失败/超时 graceful 返回 False。"""
    try:
        async with asyncio.timeout(PING_TIMEOUT):
            return bool(await redis_client.ping())
    except Exception as exc:
        logger.warning("Redis ping failed", error=str(exc))
        return False


async def ping_mongo() -> bool:
    """检查 MongoDB 连通性，未配置或失败返回 False。"""
    if mongo_client is None:
        return False
    try:
        async with asyncio.timeout(PING_TIMEOUT):
            await mongo_client.admin.command("ping")
        return True
    except Exception as exc:
        logger.warning("MongoDB ping failed", error=str(exc))
        return False


async def close_all() -> None:
    """应用关闭时释放所有连接池。"""
    await redis_pool.aclose()
    await pg_engine.dispose()
    if mongo_client is not None:
        mongo_client.close()
    logger.info("All database connections closed")
