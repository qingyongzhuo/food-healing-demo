"""APScheduler 定时任务独立进程启动入口（Phase 8）。

部署时与 web / consumer 分进程运行：
    uv run python -m app.tasks.run_scheduler

注册的定时任务：
1. 每日凌晨 00:30 触发「生成全部用户 AI 营养简报」
   - 查 PG user 表拿全部 user_id
   - 逐个调 ai_service.trigger_daily_summary_task（投递 MQ → 消费者异步生成）
   - 失败的用户记 error 日志，不阻塞下一个

设计要点：
- 单 asyncio 事件循环跑 APScheduler（AsyncIOScheduler）
- 启动前 init_producer（trigger_daily_summary_task 内部 publish 需要）
- 启动前 ping PG，DB 不通直接退出（无用户可遍历）
- 收到 SIGINT/SIGTERM 优雅退出（先停 scheduler 再关连接）
- 时区用 settings.TIMEZONE（默认 Asia/Shanghai）
- 业务任务异常不抛（避免 scheduler 整体退出），仅记日志
"""

from __future__ import annotations

import asyncio
import signal
import sys
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import settings
from app.database import PgSessionLocal, ping_pg
from app.db.rabbitmq_producer import close_producer, init_producer
from app.models.pg_orm import User
from app.services.ai_service import trigger_daily_summary_task
from app.utils.logger import logger, setup_logging


# 时区（默认 Asia/Shanghai，对应「凌晨 00:30」语义）
SCHEDULER_TIMEZONE = getattr(settings, "TIMEZONE", "Asia/Shanghai")

# 触发时点：每天 00:30（避开 00:00 整点任务密集期）
DAILY_REPORT_CRON = CronTrigger(hour=0, minute=30, timezone=SCHEDULER_TIMEZONE)


async def _generate_all_daily_reports() -> None:
    """定时任务：为全部用户生成当日 AI 营养简报。

    实现：
    1. 查 PG user 表取全部 user_id（status=1 正常）
    2. 对每个用户调 trigger_daily_summary_task
       - 优先投递 MQ（异步消费者处理）
       - MQ 不可用则 fallback 同步生成
    3. 单用户失败不影响其他用户

    异常处理：任务级 try/except，记日志后继续下一个用户。
    """
    today = date.today().isoformat()
    logger.info("scheduler_task_start", task="daily_reports", report_date=today)

    try:
        async with PgSessionLocal() as session:
            stmt = select(User.id).where(User.status == 1)
            user_ids = (await session.execute(stmt)).scalars().all()
    except Exception as exc:
        logger.error(
            "scheduler_task_load_users_failed",
            task="daily_reports",
            error=str(exc),
        )
        return

    if not user_ids:
        logger.info("scheduler_task_no_users", task="daily_reports")
        return

    success_count = 0
    fail_count = 0
    for uid in user_ids:
        try:
            await trigger_daily_summary_task(user_id=int(uid), report_date=today)
            success_count += 1
        except Exception as exc:
            fail_count += 1
            logger.error(
                "scheduler_task_user_failed",
                task="daily_reports",
                user_id=uid,
                report_date=today,
                error=str(exc),
            )

    logger.info(
        "scheduler_task_done",
        task="daily_reports",
        report_date=today,
        total=len(user_ids),
        success=success_count,
        fail=fail_count,
    )


async def _run_scheduler() -> None:
    """启动 APScheduler，阻塞直到收到退出信号。"""
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "scheduler_process_starting",
        env=settings.ENV,
        timezone=SCHEDULER_TIMEZONE,
    )

    # 启动前 ping PG（DB 不通直接退出，无用户可遍历）
    pg_ok = await ping_pg()
    if not pg_ok:
        logger.error("scheduler_process_exit_no_pg", reason="PG 不可用")
        return

    # 初始化 MQ 生产者（trigger_daily_summary_task 内部 publish 需要）
    await init_producer()

    scheduler = AsyncIOScheduler(timezone=SCHEDULER_TIMEZONE)
    scheduler.add_job(
        _generate_all_daily_reports,
        trigger=DAILY_REPORT_CRON,
        id="daily_reports",
        name="生成全部用户 AI 营养简报",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,  # 错过 10 分钟内仍补跑
    )
    scheduler.start()
    logger.info(
        "scheduler_ready",
        jobs=[j.id for j in scheduler.get_jobs()],
        next_run=str(scheduler.get_job("daily_reports").next_run_time)
        if scheduler.get_job("daily_reports")
        else None,
    )

    # 注册信号处理（优雅退出）
    stop_event = asyncio.Event()

    def _on_signal(signum: int, _frame) -> None:
        logger.info("scheduler_received_signal", signal=signum)
        stop_event.set()

    signals = [signal.SIGINT]
    if sys.platform != "win32":
        signals.append(signal.SIGTERM)
    for sig in signals:
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(sig, _on_signal, sig, None)
        except NotImplementedError:
            signal.signal(sig, _on_signal)

    await stop_event.wait()

    logger.info("scheduler_stopping")
    scheduler.shutdown(wait=False)
    await close_producer()
    logger.info("scheduler_stopped")


def main() -> None:
    """定时任务独立进程入口。"""
    try:
        asyncio.run(_run_scheduler())
    except KeyboardInterrupt:
        logger.info("scheduler_interrupted")
    except Exception as exc:
        logger.error("scheduler_crashed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
