"""FastAPI 应用入口。

- 注册路由（统一 /api 前缀，admin 额外 /api/admin 前缀）
- 挂载中间件（CORS / request_id / 请求日志）
- 启动/关闭事件（初始化日志、RabbitMQ 生产者、释放连接池）
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import close_all, ping_mongo, ping_pg, ping_redis
from app.db.rabbitmq_producer import close_producer, init_producer
from app.exceptions import register_exception_handlers
from app.middleware import setup_middlewares
from app.routes import (
    admin,
    ai_chat,
    auth,
    camera,
    chat,
    food,
    health,
    leaderboard,
    menu,
    mood,
    preferences,
    recognize,
    recommend,
    share_card,
    sport,
    user,
    voice_to_tray,
    weekly_report,
)
# 阶段 5 遗留：message_task / routes.message 模块尚未创建，注释避免阻塞启动
# from app.tasks.message_task import start_message_consumer, stop_message_consumer
from app.tasks.ai_task import (
    start_daily_summary_consumer,
    start_recognize_consumer,
    stop_daily_summary_consumer,
    stop_recognize_consumer,
)
from app.utils.logger import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动初始化、关闭释放资源。

    启动顺序：
    1. 日志（最先，后续日志可用）
    2. PG/MySQL/Redis（database.py 模块加载时已建连接，此处 ping 验证）
    3. RabbitMQ 生产者（可选，RABBITMQ_URL 为空跳过）

    关闭顺序（与启动相反）：
    1. RabbitMQ 生产者
    2. PG/MySQL/Redis 连接池
    """
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "app_starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.ENV,
    )

    # 启动连通性检查（graceful，失败不阻塞启动）
    pg_ok = await ping_pg()
    mongo_ok = await ping_mongo()
    redis_ok = await ping_redis()
    logger.info(
        "db_ping_on_startup",
        postgresql=pg_ok,
        mongo=mongo_ok,
        redis=redis_ok,
    )

    # RabbitMQ 生产者初始化（可选）
    mq_ok = await init_producer()
    logger.info("rabbitmq_producer_on_startup", ready=mq_ok)

    # 拍照识菜 MQ 消费者（阶段 6，可选；RABBITMQ_URL 为空跳过，camera_service 自动 fallback）
    recognize_consumer_ok = await start_recognize_consumer()
    logger.info("recognize_consumer_on_startup", ready=recognize_consumer_ok)

    # 每日 AI 营养简报 MQ 消费者（Phase 3，可选；RABBITMQ_URL 为空跳过）
    daily_consumer_ok = await start_daily_summary_consumer()
    logger.info("daily_summary_consumer_on_startup", ready=daily_consumer_ok)

    try:
        yield
    finally:
        # 关闭顺序：消费者 → 生产者 → 数据库
        await stop_daily_summary_consumer()
        await stop_recognize_consumer()
        await close_producer()
        await close_all()
        logger.info("app_stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="会成长、会记忆、会陪伴的校园饮食伙伴 — 后端 API",
    lifespan=lifespan,
)


# ===== 中间件（顺序重要：request_id → auth → CORS → 请求日志）=====
setup_middlewares(app)

# ===== 异常处理 =====
register_exception_handlers(app)

# ===== 静态资源（头像等本地文件）=====
os.makedirs(settings.AVATAR_UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="uploads"), name="static")

# ===== 路由注册（统一 /api 前缀）=====
app.include_router(auth.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(recognize.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(recommend.router, prefix="/api")
app.include_router(weekly_report.router, prefix="/api")
app.include_router(preferences.router, prefix="/api")
app.include_router(menu.router, prefix="/api")
app.include_router(leaderboard.router, prefix="/api")
app.include_router(mood.router, prefix="/api")
app.include_router(sport.router, prefix="/api")
app.include_router(voice_to_tray.router, prefix="/api")
app.include_router(share_card.router, prefix="/api")
app.include_router(food.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(camera.router, prefix="/api")
app.include_router(ai_chat.router, prefix="/api")
# admin 路由本身带 /admin 前缀，整体路径 /api/admin/*
app.include_router(admin.router, prefix="/api")


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """根路径返回应用基本信息。"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
