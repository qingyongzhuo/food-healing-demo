"""RabbitMQ 生产者单例（aio-pika）。

- 全局单例连接 + 交换机，应用启动时 init_producer()，关闭时 close_producer()
- publish() 通用发送方法：业务代码只传 routing_key + body dict
- RABBITMQ_URL 为空时 graceful 跳过（Phase 1 识图改 asyncio.create_task，MQ 暂不用）

用法：
    from app.db.rabbitmq_producer import publish, init_producer, close_producer

    # main.py lifespan 启动：await init_producer()
    # 业务发送：await publish("recognize.task", {"task_id": "xxx", ...})
    # main.py lifespan 关闭：await close_producer()
"""

from __future__ import annotations

import json
from typing import Any

import aio_pika

from app.config import settings
from app.utils.logger import logger


# 全局单例（启动时初始化，关闭时置 None）
_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractRobustChannel | None = None
_exchange: aio_pika.abc.AbstractRobustExchange | None = None


async def init_producer() -> bool:
    """初始化 RabbitMQ 连接 + 信道 + 交换机。

    RABBITMQ_URL 为空时直接返回 False（不报错，graceful 跳过）。
    连接失败时记录 warning 但不抛异常，避免阻塞应用启动。

    Returns:
        True 已初始化；False 跳过（未配置）或失败。
    """
    global _connection, _channel, _exchange

    if not settings.RABBITMQ_URL:
        logger.info("rabbitmq_producer_skip_no_url")
        return False

    try:
        _connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL, timeout=5
        )
        _channel = await _connection.channel()
        # 声明持久化交换机（durable=True，重启不丢）
        exchange_type = getattr(
            aio_pika.ExchangeType, settings.RABBITMQ_EXCHANGE_TYPE.upper(),
            aio_pika.ExchangeType.DIRECT,
        )
        _exchange = await _channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE,
            exchange_type,
            durable=True,
        )
        logger.info(
            "rabbitmq_producer_ready",
            exchange=settings.RABBITMQ_EXCHANGE,
            type=settings.RABBITMQ_EXCHANGE_TYPE,
        )
        return True
    except Exception as exc:
        logger.warning("rabbitmq_producer_init_failed", error=str(exc))
        # 重置单例，避免半连接状态
        _connection = None
        _channel = None
        _exchange = None
        return False


async def publish(
    routing_key: str,
    body: dict[str, Any],
    *,
    persistent: bool = True,
    content_type: str = "application/json",
) -> bool:
    """发送一条 JSON 消息到主交换机。

    Args:
        routing_key: 路由键，如 "recognize.task"。
        body: 消息体（dict，自动 json 序列化）。
        persistent: 是否持久化（默认 True，写入磁盘）。
        content_type: 内容类型，默认 application/json。

    Returns:
        True 发送成功；False 未初始化或发送失败（graceful）。
    """
    if _exchange is None:
        logger.warning(
            "rabbitmq_publish_skip_not_ready",
            routing_key=routing_key,
        )
        return False

    try:
        message = aio_pika.Message(
            body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            content_type=content_type,
            delivery_mode=(
                aio_pika.DeliveryMode.PERSISTENT
                if persistent
                else aio_pika.DeliveryMode.NOT_PERSISTENT
            ),
        )
        await _exchange.publish(message, routing_key=routing_key)
        logger.info(
            "rabbitmq_publish_ok",
            routing_key=routing_key,
            body_size=len(body),
        )
        return True
    except Exception as exc:
        logger.error(
            "rabbitmq_publish_failed",
            routing_key=routing_key,
            error=str(exc),
        )
        return False


async def push_message(
    user_id: int,
    msg_type: str,
    title: str,
    content: str,
) -> bool:
    """便捷方法：发送一条消息推送任务到 task.push.msg 队列。

    消费者（tasks/message_task.py）监听此队列后调用
    message_service.create_message 写入 system_message 表。

    Args:
        user_id: 目标用户 ID
        msg_type: 消息类型（remind / ai），见 app.constants.MSG_TYPES
        title: 标题
        content: 正文

    Returns:
        True 发送成功；False MQ 未就绪或发送失败（graceful，业务侧可降级直写 DB）
    """
    from app.constants import ROUTING_KEY_PUSH_MSG

    body = {
        "user_id": user_id,
        "msg_type": msg_type,
        "title": title,
        "content": content,
    }
    return await publish(ROUTING_KEY_PUSH_MSG, body)


async def close_producer() -> None:
    """关闭 RabbitMQ 连接，释放资源。"""
    global _connection, _channel, _exchange

    if _connection is None:
        return

    try:
        await _connection.close()
        logger.info("rabbitmq_producer_closed")
    except Exception as exc:
        logger.warning("rabbitmq_producer_close_failed", error=str(exc))
    finally:
        _connection = None
        _channel = None
        _exchange = None


def is_ready() -> bool:
    """检查生产者是否已就绪（用于健康检查）。"""
    return _exchange is not None
