"""健康检查 + 健康档案路由。

- GET /health：健康检查（完整实现）
- GET /api/health/profile：健康档案查询（占位）
- POST /api/health/profile：健康档案更新（占位）
"""

from __future__ import annotations

import asyncio
import socket
import time
from typing import Any

from fastapi import APIRouter

from app.config import settings
from app.database import ping_mongo, ping_pg, ping_redis
from app.exceptions import not_implemented
from app.models.schemas import BaseResponse, HealthCheckResponse
from app.utils.logger import logger

router = APIRouter(tags=["health"])


# ===================================================================
# 健康检查（完整实现）
# ===================================================================

async def _ping_with_latency(name: str, coro: Any) -> dict[str, str]:
    """执行单个组件 ping，返回 {status, latency_ms}。失败 graceful 返回 fail。"""
    start = time.perf_counter()
    try:
        ok = await coro
        latency_ms = f"{(time.perf_counter() - start) * 1000:.0f}ms"
        status = "ok" if ok else "fail"
    except Exception as exc:
        latency_ms = f"{(time.perf_counter() - start) * 1000:.0f}ms"
        status = "fail"
        logger.warning("Health check component failed", component=name, error=str(exc))
    return {"status": status, "latency_ms": latency_ms}


async def _ping_rabbitmq() -> bool:
    """RabbitMQ 连通性检查。

    RABBITMQ_URL 为空时（Phase 1 暂不用 MQ）直接返回 False 跳过，
    避免对未部署的服务发起无意义的连接探测。
    """
    if not settings.RABBITMQ_URL:
        return False  # 未配置，跳过
    try:
        import aio_pika
    except ImportError:
        return False
    try:
        connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL, timeout=3
        )
        await connection.close()
        return True
    except Exception as exc:
        logger.warning("RabbitMQ ping failed", error=str(exc))
        return False


async def _ping_nacos() -> bool:
    """Nacos 连通性检查。

    用户未部署 Nacos 时（NACOS_ENABLED=False），直接返回 False 跳过，
    避免对未部署的服务发起无意义的 TCP 探测。
    """
    if not getattr(settings, "NACOS_ENABLED", False):
        return False  # 用户未部署 Nacos，跳过
    host, _, port = settings.NACOS_SERVER.partition(":")
    try:
        loop = asyncio.get_running_loop()

        def _probe() -> bool:
            try:
                with socket.create_connection((host, int(port)), timeout=3):
                    return True
            except OSError:
                return False

        return await loop.run_in_executor(None, _probe)
    except Exception as exc:
        logger.warning("Nacos ping failed", error=str(exc))
        return False


async def _ping_oss() -> bool:
    """OSS/MinIO 连通性检查（真连：用 oss2 列 bucket）。

    旧实现仅做 DNS 解析，AK/SK 是占位符也报 ok（假绿）。
    改为用 oss2.Auth + Service 真实调用 list buckets 接口，
    AK/SK 错或 endpoint 不通都会返回 False。
    """
    try:
        import oss2

        loop = asyncio.get_running_loop()

        def _probe() -> bool:
            try:
                auth = oss2.Auth(
                    settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET
                )
                svc = oss2.Service(
                    auth, settings.OSS_ENDPOINT, connect_timeout=3
                )
                list(oss2.BucketIterator(svc))
                return True
            except Exception:
                return False

        return await loop.run_in_executor(None, _probe)
    except Exception as exc:
        logger.warning("OSS ping failed", error=str(exc))
        return False


@router.get("/health", response_model=BaseResponse)
async def health_check() -> BaseResponse:
    """健康检查。

    Returns:
        BaseResponse：统一响应契约 {code, message, data}，
        data 为 HealthCheckResponse（整体 status + 各组件连通性）。
        组件不通时 graceful 降级，不抛错。
    """
    components_raw = await asyncio.gather(
        _ping_with_latency("postgresql", ping_pg()),
        _ping_with_latency("redis", ping_redis()),
        _ping_with_latency("mongo", ping_mongo()),
        _ping_with_latency("rabbitmq", _ping_rabbitmq()),
        _ping_with_latency("nacos", _ping_nacos()),
        _ping_with_latency("oss", _ping_oss()),
    )
    names = ["postgresql", "redis", "mongo", "rabbitmq", "nacos", "oss"]
    components = {name: result for name, result in zip(names, components_raw)}

    all_ok = all(c["status"] == "ok" for c in components.values())
    any_ok = any(c["status"] == "ok" for c in components.values())
    overall = "ok" if all_ok else ("degraded" if any_ok else "down")

    health_data = HealthCheckResponse(
        status=overall,
        version=settings.APP_VERSION,
        components=components,
    )
    return BaseResponse(code=0, message="ok", data=health_data)


# ===================================================================
# 健康档案（Phase 0 占位）
# ===================================================================

@router.get("/health/profile", response_model=BaseResponse)
async def get_health_profile() -> BaseResponse:
    """查询健康档案。Phase 4 实现。"""
    return not_implemented()


@router.post("/health/profile", response_model=BaseResponse)
async def update_health_profile() -> BaseResponse:
    """更新健康档案。Phase 4 实现。"""
    return not_implemented()
