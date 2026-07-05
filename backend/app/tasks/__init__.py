"""tasks 子包：后台异步任务。

当前识图任务用 asyncio.create_task 跑在 services/recognize_service.py，
后续可迁移到本子包统一管理（如改用 RabbitMQ 消费者模式）。

Phase 1 占位，无实际代码。
"""
