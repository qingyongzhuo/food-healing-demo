"""pytest 全局 fixtures。"""

from __future__ import annotations

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """异步 HTTP 客户端 fixture。

    用 asgi-lifespan.LifespanManager 包 app，触发 startup/shutdown 事件，
    让 close_all() 等清理逻辑能正常执行，避免 'coroutine was never awaited'
    与 'Event loop is closed' 警告。
    """
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
