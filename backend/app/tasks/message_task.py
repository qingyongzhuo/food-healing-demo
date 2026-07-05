"""消息推送 RabbitMQ 消费者（Phase 5 + Phase 8 增强）。

监听 task.push.msg 队列，收到推送任务后
调用 message_service.create_message 写入 system_message 表。

启动：
- 进程内：main.py lifespan 中 await start_message_consumer()
- 独立进程：uv run python -m app.tasks.run_consumer

Phase 8 容错增强：
- 主队列声明 x-dead-letter-exchange，nack(requeue=False) 进入死信队列
- 消费失败时按 x-retry header 跟踪重试次数：
  - retry < MQ_MAX_RETRIES：nack(requeue=True) 重投（带指数退避）
  - retry >= MQ_MAX_RETRIES：nack(requeue=False) 进入死信队列
- 每条消息消费前后完整日志打印（msg_id / retry / 耗时 / 结果）

设计要点：
- 用 aio-pika 的 RobustConnection（自动重连）
- 队列持久化（durable=True），与交换机 binding 后重启不丢
- 消费者手动 ack（no_ack=False），由 _process_message 显式 ack/nack
- RABBITMQ_URL 未配置时 graceful 跳过（与生产者一致）
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import aio_pika

from app.config import settings
from app.constants import (
    DLX_EXCHANGE,
    DLX_QUEUE_PUSH_MSG,
    MQ_MAX_RETRIES,
    MSG_TYPES,
    QUEUE_NAME_PUSH_MSG,
    ROUTING_KEY_PUSH_MSG,
)
from app.schemas.message import PushMessagePayload
from app.services import message_service
from app.utils.logger import logger


# 全局消费者任务句柄（用于关闭时取消）
_consumer_task: asyncio.Task | None = None
_connection: aio_pika.abc.AbstractRobustConnection | None = None


async def _process_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """处理一条推送消息，带重试 + 死信机制。

    手动 ack/nack 控制（no_ack=False 模式）：
    - 成功 → message.ack()
    - 校验类失败（消息本身有问题） → message.ack()，不重投
    - 业务异常 + retry < MAX → asyncio.sleep 退避后 message.nack(requeue=True)
    - 业务异常 + retry >= MAX → message.nack(requeue=False) 进入死信队列

    每条消息消费前后完整日志打印（msg_id / retry / 耗时 / 结果）。
    """
    # 提取重试计数（默认 0）
    headers = message.headers or {}
    retry_count = int(headers.get("x-retry", 0))
    msg_id = message.message_id or "-"
    body_preview = message.body[:200]

    logger.info(
        "message_consumer_msg_received",
        msg_id=msg_id,
        retry=retry_count,
        body_preview=body_preview,
    )

    start_time = time.monotonic()
    succeeded = False
    should_requeue = False

    try:
        body_text = message.body.decode("utf-8")
        payload_dict: dict[str, Any] = json.loads(body_text)

        # Pydantic 校验
        payload = PushMessagePayload(**payload_dict)

        # 业务侧二次校验 msg_type
        if payload.msg_type not in MSG_TYPES:
            logger.warning(
                "message_consumer_invalid_type",
                msg_id=msg_id,
                msg_type=payload.msg_type,
            )
            # 校验失败直接 ack（消息本身有问题，重投也不会成功）
            succeeded = True
        else:
            # 写入 DB
            await message_service.create_message(
                user_id=payload.user_id,
                msg_type=payload.msg_type,
                title=payload.title,
                content=payload.content,
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "message_consumer_ok",
                msg_id=msg_id,
                user_id=payload.user_id,
                msg_type=payload.msg_type,
                title=payload.title,
                elapsed_ms=elapsed_ms,
            )
            succeeded = True

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "message_consumer_failed",
            msg_id=msg_id,
            retry=retry_count,
            elapsed_ms=elapsed_ms,
            error=str(exc),
            body_preview=body_preview,
        )

        # 决定重试还是进死信队列
        if retry_count < MQ_MAX_RETRIES:
            # 退避延迟：base * 2^retry，上限 60s
            delay = min(5 * (2 ** retry_count), 60)
            logger.info(
                "message_consumer_retry_scheduled",
                msg_id=msg_id,
                retry=retry_count + 1,
                delay_seconds=delay,
            )
            await asyncio.sleep(delay)
            should_requeue = True
        else:
            # 达到最大重试次数，nack(requeue=False) 进入死信队列
            logger.error(
                "message_consumer_dlq_routed",
                msg_id=msg_id,
                retry=retry_count,
                max_retries=MQ_MAX_RETRIES,
                dlq=DLX_QUEUE_PUSH_MSG,
            )
            # should_requeue 保持 False

    # 显式 ack/nack（no_ack=False 模式下必须显式处理）
    try:
        if succeeded:
            await message.ack()
        else:
            await message.nack(requeue=should_requeue)
    except Exception as ack_exc:
        logger.warning(
            "message_consumer_ack_failed",
            msg_id=msg_id,
            error=str(ack_exc),
        )


async def _run_consumer() -> None:
    """消费者主循环（在后台 task 中跑）。

    声明死信交换机 + 死信队列，并把主队列的 x-dead-letter-exchange 指向它。
    """
    global _connection

    if not settings.RABBITMQ_URL:
        logger.info("message_consumer_skip_no_url")
        return

    try:
        _connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL, timeout=5
        )
        async with _connection:
            channel = await _connection.channel()

            # 1. 声明死信交换机（fanout，所有死信统一进入）
            dlx_exchange = await channel.declare_exchange(
                DLX_EXCHANGE,
                aio_pika.ExchangeType.FANOUT,
                durable=True,
            )

            # 2. 声明死信队列并绑定到 DLX
            dlq = await channel.declare_queue(DLX_QUEUE_PUSH_MSG, durable=True)
            await dlq.bind(dlx_exchange, routing_key="")

            # 3. 声明主队列（带 x-dead-letter-exchange 参数）
            queue_args = {
                "x-dead-letter-exchange": DLX_EXCHANGE,
                "x-dead-letter-routing-key": "",
            }
            queue = await channel.declare_queue(
                QUEUE_NAME_PUSH_MSG,
                durable=True,
                arguments=queue_args,
            )

            # 4. 绑定主队列到主交换机
            await queue.bind(
                settings.RABBITMQ_EXCHANGE,
                routing_key=ROUTING_KEY_PUSH_MSG,
            )

            logger.info(
                "message_consumer_ready",
                queue=QUEUE_NAME_PUSH_MSG,
                routing_key=ROUTING_KEY_PUSH_MSG,
                dlx=DLX_EXCHANGE,
                dlq=DLX_QUEUE_PUSH_MSG,
            )
            # prefetch=1，单消费者串行处理，避免压垮 DB
            await channel.set_qos(prefetch_count=1)
            await queue.consume(_process_message, no_ack=False)

            # 阻塞等待，直到被取消
            await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("message_consumer_stopped")
        raise
    except Exception as exc:
        logger.error("message_consumer_crashed", error=str(exc))


async def start_message_consumer() -> bool:
    """启动消息推送消费者。

    在后台 task 中跑 _run_consumer，避免阻塞 lifespan。
    Returns:
        True 已启动；False 未配置 MQ 或启动失败。
    """
    global _consumer_task

    if not settings.RABBITMQ_URL:
        logger.info("message_consumer_skip_no_url")
        return False

    _consumer_task = asyncio.create_task(_run_consumer())
    logger.info("message_consumer_started")
    return True


async def stop_message_consumer() -> None:
    """关闭消费者，释放连接。"""
    global _consumer_task, _connection

    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None

    if _connection is not None:
        try:
            await _connection.close()
        except Exception:
            pass
        _connection = None

    logger.info("message_consumer_closed")
