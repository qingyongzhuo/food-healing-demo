"""/health 接口测试。

用 httpx AsyncClient + ASGITransport 直接走 ASGI，无需起端口。
通过 asgi-lifespan.LifespanManager 触发 startup/shutdown。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    """/health 返回 200 状态码。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape(client: AsyncClient) -> None:
    """/health 返回统一 {code, message, data}，data 含 status/version/components。"""
    resp = await client.get("/api/health")
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    data = body["data"]
    assert "status" in data
    assert "version" in data
    assert "components" in data
    assert data["status"] in ("ok", "degraded", "down")


@pytest.mark.asyncio
async def test_health_components_all_present(client: AsyncClient) -> None:
    """components 包含 6 个组件：mysql/postgresql/redis/rabbitmq/nacos/oss。"""
    resp = await client.get("/api/health")
    components = resp.json()["data"]["components"]
    expected = {"mysql", "postgresql", "redis", "rabbitmq", "nacos", "oss"}
    assert set(components.keys()) == expected
    for name, info in components.items():
        assert info["status"] in ("ok", "fail"), f"{name} status invalid"
        assert "latency_ms" in info, f"{name} missing latency_ms"


@pytest.mark.asyncio
async def test_health_graceful_degradation(client: AsyncClient) -> None:
    """服务器组件可能不通，但 /health 不应报错，至少返回 200 + degraded/down。"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    # 测试环境无真实服务器，预期 degraded 或 down，不应抛 500
    assert body["data"]["status"] in ("ok", "degraded", "down")
