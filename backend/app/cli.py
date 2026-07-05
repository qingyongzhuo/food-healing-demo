"""快捷启动命令入口（Phase 8）。

通过 pyproject.toml [project.scripts] 注册为控制台命令，
`uv sync` 后可直接：

    uv run fh-dev          # 开发模式 web 服务（热重载）
    uv run fh-prod         # 生产模式 web 服务（4 worker）
    uv run fh-consumer     # RabbitMQ 消费者独立进程
    uv run fh-scheduler    # APScheduler 定时任务独立进程
    uv run fh-init-db      # 初始化 PG 表 + 种子数据
    uv run fh-check-db     # 检查各表数据情况

也可直接用 uvicorn / python -m 调用，等价命令：
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    uv run python -m app.tasks.run_consumer
    uv run python -m app.tasks.run_scheduler
    uv run python -m app.scripts.init_db
    uv run python -m app.scripts.check_data
"""

from __future__ import annotations

import os
import sys


def dev() -> None:
    """开发模式 web 服务（热重载，单进程）。"""
    # 用 os.execvp 让 uvicorn 接管进程，支持 Ctrl-C 优雅退出
    args = [
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        os.environ.get("HOST", "0.0.0.0"),
        "--port",
        os.environ.get("PORT", "8000"),
    ]
    _exec_uvicorn(args)


def prod() -> None:
    """生产模式 web 服务（4 worker，无热重载）。"""
    args = [
        "uvicorn",
        "app.main:app",
        "--host",
        os.environ.get("HOST", "0.0.0.0"),
        "--port",
        os.environ.get("PORT", "8000"),
        "--workers",
        os.environ.get("WORKERS", "4"),
    ]
    _exec_uvicorn(args)


def consumer() -> None:
    """RabbitMQ 消费者独立进程入口。"""
    from app.tasks.run_consumer import main

    main()


def scheduler() -> None:
    """APScheduler 定时任务独立进程入口。"""
    from app.tasks.run_scheduler import main

    main()


def init_db() -> None:
    """初始化 PG 表 + 种子数据。"""
    from app.scripts.init_db import main

    main()


def check_db() -> None:
    """检查各表数据情况。"""
    from app.scripts.check_data import main

    main()


def _exec_uvicorn(args: list[str]) -> None:
    """以子进程方式启动 uvicorn，转发退出码。"""
    import subprocess

    try:
        result = subprocess.run(args)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(130)
