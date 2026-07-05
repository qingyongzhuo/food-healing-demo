"""RabbitMQ 消费者独立进程启动入口（Phase 8）。

部署时与 web 服务分进程运行，避免消费者阻塞影响 API 响应：
    uv run python -m app.tasks.run_consumer

启动的消费者：
1. 识菜消费者（ai_task.start_recognize_consumer）
   - 监听 ai_recognize_queue，处理拍照识菜任务
2. 每日 AI 简报消费者（ai_task.start_daily_summary_consumer）
   - 监听 ai_daily_summary_queue，生成日报 + 推送消息
3. 消息推送消费者（message_task.start_message_consumer）
   - 监听 task.push.msg.queue，写入 system_message 表

设计要点：
- 单 asyncio 事件循环跑全部消费者
- 启动前先 init_producer（消费者内复用连接池）
- 启动失败不退出进程，仅记日志（避免单消费者故障拖垮其他消费者）
- 收到 SIGINT/SIGTERM 优雅退出（先停消费者再关连接）
- RABBITMQ_URL 为空时直接退出（无消费者可跑）
"""

from __future__ import annotations

import asyncio
import signal
import sys

from app.config import settings
from app.db.rabbitmq_producer import close_producer, init_producer
from app.tasks.ai_task import (
    start_daily_summary_consumer,
    start_recognize_consumer,
    stop_daily_summary_consumer,
    stop_recognize_consumer,
)
from app.tasks.message_task import (
    start_message_consumer,
    stop_message_consumer,
)
from app.utils.logger import logger, setup_logging


async def _run_all_consumers() -> None:
    """启动全部 RabbitMQ 消费者，阻塞直到收到退出信号。"""
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "consumer_process_starting",
        env=settings.ENV,
        rabbitmq_configured=bool(settings.RABBITMQ_URL),
    )

    if not settings.RABBITMQ_URL:
        logger.warning(
            "consumer_process_exit_no_mq",
            reason="RABBITMQ_URL 未配置，无消费者可运行",
        )
        return

    # 初始化生产者（消费者内部 publishing 场景会复用）
    await init_producer()

    # 启动顺序：识菜 → 每日简报 → 消息推送（互不依赖）
    consumers_started: list[tuple[str, bool]] = []

    ok1 = await start_recognize_consumer()
    consumers_started.append(("recognize", ok1))

    ok2 = await start_daily_summary_consumer()
    consumers_started.append(("daily_summary", ok2))

    ok3 = await start_message_consumer()
    consumers_started.append(("message_push", ok3))

    for name, ok in consumers_started:
        status = "started" if ok else "skipped_or_failed"
        logger.info("consumer_status", name=name, status=status)

    if not any(ok for _, ok in consumers_started):
        logger.error(
            "consumer_process_exit_all_failed",
            reason="全部消费者启动失败，退出进程",
        )
        await close_producer()
        return

    # 注册信号处理（优雅退出）
    stop_event = asyncio.Event()

    def _on_signal(signum: int, _frame) -> None:
        logger.info("consumer_received_signal", signal=signum)
        stop_event.set()

    # Windows 仅支持 SIGINT；Linux SIGTERM/SIGINT
    signals = [signal.SIGINT]
    if sys.platform != "win32":
        signals.append(signal.SIGTERM)
    for sig in signals:
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(sig, _on_signal, sig, None)
        except NotImplementedError:
            # Windows asyncio loop 不支持 add_signal_handler，fallback 到 signal
            signal.signal(sig, _on_signal)

    logger.info("consumer_process_ready_waiting_for_messages")
    await stop_event.wait()

    # 优雅退出：先停消费者，再关生产者
    logger.info("consumer_process_stopping")
    await stop_recognize_consumer()
    await stop_daily_summary_consumer()
    await stop_message_consumer()
    await close_producer()
    logger.info("consumer_process_stopped")


def main() -> None:
    """消费者独立进程入口。"""
    try:
        asyncio.run(_run_all_consumers())
    except KeyboardInterrupt:
        logger.info("consumer_process_interrupted")
    except Exception as exc:
        logger.error("consumer_process_crashed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
