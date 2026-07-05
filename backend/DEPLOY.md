# 食愈校园 — 部署文档

## 1. 服务器信息

| 项目 | 值 |
|---|---|
| IP | `118.178.229.21` |
| 系统 | Alibaba Cloud Linux 8 (x86_64) |
| Python | 3.11+ |

## 2. 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    Docker 容器层                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │   web     │ │ consumer │ │scheduler │  ← 后端应用 │
│  │  :8000   │ │  (MQ消费) │ │ (定时任务) │             │
│  └──────────┘ └──────────┘ └──────────┘             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │PostgreSQL│ │  Redis   │ │ MongoDB  │  ← 数据存储 │
│  │  :5432   │ │  :6379   │ │  :27017  │             │
│  └──────────┘ └──────────┘ └──────────┘             │
│  ┌──────────┐ ┌──────────┐                         │
│  │RabbitMQ  │ │  MinIO   │           ← 中间件/OSS  │
│  │  :5672   │ │  :9000   │                         │
│  └──────────┘ └──────────┘                         │
└─────────────────────────────────────────────────────┘
```

## 3. 基础设施（Docker 部署）

### 3.1 PostgreSQL

- 端口：`5432`
- 数据库：`food_healing`
- 用户：`postgres`
- 密码：`1234@1234`

### 3.2 Redis

- 端口：`6379`
- 密码：`1234@1234`

### 3.3 MongoDB

- 端口：`27017`
- 数据库：`food_healing`

### 3.4 RabbitMQ

- 端口：`5672`（AMQP）/ `15672`（管理界面）
- 用户：`guest`
- 密码：`1234@1234`

### 3.5 MinIO

- 端口：`9000`（API）/ `9001`（控制台）
- Access Key：`minioadmin`
- Secret Key：`minioadmin`
- Bucket：`food-healing-images`

## 4. 后端应用（Docker 部署）

### 4.1 镜像构建

一个镜像三种运行模式，通过 `MODE` 环境变量切换：

| MODE | 进程 | 说明 |
|---|---|---|
| `web` | uvicorn 4 worker | FastAPI HTTP 服务，端口 8000 |
| `consumer` | MQ 消费者 | 消息推送 + 拍照识菜异步处理 |
| `scheduler` | APScheduler | 每日 00:30 触发 AI 营养简报 |

### 4.2 关键文件

| 文件 | 用途 |
|---|---|
| `Dockerfile` | 基于 `python:3.11-slim` + `uv` 构建 |
| `.dockerignore` | 排除 `.venv`、`__pycache__`、测试等 |
| `docker-compose.yml` | 编排 web / consumer / scheduler 三个容器 |
| `.env` | 环境变量（数据库连接、AI Key、JWT 密钥等） |

### 4.3 环境变量要点

| 变量 | 必填 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | ✅ | 通义千问 VL（拍照识菜） |
| `BAILIAN_API_KEY` | ✅ | 阿里百炼（AI 对话/简报） |
| `PG_DSN` | ✅ | PostgreSQL 连接串 |
| `REDIS_URL` | ✅ | Redis 连接串 |
| `MONGO_URL` | ❌ | MongoDB 连接串（空则跳过） |
| `RABBITMQ_URL` | ✅ | RabbitMQ 连接串 |
| `OSS_ENDPOINT` | ✅ | MinIO endpoint |
| `JWT_SECRET` | ✅ | 生产必须修改为随机字符串 |
| `JWT_EXPIRE_HOURS` | 默认 168（7 天） | Token 过期时间 |

### 4.4 容器间网络

后端容器通过 Docker 网络与基础设施容器通信。`.env` 中数据库地址需使用容器名（如 `postgres`、`redis`）而非 IP，前提是所有容器在同一 Docker 网络内。

## 5. 部署步骤

### 5.1 本地配置 SSH 密钥

```powershell
# 生成密钥（如果还没有）
ssh-keygen -t ed25519 -C "your_email@example.com"

# 查看公钥
type C:\Users\30612\.ssh\id_ed25519.pub
```

### 5.2 服务器添加公钥

通过云控制台 VNC 登录服务器：

```bash
mkdir -p ~/.ssh
echo "粘贴公钥内容" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 5.3 上传代码

```powershell
scp -r d:\desktop\Trae\food-healing-demo\backend root@118.178.229.21:/opt/food-healing/
```

### 5.4 配置环境变量

```bash
cd /opt/food-healing/backend

# 编辑 .env，确保数据库连接地址正确
# 如果 infra 和 backend 在同一 Docker 网络，用容器名代替 IP：
#   PG_DSN=postgresql+asyncpg://postgres:1234%401234@postgres:5432/food_healing
#   REDIS_URL=redis://:1234%401234@redis:6379/0
#   RABBITMQ_URL=amqp://guest:1234%401234@rabbitmq:5672/
#   MONGO_URL=mongodb://mongo:27017
#   OSS_ENDPOINT=http://minio:9000

vi .env
```

### 5.5 构建并启动

```bash
cd /opt/food-healing/backend

# 构建镜像
docker compose build

# 初始化数据库（仅首次）
docker compose run --rm web uv run fh-init-db

# 启动全部服务
docker compose up -d

# 查看日志
docker compose logs -f
```

### 5.6 验证

```bash
# 健康检查
curl http://127.0.0.1:8000/api/health

# 预期返回各组件连通状态
```

## 6. 常用运维命令

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f web          # web 服务日志
docker compose logs -f consumer     # 消费者日志
docker compose logs -f scheduler    # 定时任务日志

# 重启服务
docker compose restart web

# 停止全部
docker compose down

# 重新构建并启动
docker compose up -d --build
```

## 7. 数据备份

```bash
# PostgreSQL 备份
docker exec <pg容器名> pg_dump -U postgres food_healing > backup.sql

# 恢复
docker exec -i <pg容器名> psql -U postgres food_healing < backup.sql
```

## 8. 注意事项

- **JWT_SECRET**：生产环境必须修改 `.env` 中的默认值
- **三进程分离**：web / consumer / scheduler 各自独立容器，不能合并
- **日志**：写入 `logs/app.log`，按日轮转，默认保留 14 天
- **MongoDB**：可选组件，`MONGO_URL` 为空时 AI 对话历史不持久化但功能不中断
- **RabbitMQ**：未配置时 graceful 降级，识菜任务改用 asyncio 后台执行