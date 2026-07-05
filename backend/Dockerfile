# 食愈校园后端 Docker 镜像
# 构建：docker build -t food-healing-backend .
# 使用：docker run -e MODE=web food-healing-backend

FROM python:3.11-slim

# 阿里云 PyPI 镜像加速
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 安装 uv（用 pip 避免 ghcr.io 在国内拉取超时）
RUN pip install uv --no-cache-dir

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY pyproject.toml uv.lock ./

# 安装依赖（生产模式，不装 dev）
RUN uv sync --no-dev --frozen

# 复制源码
COPY app/ ./app/

# 创建上传目录和日志目录
RUN mkdir -p uploads/avatars uploads/camera logs

# 默认环境变量
ENV HOST=0.0.0.0
ENV PORT=8000
ENV WORKERS=4
ENV PYTHONUNBUFFERED=1

# 通过 MODE 环境变量切换运行模式
# MODE=web       → 生产 web 服务（默认）
# MODE=consumer  → RabbitMQ 消费者
# MODE=scheduler → APScheduler 定时任务
ENV MODE=web

EXPOSE 8000

CMD if [ "$MODE" = "consumer" ]; then \
    uv run python -m app.tasks.run_consumer; \
    elif [ "$MODE" = "scheduler" ]; then \
    uv run python -m app.tasks.run_scheduler; \
    else \
    uv run uvicorn app.main:app --host "$HOST" --port "$PORT" --workers "$WORKERS"; \
    fi