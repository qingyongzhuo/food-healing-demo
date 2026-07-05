"""structlog 配置。

输出结构化 JSON 日志，含 request_id/user_id/latency_ms 等字段。
AI 调用单独 logger 额外记录 model/scene/duration_ms/success。

阶段 8 增强：
- 同时输出到 stdout + 文件（按日轮转，保留 14 天）
- 文件路径 logs/app.log（自动创建目录）
- 文件输出 JSON 单行（便于 ELK / Loki 采集）
- stdout 仍为 JSON（structlog 默认行为）

环境变量控制：
- LOG_LEVEL：DEBUG/INFO/WARN/ERROR，默认 INFO
- LOG_DIR：日志目录，默认 logs
- LOG_RETENTION_DAYS：保留天数，默认 14
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import structlog

from app.config import settings


def _build_file_handler(log_dir: Path, retention_days: int) -> TimedRotatingFileHandler:
    """构造按日轮转的文件 handler。

    - 文件路径：{log_dir}/app.log
    - 轮转：每日 0 点，备份文件后缀 .YYYY-MM-DD
    - 保留：retention_days 天（通过 backupCount 实现）
    - 编码：UTF-8（Windows 默认 GBK 会导致中文乱码）
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
        utc=False,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def setup_logging(log_level: str | None = None) -> None:
    """初始化 structlog 与标准 logging。

    Args:
        log_level: 日志级别字符串（DEBUG/INFO/WARN/ERROR），默认读 settings.LOG_LEVEL。
    """
    level = log_level or settings.LOG_LEVEL
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # 文件 handler（按日轮转）
    log_dir = Path(getattr(settings, "LOG_DIR", "logs"))
    retention = int(getattr(settings, "LOG_RETENTION_DAYS", 14))
    file_handler = _build_file_handler(log_dir, retention)

    # 标准 logging 基础配置：双输出（stdout + 文件）
    # 注意：stream 与 handlers 不能同时传，故只传 handlers
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        handlers=[logging.StreamHandler(sys.stdout), file_handler],
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
"""默认业务 logger。"""

ai_logger = structlog.get_logger("ai")
"""AI 调用专用 logger，额外记录 model/scene/duration_ms/success/fallback 字段。"""
