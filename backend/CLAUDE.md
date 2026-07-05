# 食愈后端 — Claude.md

> 给 AI 协作助手的工程导航文档。读这一份就能快速定位代码、理解约定。

## 1. 项目概述

**食愈校园** — 会成长、会记忆、会陪伴的校园饮食伙伴。后端提供用户鉴权、AI 对话（SSE 流式）、拍照识菜（异步任务）、营养记录、健康档案等能力。

- **定位**：面向校园学生的饮食记录 + AI 营养陪伴 App 后端
- **部署服务器**：`118.178.229.21`（PG/Mongo/Redis/OSS 同机）
- **当前阶段**：Phase 8 完成（uv 包管理 + 多进程启动 + APScheduler 定时简报 + MQ 容错增强；后端核心架构全部就绪）

## 2. 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| Web 框架 | FastAPI 0.139+ | 异步、自动 OpenAPI 文档 |
| ASGI | uvicorn[standard] | 开发 `--reload`，生产直接跑 |
| 配置 | pydantic-settings + .env | `app/config.py` 单例 |
| ORM | SQLAlchemy 2.0 [asyncio] | 异步引擎，`sessionmaker` |
| PG 驱动 | asyncpg | SQLAlchemy 底层（8 张关系表） |
| MongoDB | motor 3.6+ | 异步驱动（3 个集合：AI 对话/识图日志/日报） |
| Redis | redis[async] | `redis.asyncio` 连接池（会话 + 缓存） |
| MQ | aio-pika | RabbitMQ（已启用 `amqp://guest:guest@118.178.229.21:5672/`，生产者+消费者；未配置时 graceful 跳过） |
| AI 平台 | 阿里百炼 + DashScope | OpenAI 兼容模式，双 API Key |
| AI SDK | openai（Python） | 文本对话 + 多模态识图 |
| 鉴权 | PyJWT + bcrypt | HS256，7 天过期，user_id 为 int |
| 日志 | structlog + TimedRotatingFileHandler | JSON 结构化 + 按日轮转文件持久化（`logs/app.log`，默认保留 14 天） |
| 限流 | slowapi | 识图 10/min，对话 20/min |
| 对象存储 | oss2 | MinIO 兼容 S3 |
| 定时任务 | APScheduler 3.10+ | AsyncIOScheduler，每日 00:30 触发全量 AI 简报（独立进程） |
| 包管理 | uv + pyproject.toml（hatchling 后端） | `uv sync` 一键装齐 + `[project.scripts]` 注册快捷命令 |

## 3. 目录结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口，lifespan + 路由注册
│   ├── config.py               # pydantic-settings 全局配置单例
│   ├── constants.py            # 业务常量（消息类型/MQ 路由键/AI prompt 模板/DLX 死信配置等）
│   ├── database.py             # PG/Mongo/Redis 连接 + ping + close_all
│   ├── middleware.py           # RequestId/Auth/CORS/RequestLog 四件套
│   ├── exceptions.py           # BizError + 全局异常处理器 + success/not_implemented
│   ├── cli.py                  # Phase 8 快捷启动入口（fh-dev/fh-prod/fh-consumer/fh-scheduler/fh-init-db/fh-check-db）
│   │
│   ├── ai/
│   │   └── router.py           # 场景→模型路由表（chat/recognize/report/mood/...）
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── rabbitmq_producer.py  # aio-pika 生产者单例（init/publish/push_message/close）
│   │
│   ├── utils/
│   │   ├── auth.py             # JWT + bcrypt + Redis 会话 + get_current_user_id 依赖注入
│   │   ├── logger.py           # structlog 配置 + logger + ai_logger
│   │   ├── bailian_client.py   # 百炼统一入口：chat_text + chat_multimodal + recognize_dish（阶段 6）
│   │   └── file_upload.py      # 图片上传压缩工具（Pillow 1024px + JPEG 85，阶段 6）
│   │
│   ├── models/
│   │   ├── schemas.py          # BaseResponse + 错误码常量（5 段）
│   │   └── pg_orm.py           # PG ORM 模型（8 张表：user/user_body_target/standard_food/user_custom_food/user_collect_food/daily_diet_record/meal_item/system_message）
│   ├── schemas/                # Pydantic 校验模型按模块拆分
│   │   ├── __init__.py
│   │   ├── user.py             # 用户中心：4 类入参/出参模型（user_id: int）
│   │   ├── food.py             # 食材库 + 饮食记录：5 类模型（Phase 4）
│   │   ├── message.py          # 消息通知：4 类模型（Phase 5）
│   │   ├── camera.py           # 拍照识菜：4 类模型 + 分类色映射（Phase 6）
│   │   └── ai_chat.py          # AI 营养师对话 + 每日简报：10 类模型（Phase 3）
│   │
│   ├── services/
│   │   ├── auth_service.py     # 注册/登录/登出/档案/头像/改密业务（user_id: int）
│   │   ├── chat_service.py     # AI 对话 SSE 流式 + 非流式（user_id: int）
│   │   ├── recognize_service.py# 识菜异步任务 + Qwen-VL（user_id: int）
│   │   ├── user_service.py     # 用户中心：基础资料/身体/目标/收藏（DB 部分占位）
│   │   ├── food_service.py     # 食材库 + 饮食记录业务（Phase 4，DB 占位）
│   │   ├── message_service.py  # 消息通知业务：查询/已读/清空/新增（Phase 5，DB 占位）
│   │   ├── camera_service.py   # 拍照识菜：图片上传 + MQ/fallback + Mongo 持久化（Phase 6）
│   │   └── ai_service.py       # AI 营养师对话 + 每日简报业务（Phase 3，PG + Mongo + 百炼）
│   │
│   ├── routes/                 # API 路由（统一 /api 前缀）
│   │   ├── auth.py             # ✅ 鉴权（完整实现）
│   │   ├── chat.py             # ✅ AI 对话 SSE（完整实现）
│   │   ├── recognize.py        # ✅ 拍照识菜（完整实现）
│   │   ├── health.py           # ✅ 健康检查（完整实现）+ 健康档案（占位）
│   │   ├── food.py             # ✅ 食材 + 饮食记录（Phase 4，8 个鉴权路由）
│   │   ├── message.py          # ✅ 消息通知（Phase 5，4 个鉴权路由）
│   │   ├── preferences.py      # ⏳ 过敏/忌口（占位 Phase 2）
│   │   ├── menu.py             # ⏳ 食堂菜单（占位）
│   │   ├── recommend.py        # ⏳ 推荐算法（占位）
│   │   ├── leaderboard.py      # ⏳ 排行榜（占位）
│   │   ├── mood.py             # ⏳ 情绪（占位）
│   │   ├── sport.py            # ⏳ 运动（占位）
│   │   ├── weekly_report.py    # ⏳ 周报（占位）
│   │   ├── voice_to_tray.py    # ⏳ 语音转餐盘（占位）
│   │   ├── share_card.py       # ⏳ 分享卡片（占位）
│   │   ├── user.py             # ✅ 用户中心（Phase 3，DB 占位待迁移）
│   │   ├── camera.py           # ✅ 拍照识菜（Phase 6，3 个鉴权路由）
│   │   ├── ai_chat.py          # ✅ AI 营养师对话 + 每日简报（Phase 3，4 个鉴权路由）
│   │   └── admin.py            # ⏳ 管理后台（占位）
│   │
│   ├── tasks/
│   │   ├── __init__.py         # 后台任务占位（识图用 asyncio.create_task）
│   │   ├── message_task.py     # ✅ 消息推送消费者（Phase 5 + Phase 8 容错：重试 + 死信队列）
│   │   ├── ai_task.py          # ✅ 拍照识菜消费者（Phase 6，监听 task.ai.recognize）+ 每日简报消费者（Phase 3，监听 task.ai.daily）
│   │   ├── run_consumer.py    # Phase 8 独立消费者进程入口（注册全部 MQ 消费者 + 信号处理）
│   │   └── run_scheduler.py    # Phase 8 APScheduler 独立进程入口（每日 00:30 触发 AI 简报）
│   │
│   └── scripts/
│       ├── init_db.py          # PG 初始化：建 8 张表 + 插入 6 条标准食材种子数据
│       └── check_data.py       # 检查各表数据情况（fh-check-db 调用）
│
├── tests/
│   ├── conftest.py
│   └── test_health.py
│
├── uploads/avatars/            # 头像本地存储
├── uploads/camera/             # 拍照识菜图片存储（Phase 6，Pillow 压缩后）
├── logs/                       # Phase 8：日志文件目录（app.log 按日轮转，默认保留 14 天）
├── data/foods.json             # 食物营养数据
├── .env                        # 实际配置（不入库）
├── .env.example                # 配置模板
├── pyproject.toml              # 依赖声明 + [project.scripts] 快捷命令 + [tool.uv] package=true + hatchling 后端
└── uv.lock                     # uv 锁定文件（依赖版本固定）
```

## 4. API 接口契约

### 4.1 统一响应格式

```json
{ "code": 0, "message": "ok", "data": {} }
```

- `code=0` 成功；非 0 见错误码表
- `data` 缺失返回 `{}` 不返回 `null`
- HTTP 状态码与业务错误码独立（业务错误 HTTP 200，参数错误 HTTP 422，未登录 HTTP 401）

### 4.2 错误码分段（`app/models/schemas.py`）

| 段 | 含义 | 示例 |
|---|---|---|
| 1xxxx | 业务参数 | 10001 缺参 / 10002 格式 / 10007 用户已存在 |
| 2xxxx | AI 调用 | 20001 VL 调用 / 20003 对话失败 |
| 3xxxx | 数据库 | 30001 DB / 30002 PG / 30003 Redis |
| 4xxxx | 鉴权限流 | 40101 未登录 / 40102 token 过期 / 42901 限流 |
| 5xxxx | 系统 | 50000 内部错误 / 50100 未实现 |

### 4.3 已实现接口

#### 鉴权 `/api/auth`（白名单：register/login）

| Method | Path | 说明 | 鉴权 |
|---|---|---|---|
| POST | `/api/auth/register` | 注册，返回 `{token, user}` | ❌ |
| POST | `/api/auth/login` | 登录，返回 `{token, user}` | ❌ |
| POST | `/api/auth/logout` | 登出，删 Redis 会话 | ✅ |
| GET | `/api/auth/me` | 查当前用户信息 + 习惯 | ✅ |
| PUT | `/api/auth/profile` | 改昵称 | ✅ |
| POST | `/api/auth/avatar` | 上传头像（FormData: file） | ✅ |
| PUT | `/api/auth/password` | 改密码（需旧密码） | ✅ |

**请求体示例**：
```json
// POST /api/auth/register（nickname 作登录账号，phone 选填）
{ "nickname": "alice", "password": "123456", "phone": "13800138000" }

// POST /api/auth/login
{ "nickname": "alice", "password": "123456" }

// POST /api/auth/logout（无 body，需 Authorization 头）
// PUT /api/auth/profile
{ "nickname": "新昵称" }

// PUT /api/auth/password
{ "old_password": "123456", "new_password": "654321" }
```

**响应示例**：
```json
// POST /api/auth/login 成功
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "token": "eyJ...",
    "user": {
      "user_id": 1,
      "nickname": "alice",
      "phone": "13800138000",
      "avatar_url": "",
      "theme": "light",
      "status": 1,
      "create_time": "2026-07-04T07:36:33.301676",
      "last_login": "2026-07-04T07:39:54.880348"
    }
  }
}

// POST /api/auth/logout 成功
{ "code": 0, "message": "已退出登录", "data": null }
```

**注**：user_id 在 JWT payload 中以 `str(user_id)` 存储（JSON 安全），业务层统一为 `int`。Redis 会话 key 为 `user:token:{user_id}`，TTL = `JWT_EXPIRE_HOURS * 3600`（默认 7 天）。**强校验**：`AuthMiddleware` 在 JWT 签名/过期校验通过后，再调 `utils/auth.validate_session(user_id, token)` 比对 Redis 中存储的 token；不一致返回 401。logout 删 Redis、change_password 提交后调 `remove_session(user_id)` → 旧 token 立即失效。Redis 异常时 fail-open（保可用，不全员下线）。

#### AI 对话 `/api/chat`

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/chat?stream=true` | SSE 流式对话（默认） |
| POST | `/api/chat?stream=false` | 一次性返回（降级） |

**请求体**：
```json
{
  "persona": "canteen_aunt",
  "messages": [{"role": "user", "content": "今天吃啥"}],
  "context": {"user_id": 1, "mode": "daily"}
}
```

**SSE 事件协议**（与前端 `api.js` 对齐）：
```
event: delta
data: {"delta":"今","done":false}

event: memory_hint
data: {"hint":"你上周说胃不舒服"}

event: done
data: {"delta":"","done":true}
```

#### 拍照识菜 `/api/recognize-dish`

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/recognize-dish` | 提交识菜任务，返回 `{task_id, status}` |
| GET | `/api/recognize/result/{task_id}` | 轮询结果，status: pending/processing/done/failed |

**提交（FormData）**：
- `file`: 图片文件（jpg/png/webp，≤5MB）
- `user_id`: 可选（token 优先）
- `meal_hint`: 可选（breakfast/lunch/dinner/snack）

**轮询响应（done 态）**：
```json
{
  "code": 0,
  "data": {
    "task_id": "rec_xxxxxxxxxxxx",
    "status": "done",
    "progress": 100,
    "dish": {
      "id": "r1234567890",
      "name": "红烧鸡",
      "category": "肉类",
      "unit": "份(150g)",
      "kcal": 250, "protein": 22, "carb": 8, "fat": 15,
      "confidence": 0.92,
      "matched": true,
      "alternatives": [{ /* 备选菜品 */ }]
    }
  }
}
```

#### 健康检查

| Method | Path | 说明 | 鉴权 |
|---|---|---|---|
| GET | `/api/health` | 各组件连通性（pg/redis/mongo/rabbitmq/nacos/oss） | ❌ |
| GET | `/` | 根路由，返回应用信息 | ❌ |

#### 用户中心 `/api/user`（Phase 3，全部需 Token）

| Method | Path | 说明 | 状态 |
|---|---|---|---|
| GET | `/api/user/profile` | 获取个人全部信息（user + body_target + collect_food_ids） | 接口就绪，DB 占位 |
| PUT | `/api/user/profile` | 编辑基础资料（昵称、头像、手机号、主题） | 接口就绪，DB 占位 |
| PUT | `/api/user/body` | 调整身体数据（身高、体重、性别、年龄） | 接口就绪，DB 占位 |
| PUT | `/api/user/target` | 修改每日营养目标（kcal、蛋白、碳水、脂肪、目标类型） | 接口就绪，DB 占位 |
| GET | `/api/user/collect` | 获取收藏食材列表（含详情） | 接口就绪，Redis 可用 |
| POST | `/api/user/collect/{food_id}` | 收藏 / 取消收藏食材（toggle） | 接口就绪，Redis 可用 |

**请求体示例**：
```json
// PUT /api/user/profile（部分更新，至少传一个字段）
{ "nickname": "新昵称", "avatar_url": "/static/avatars/x.jpg", "phone": "13800138000", "theme": "dark" }

// PUT /api/user/body（部分更新）
{ "height_cm": 175.0, "weight_kg": 65.5, "gender": "male", "age": 22 }

// PUT /api/user/target（全量更新）
{ "daily_kcal": 2000, "protein_g": 60, "carb_g": 260, "fat_g": 65, "target_type": "maintain" }
```

**响应示例**：
```json
// GET /api/user/profile
{
  "code": 0,
  "data": {
    "user": { "user_id": 1, "nickname": "爱丽丝", "avatar_url": "...", "phone": "138...", "created_at": "..." },
    "body_target": { "height_cm": 165.0, "weight_kg": 55.0, "gender": "female", "age": 20, "target_type": "fat_loss", "daily_kcal": 1600, "protein_g": 60, "carb_g": 200, "fat_g": 50, "theme": "light" },
    "collect_food_ids": ["1", "12"]
  }
}

// POST /api/user/collect/1
{ "code": 0, "message": "已收藏", "data": { "collected": true, "food_id": "1" } }
```

**数据表（PG）**：
- `user_body_target`：用户身体数据 + 营养目标 + 主题，user_id 外键
- `user_collect_food`：用户收藏食材关联，user_id + food_id + custom_food_id 联合唯一
- Redis key：`user:collect:{user_id}` → SET，缓存收藏 ID 集合

**注**：service 层 DB 操作用 `pass + # TODO` 占位，待 Phase 3 填充。Redis 缓存部分已可用。

#### 食材库 + 饮食记录 `/api/food` & `/api/diet`（Phase 4，全部需 Token）

| Method | Path | 说明 | 状态 |
|---|---|---|---|
| GET | `/api/food/list` | 食材列表（搜索 + 分类筛选 + Redis 缓存） | 接口就绪，Redis 可用，DB 占位 |
| POST | `/api/food/custom` | 新增自定义食材 | 接口就绪，DB 占位 |
| PUT | `/api/food/custom/{id}` | 编辑自定义食材（owner 校验） | 接口就绪，DB 占位 |
| DELETE | `/api/food/custom/{id}` | 删除自定义食材（owner 校验） | 接口就绪，DB 占位 |
| POST | `/api/diet/add` | 添加食材到当日某一餐（支持多选） | 接口就绪，营养换算可用，DB 占位 |
| PUT | `/api/diet/item/{item_id}` | 修改餐食重量（自动重算营养） | 接口就绪，DB 占位 |
| DELETE | `/api/diet/item/{item_id}` | 删除单条餐食（自动重算汇总） | 接口就绪，DB 占位 |
| GET | `/api/diet/today` | 当日饮食 + 总营养（首页核心接口） | 接口就绪，DB 占位 |

**请求体示例**：
```json
// POST /api/diet/add
{
  "meal_type": "lunch",
  "items": [
    {"food_id": 1, "grams": 200},
    {"custom_food_id": 5, "grams": 150}
  ]
}

// POST /api/food/custom
{ "name": "自制沙拉", "category": "蔬菜", "kcal_per_100g": 80, "protein_per_100g": 2, "carb_per_100g": 10, "fat_per_100g": 4 }
```

**响应示例**：
```json
// GET /api/diet/today
{
  "code": 0,
  "data": {
    "record_id": 123,
    "record_date": "2026-07-04",
    "summary": {"kcal": 800, "protein": 40, "carb": 100, "fat": 25},
    "groups": [
      {"meal_type": "breakfast", "items": [...], "subtotal_kcal": 400},
      {"meal_type": "lunch", "items": [...], "subtotal_kcal": 400},
      {"meal_type": "dinner", "items": [], "subtotal_kcal": 0},
      {"meal_type": "snack", "items": [], "subtotal_kcal": 0}
    ]
  }
}
```

**数据表（PG）**：`standard_food` / `user_custom_food` / `daily_diet_record` / `meal_item`，详见 `pg_orm.py`
**Redis 缓存**：`food_healing:food_search:{category}:{keyword}` → JSON，TTL 5 分钟

**注**：service 层 DB 操作用 `pass + # TODO` 占位（注释中给出完整预期 SQLAlchemy 查询），营养换算 / Redis 缓存 / 业务校验已写完整。

#### 消息通知 `/api/message`（Phase 5，全部需 Token）

| Method | Path | 说明 | 状态 |
|---|---|---|---|
| GET | `/api/message/list` | 分页获取消息（支持分类筛选 + 未读数） | 接口就绪，DB 占位 |
| PUT | `/api/message/{msg_id}/read` | 单条标记已读（owner 校验，幂等） | 接口就绪，DB 占位 |
| PUT | `/api/message/read-all` | 全部消息标记已读 | 接口就绪，DB 占位 |
| DELETE | `/api/message/clear` | 清空当前用户全部消息 | 接口就绪，DB 占位 |

**响应示例**：
```json
// GET /api/message/list?msg_type=remind&page=1&page_size=20
{
  "code": 0,
  "data": {
    "items": [
      {"id": 1, "msg_type": "remind", "title": "午餐提醒",
       "content": "该吃午饭啦", "is_read": 0, "create_time": "2026-07-04T12:00:00"}
    ],
    "total": 15, "page": 1, "page_size": 20, "unread_count": 3
  }
}
```

**数据表（PG）**：`system_message`（user_id FK, msg_type: remind/ai, is_read: 0/1）
**MQ 推送链路**：
- 生产者：`from app.db.rabbitmq_producer import push_message` → 发到路由键 `task.push.msg`
- 消费者：`app/tasks/message_task.py` 启动时 `start_message_consumer()`，监听 `task.push.msg.queue`，调 `message_service.create_message` 写库
- 未配置 `RABBITMQ_URL` 时 graceful 跳过（生产者返回 False，消费者直接 return）

**常量**（`app/constants.py`）：`MSG_TYPE_REMIND` / `MSG_TYPE_AI` / `MSG_TYPES` / `MSG_READ_UNREAD` / `MSG_READ_READ` / `ROUTING_KEY_PUSH_MSG` / `QUEUE_NAME_PUSH_MSG`

**注**：service 层 DB 操作用 `pass + # TODO` 占位（注释中给出完整预期 SQLAlchemy 查询），权限校验 / 返回结构 / 消息体 Pydantic 校验已写完整。

#### AI 营养师对话 + 每日简报 `/api/ai`（Phase 3，全部需 Token）

| Method | Path | 说明 | 状态 |
|---|---|---|---|
| POST | `/api/ai/chat` | 发送咨询问题，携带当日饮食上下文调百炼，返回回答并保存对话 | ✅ |
| GET | `/api/ai/chat/list` | 分页查询指定日期聊天历史（双用法：传 `record_date` 查单日 / 不传查分页） | ✅ |
| GET | `/api/ai/daily-summary` | 获取当天自动生成的营养分析简报（传 `report_date` 指定日期，默认当天） | ✅ |
| GET | `/api/ai/report/history` | 查看过往每日完整 AI 饮食报告（`page` + `page_size` 分页） | ✅ |

**请求体示例**：
```json
// POST /api/ai/chat
{ "content": "我今天主食吃太多了怎么办？", "query_date": "2026-07-04" }
// query_date 可选，默认当天；content 必填，1-500 字符
```

**响应示例**：
```json
// POST /api/ai/chat
{
  "code": 0,
  "data": {
    "reply": "今天你的早餐和午餐都包含了较多主食...",
    "query_date": "2026-07-04",
    "saved": true
  }
}

// GET /api/ai/chat/list?record_date=2026-07-04
{
  "code": 0,
  "data": {
    "record_date": "2026-07-04",
    "chat_list": [
      {"role": "user", "content": "...", "created_at": "..."},
      {"role": "assistant", "content": "...", "created_at": "..."}
    ]
  }
}

// GET /api/ai/daily-summary?report_date=2026-07-04
{
  "code": 0,
  "data": {
    "found": true,
    "report_date": "2026-07-04",
    "summary_short": "今天总能量略超目标，蛋白摄入不足...",
    "full_content": "# 每日营养简报\n\n## 一、营养总览\n..."
  }
}

// GET /api/ai/report/history?page=1&page_size=10
{
  "code": 0,
  "data": {
    "items": [
      {"report_date": "2026-07-04", "summary_short": "...", "created_at": "..."}
    ],
    "total": 5, "page": 1, "page_size": 10
  }
}
```

**核心调用链**：
```
POST /ai/chat
  → ai_service.chat_with_assistant(user_id, content, query_date)
  → _load_diet_data(user_id, query_date)       # PG 拉当日三餐 + 食材名 join
  → _load_user_target(user_id)                  # PG 拉营养目标
  → _load_chat_history(user_id, query_date)     # Mongo $slice 取最近 N 条对话
  → _build_diet_context()                       # 拼装上下文 Markdown
  → bailian_client.chat_with_diet_context()     # 调百炼 report 场景
  → _append_chat_history()                      # Mongo $push + $each + upsert 追加
```

**每日简报异步链路**：
```
APScheduler 每日 00:30 (tasks/run_scheduler.py)
  → 遍历 user 表 status=1 的全部 user_id
  → ai_service.trigger_daily_summary_task(user_id, today)
     ├─ MQ 就绪: publish_daily_summary_task → ai_daily_summary_queue → _handle_daily_summary_task → generate_daily_summary
     └─ MQ 未就绪: 直接 await generate_daily_summary（同步 fallback）
  → generate_daily_summary:
     - _load_diet_data + _load_user_target 拼上下文
     - chat_text(scene="report", max_tokens=1500)  # 显式覆盖避免截断
     - 写 Mongo ai_daily_report {user_id, report_date, full_content, summary_short, created_at}
     - 回写 Mongo ai_chat_history.daily_summary（upsert 补 chat_list=[] / created_at）
  → 推送 system_message (msg_type=ai): "你的 YYYY-MM-DD 营养简报已生成"
```

**关键常量**（`app/constants.py`）：
- `AI_CHAT_HISTORY_COLLECTION = "ai_chat_history"`（Mongo）
- `AI_DAILY_REPORT_COLLECTION = "ai_daily_report"`（Mongo）
- `AI_DAILY_SUMMARY_QUEUE = "ai_daily_summary_queue"`
- `AI_DAILY_SUMMARY_ROUTING_KEY = "task.ai.daily"`
- `NUTRITIONIST_SYSTEM_PROMPT`（营养师系统提示词，定义 AI 角色与回答风格）
- `AI_DAILY_SUMMARY_PROMPT`（每日简报模板，4 段 Markdown：营养总览/偏差分析/改善建议/推荐食谱）

**数据存储**：
- 对话历史 → Mongo `ai_chat_history` 集合，按 `{user_id, record_date}` 唯一键，`chat_list` 数组追加（`$push + $each`），`daily_summary` 字段存简报摘要
- 每日简报 → Mongo `ai_daily_report` 集合，按 `{user_id, report_date}` 唯一键，`full_content` 存完整 Markdown，`summary_short` 存前 200 字摘要
- 当日饮食数据 → PG `daily_diet_record` + `meal_item` + `standard_food` / `user_custom_food`（按 `breakfast < lunch < dinner < snack` 业务顺序排序）
- 用户营养目标 → PG `user_body_target`

**Mongo 操作要点**：
- 查询历史对话用 `$slice: -N` 投影，只取最近 N 条避免 token 溢出（默认 20 条）
- 追加对话用 `$setOnInsert`（首插时写 `created_at`）+ `$push: {chat_list: {$each: [...]}}` + `upsert=True`
- 简报回写 `ai_chat_history` 时同样用 `$setOnInsert` 补 `chat_list=[]` 与 `created_at`，避免后续聊天文档缺字段

**鉴权**：4 个接口全部通过 `get_current_user_id(request)` 取 user_id（int），无 Token 返回 401。

**注**：Mongo 未配置（`MONGO_URL` 为空）时所有读写操作 graceful 降级：
- `chat_with_assistant` 仍可调百炼返回回答，`saved=false`
- `get_chat_history_by_date` / `list_chat_history` 返回空列表
- `get_daily_summary` 返回 `found=false`
- `list_daily_reports` 返回空列表

#### 拍照识菜 `/api/camera`（阶段 6，全部需 Token）

| Method | Path | 说明 | 状态 |
|---|---|---|---|
| POST | `/api/camera/upload` | 上传菜品图片，下发异步识别任务，返回 task_id | ✅ 图片上传 + MQ/fallback |
| GET | `/api/camera/result?task_id=xxx` | 查询识别结果（pending/processing/done/failed） | ✅ Redis 任务状态 |
| GET | `/api/camera/logs?limit=50&skip=0` | 查询本人所有历史识别记录 | ✅ Mongo 持久化 |

**异步链路**：
```
POST /camera/upload
  → save_camera_image (Pillow 压缩到 1024px, 存 uploads/camera/)
  → Redis 任务状态 = pending
  → publish_recognize_task (RabbitMQ)
     ├─ MQ 就绪: ai_task 消费者接收 → recognize_dish → 写 Mongo → 更新 Redis = done
     └─ MQ 未就绪: asyncio.create_task fallback → 同样流程
GET /camera/result?task_id=xxx → 读 Redis 任务状态
GET /camera/logs → 读 Mongo camera_recognize_log 集合
```

**关键常量**（`app/constants.py`）：
- `AI_RECOGNIZE_QUEUE = "ai_recognize_queue"`
- `AI_RECOGNIZE_ROUTING_KEY = "task.ai.recognize"`
- `CAMERA_TASK_KEY_PREFIX = "food_healing:camera_task:"`（Redis，TTL 600s）
- `CAMERA_RECOGNIZE_LOG_COLLECTION = "camera_recognize_log"`（Mongo）
- `RECOGNIZE_DISH_SYSTEM_PROMPT`（Qwen-VL 识菜 prompt，强制 JSON 输出）

**数据流**：
- 图片：Pillow 压缩到最大边 1024px + JPEG quality 85，存 `uploads/camera/`，返回 `/static/camera/xxx.jpg`
- 任务状态：Redis `food_healing:camera_task:{task_id}`，TTL 10 分钟
- 历史记录：Mongo `camera_recognize_log` 集合，按 user_id 索引，按 created_at 倒序
- AI 调用：`utils/bailian_client.recognize_dish()` 内置 prompt + JSON 解析，复用 chat_multimodal 的主模型+降级机制

**MQ 消费者**（`app/tasks/ai_task.py`）：
- 进程内 asyncio 后台任务（main.py lifespan 启动）
- RABBITMQ_URL 为空时 graceful 跳过，camera_service 自动 fallback 到 asyncio.create_task
- prefetch_count=1，避免单进程 OOM
- 单消息处理失败不退出，记日志后 ack（任务最终状态由 _handle_recognize_task 更新为 failed）

**与现有 recognize 模块的关系**：
- 现有 `/api/recognize-dish`（Phase 1，asyncio.create_task + Redis TTL 10 分钟，无历史）保留不动
- 新增 `/api/camera/*`（阶段 6，MQ + Mongo 持久化 + 历史查询）作为升级版
- 前端可逐步迁移到 camera 接口

### 4.4 占位接口

`/api/preferences`、`/api/menu/*`、`/api/recommend/*`、`/api/leaderboard/*`、`/api/mood/*`、`/api/sport/*`、`/api/weekly-report/*`、`/api/voice-to-tray/*`、`/api/share-card/*`、`/api/admin/*` 均为 Phase 0 占位，返回 `501 Not Implemented` + `code=50100`。

## 5. 开发规范

### 5.1 代码风格

- **Python 版本**：≥ 3.11（用 `from __future__ import annotations` 启用 PEP 604）
- **行宽**：100（ruff 配置）
- **import 顺序**：stdlib → 第三方 → 本项目（app.*）
- **类型注解**：所有公共函数必加，私有可省
- **docstring**：模块级 + 公共函数必加，三引号，中文

### 5.2 分层约定

```
routes/   → 只做参数校验 + 调 service + 返回 success(data=)
services/ → 业务逻辑，抛 BizError(code, message)
models/   → ORM 模型 + Pydantic schemas
utils/    → 工具函数（auth/logger/bailian_client）
ai/       → AI 路由表
db/       → MQ 生产者（PG/Mongo/Redis 在 database.py）
```

**禁止**：
- routes 层直接操作数据库（必须走 service）
- service 层返回 BaseResponse（只抛 BizError 或返回 data）
- 业务代码硬编码模型名（必须 `get_route(scene)`）

### 5.3 AI 调用规范

```python
# ✅ 正确：用 bailian_client 统一入口
from app.utils.bailian_client import chat_text, chat_multimodal

reply = await chat_text("chat", messages)
result = await chat_multimodal("recognize", image_bytes, "识别菜品", "image/jpeg")

# ✅ SSE 流式仍用 services/chat_service.py（逻辑复杂，不迁移）
# ❌ 错误：业务代码直接 AsyncOpenAI(...)
```

**场景→模型路由**（`app/ai/router.py`）：

| scene | 平台 | 模型 | 降级 | 超时 |
|---|---|---|---|---|
| recognize | vl | qwen-vl-max | qwen-vl-plus | 40s |
| chat | bailian | qwen3.7-plus | qwen3.7-flash | 20s |
| report | bailian | qwen3.7-max | qwen3.7-plus | 30s |
| mood/summary/share_card | bailian | qwen3.7-flash | - | 10s |

### 5.4 数据库规范

**PostgreSQL（8 张关系表，全部在 `pg_orm.py`）**：

| 表 | 用途 | 关键字段 |
|---|---|---|
| `user` | 用户基础 | id BIGINT PK, nickname 唯一, password_hash, phone, theme, status |
| `user_body_target` | 身体 & 营养目标 | user_id FK CASCADE, height/weight/gender, target_type, daily_calorie + 三大营养素 |
| `standard_food` | 系统标准食材库 | category(主食/肉类/蔬菜/水果/饮品/零食), cal_per_100, 三大营养素, tag_color |
| `user_custom_food` | 用户自定义食材 | user_id FK CASCADE, 同 standard_food 结构 |
| `user_collect_food` | 用户收藏 | user_id FK CASCADE, food_id / custom_food_id 二选一, 联合唯一 |
| `daily_diet_record` | 每日饮食总记录 | user_id + record_date 联合唯一, total_calorie + 三大营养素 |
| `meal_item` | 单餐食物明细 | diet_record_id FK CASCADE, meal_type(breakfast/lunch/dinner/snack), weight, 三大营养素 |
| `system_message` | 系统消息 | user_id FK CASCADE, msg_type(remind/ai), is_read |

**MongoDB（3 个集合，启动自动创建）**：

| 集合 | 用途 | 关键字段 |
|---|---|---|
| `ai_chat_history` | AI 对话历史 | user_id, record_date, chat_list[{role, content, created_at}], daily_summary, created_at |
| `camera_recognize_log` | 拍照识菜日志 | user_id, image_url, food_list[{name, weight}], total_cal |
| `ai_daily_report` | AI 每日营养报告 | user_id, report_date, full_content, summary_short, created_at |

**Redis Key 规范**：

| Key 模式 | 类型 | TTL | 用途 |
|---|---|---|---|
| `user:token:{user_id}` | string | 7 天 | JWT 会话（强校验：中间件每请求比对 token 一致性，logout/改密后立即失效） |
| `user:collect:{user_id}` | set | - | 收藏食材 ID 集合 |
| `hot_food:cache` | hash | - | 热门食材缓存 |
| `verify:phone:{phone}` | string | 5 分钟 | 手机验证码（绑定手机号时） |

**注**：MongoDB 配置为可选，`MONGO_URL` 为空时 graceful 跳过（`mongo_db = None`）。所有时间字段为 `TIMESTAMP WITHOUT TIME ZONE`，业务代码传 naive datetime（如 `datetime.now(timezone.utc).replace(tzinfo=None)`）。

### 5.5 鉴权规范

- 白名单：`/api/auth/register`、`/api/auth/login`、`/api/health`、`/docs`、`/static/*`
- 其余 `/api/*` 必须带 `Authorization: Bearer <token>`
- 业务代码取 user_id：`get_current_user_id(request)`（中间件已注入 `request.state.user_id`，优先用缓存）

### 5.6 异常处理

```python
from app.exceptions import BizError, success, not_implemented
from app.models.schemas import ERR_PARAM_MISSING

# 业务错误
raise BizError(code=ERR_PARAM_MISSING, message="昵称不能为空", http_status=400)

# 占位接口
return not_implemented()  # 自动抛 501

# 成功响应
return success(data={"user": user}, message="昵称已更新")
```

## 6. 常用命令

```powershell
# 进入后端目录
cd d:\desktop\Trae\food-healing-demo\backend

# 一键安装/同步全部依赖（uv 自动管理虚拟环境）
uv sync

# === Phase 8 三进程独立启动（推荐）===
uv run fh-dev          # 开发模式 web 服务（热重载，单进程）
uv run fh-prod         # 生产模式 web 服务（4 worker，无热重载）
uv run fh-consumer     # RabbitMQ 消费者独立进程（消息推送 + 识菜）
uv run fh-scheduler    # APScheduler 定时任务独立进程（每日 00:30 AI 简报）
uv run fh-init-db      # 初始化 PG 表 + 种子数据
uv run fh-check-db     # 检查各表数据情况

# 等价原生命令（不通过 entry points）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
uv run python -m app.tasks.run_consumer
uv run python -m app.tasks.run_scheduler
uv run python -m app.scripts.init_db
uv run python -m app.scripts.check_data

# 跑测试（覆盖率 ≥ 80%）
uv run pytest

# 跑单个测试
uv run pytest tests/test_health.py -v
```

**部署提示**：
- 虚拟环境由 uv 自动管理（`.venv/`），无需手动 `python -m venv`
- 生产关闭 `--reload`，使用 `fh-prod` 多 worker
- 三条进程（web / consumer / scheduler）必须分开启动，可分别部署到不同容器
- 日志文件写入 `logs/app.log`，按日轮转，默认保留 14 天

## 7. 环境变量

见 `.env.example`。关键字段：

| 变量 | 必填 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | ✅ | 通义千问 VL（识图） |
| `BAILIAN_API_KEY` | ✅ | 阿里百炼（对话/周报/情绪） |
| `PG_DSN` | ✅ | PostgreSQL 连接串 |
| `REDIS_URL` | ✅ | Redis 连接串 |
| `MONGO_URL` | ❌ | MongoDB 连接串（空则跳过，graceful 降级） |
| `MONGO_DB` | 默认 `food_healing` | MongoDB 数据库名 |
| `RABBITMQ_URL` | ✅ | RabbitMQ 连接串，已启用 `amqp://guest:guest@118.178.229.21:5672/`（空则 graceful 跳过） |
| `OSS_ENDPOINT` | ✅ | MinIO endpoint |
| `JWT_SECRET` | ✅ | 生产必改 |
| `JWT_EXPIRE_HOURS` | 默认 168（7 天） | Redis 会话 TTL 同步此值 |
| `LOG_DIR` | 默认 `logs` | 日志文件目录（按日轮转） |
| `LOG_RETENTION_DAYS` | 默认 `14` | 日志保留天数 |
| `TIMEZONE` | 默认 `Asia/Shanghai` | APScheduler 时区，影响每日 AI 简报触发时点（00:30） |
| `NACOS_ENABLED` | 默认 false | 未部署跳过 |

## 8. 常见任务导航

| 我想... | 看哪里 |
|---|---|
| 加新 API | `routes/` 新建文件 + `main.py` 注册路由 |
| 加新 AI 场景 | `ai/router.py` 加 scene + `utils/bailian_client.py` 调用 |
| 改数据库模型 | `models/pg_orm.py`（PG 8 张表）；MongoDB 无 schema，直接读写 |
| 加中间件 | `middleware.py` + `setup_middlewares()` |
| 加错误码 | `models/schemas.py` 加常量 + 业务代码用 |
| 改配置 | `config.py` 加字段 + `.env.example` 同步 |
| 发 MQ 消息 | `from app.db.rabbitmq_producer import publish` 或便捷方法 `push_message` |
| 调百炼 | `from app.utils.bailian_client import chat_text, chat_multimodal` |
| 加消息推送 | `from app.db.rabbitmq_producer import push_message`（自动发到 task.push.msg） |
| 加常量 | `app/constants.py`（消息类型 / MQ 路由键 / AI prompt 模板 / DLX 死信配置） |
| 加快捷启动命令 | `pyproject.toml [project.scripts]` + `app/cli.py` 加函数 |
| 加定时任务 | `tasks/run_scheduler.py` 加 job（`AsyncIOScheduler.add_job`） |
| 改日志保留 | `config.py` 改 `LOG_RETENTION_DAYS`，或 `.env` 同步 |

## 9. 已知问题 + 待办

- **Phase 3 完成（AI 营养师对话 + 每日简报）**：4 个鉴权接口 + Mongo 双集合（`ai_chat_history` / `ai_daily_report`）+ MQ 每日简报异步任务 + APScheduler 每日 00:30 自动触发。已通过 401 拦截、登录、对话、历史、简报、报告 6 项验收测试。Mongo 未连接时全部接口 graceful 降级
- **Phase 4 完成**：食材库 + 每日三餐饮食记录模块（8 个鉴权路由 + Redis 搜索缓存 + 营养换算）。service 层 DB 操作用 `pass + # TODO` 占位，注释中给出完整预期 SQLAlchemy 查询，待表落地后替换
- **Phase 5 完成**：消息通知模块（4 个鉴权路由 + MQ 推送链路）。`SystemMessage` 表已存在于 `pg_orm.py`，service 层 DB 操作同样用 `pass + # TODO` 占位
- **Phase 8 完成**：uv 包管理改造 + 多进程启动 + APScheduler 定时简报 + MQ 容错增强。详见第 11 节
- **鉴权强化完成**：`AuthMiddleware` 已加 Redis 会话强校验（`validate_session`），logout/改密后旧 token 立即失效；`update_nickname` 加 `IntegrityError` 兜底；`upload_avatar` 旧头像删除路径修正
- **Phase 3 用户中心**：user_service 占位待迁移（与 Phase 3 AI 模块独立，未冲突）、菜单/推荐/排行榜、过敏/忌口（preferences.py 占位）
- **Phase 6+**：情绪/运动/周报/语音转餐盘/分享卡片
- **RabbitMQ**：✅ 已启用（`amqp://guest:guest@118.178.229.21:5672/`，交换机 `food_healing` DIRECT durable）。消息推送消费者（`tasks/message_task.py`，Phase 8 已加 DLX + 重试）、拍照识菜消费者（`tasks/ai_task.py` 监听 `task.ai.recognize`）、每日简报消费者（`tasks/ai_task.py` 监听 `task.ai.daily`，Phase 3 新增）均已在 lifespan 启动；Phase 8 起也支持独立进程 `fh-consumer` 启动。`guest/guest` 默认账号已开放远程访问，生产建议改专用账号
- **Nacos**：未部署，`NACOS_ENABLED=false` 跳过
- **MongoDB**：`MONGO_URL` 为空时 graceful 跳过。Phase 3 已完成 `ai_chat_history` / `ai_daily_report` 集合的读写逻辑，配置 `MONGO_URL` 后即可启用对话持久化与每日简报

## 10. 协作约定

- 改动后端 API **必须同步更新前端** `frontend-v2/src/lib/api.js`
- 新增场景必须在 `ai/router.py` 注册，业务代码不硬编码模型名
- 数据库 schema 变更必须写迁移脚本（`scripts/`）
- 提交前跑 `uv run pytest` 确保测试通过

## 11. Phase 8 详细说明（uv 包管理 + 多进程 + APScheduler + MQ 容错）

### 11.1 uv 包管理结构

- `pyproject.toml` 是唯一依赖来源（已删除旧 `requirements.txt`）
- 用 hatchling 作为构建后端，`[tool.hatch.build.targets.wheel] packages = ["app"]` 显式指定只打包 app 目录，避免 flat-layout 误把 `data/` `logs/` `uploads/` 当作包
- `[tool.uv] package = true` 让 uv 把本项目当作可安装包，这样 `[project.scripts]` 的 entry points 才会被真正安装到 `.venv/Scripts/`
- `uv.lock` 锁定全部依赖版本，部署执行 `uv sync` 即可复现完全一致的环境
- dev 依赖放在 `[dependency-groups] dev = [...]`，默认不安装到生产环境；`uv sync --dev` 才装

### 11.2 快捷启动命令（`[project.scripts]`）

| 命令 | 入口 | 用途 |
|---|---|---|
| `uv run fh-dev` | `app.cli:dev` | 开发模式 web 服务（热重载，单进程） |
| `uv run fh-prod` | `app.cli:prod` | 生产模式 web 服务（4 worker，无热重载） |
| `uv run fh-consumer` | `app.cli:consumer` | RabbitMQ 消费者独立进程（消息推送 + 识菜） |
| `uv run fh-scheduler` | `app.cli:scheduler` | APScheduler 定时任务独立进程 |
| `uv run fh-init-db` | `app.cli:init_db` | 初始化 PG 表 + 种子数据 |
| `uv run fh-check-db` | `app.cli:check_db` | 检查各表数据情况 |

等价原生命令：`uv run python -m app.tasks.run_consumer`、`uv run python -m app.tasks.run_scheduler` 等。

### 11.3 日志文件持久化（`utils/logger.py`）

- 双 handler：`StreamHandler(sys.stdout)` + `TimedRotatingFileHandler`
- 文件路径：`{LOG_DIR}/app.log`（默认 `logs/app.log`）
- 轮转策略：每天午夜切一份，文件名后缀 `app.log.YYYY-MM-DD`
- 保留天数：`LOG_RETENTION_DAYS`（默认 14，超期自动删除）
- 编码：UTF-8（避免中文乱码）
- 时区：本地时间（`utc=False`，与 PG `TIMESTAMP WITHOUT TIME ZONE` 一致）

### 11.4 APScheduler 定时任务（`tasks/run_scheduler.py`）

- 调度器：`AsyncIOScheduler(timezone=settings.TIMEZONE)`（默认 `Asia/Shanghai`）
- 触发时点：每日 00:30（`CronTrigger(hour=0, minute=30)`，避开 00:00 整点任务密集期）
- 任务内容：遍历 `user` 表 status=1 的全部 user_id，逐个调 `ai_service.trigger_daily_summary_task`
  - 优先投递 MQ（`task.ai.daily` 路由键，队列 `ai_daily_summary_queue`）
  - MQ 不可用则 fallback 同步生成（写 Mongo `ai_daily_report` 集合）
- 容错：
  - 单用户失败记日志后继续下一个，不阻塞
  - 启动前 ping PG，DB 不通直接退出
  - 启动前 init_producer（trigger_daily_summary_task 内部 publish 需要）
  - `max_instances=1` + `coalesce=True` 防止任务重叠
  - `misfire_grace_time=600` 错过 10 分钟内仍补跑
- 信号处理：SIGINT（Windows）/ SIGINT+SIGTERM（Unix）优雅退出
- 独立进程运行：`uv run fh-scheduler` 或 `uv run python -m app.tasks.run_scheduler`

### 11.5 RabbitMQ 消费容错增强（`tasks/message_task.py`）

**死信队列（DLX）结构**：
- 死信交换机：`DLX_EXCHANGE = "food_healing_dlx"`（fanout）
- 死信队列：`DLX_QUEUE_PUSH_MSG = "task.push.msg.dlq"`
- 主队列 `task.push.msg.queue` 声明 `x-dead-letter-exchange = food_healing_dlx`，nack(requeue=False) 时消息进入 DLQ

**重试策略**（`_process_message`）：
- 通过 `message.headers["x-retry"]` 跟踪重试次数（默认 0）
- 失败时若 `retry_count < MQ_MAX_RETRIES`（默认 3）：
  - 退避延迟 `min(5 * 2^retry, 60)` 秒（5s/10s/20s，上限 60s）
  - `await asyncio.sleep(delay)` 后 `message.nack(requeue=True)` 重投
- 达到最大重试次数：`message.nack(requeue=False)` 进入死信队列
- 校验类失败（msg_type 不合法、JSON 解析失败）：直接 ack，不重投（重投也不会成功）

**日志规范**：每条消息消费全流程打印 5 条结构化日志：
1. `message_consumer_msg_received`（msg_id / retry / body_preview）
2. `message_consumer_ok` 或 `message_consumer_failed`（耗时 / 错误）
3. `message_consumer_retry_scheduled`（next retry / delay）或 `message_consumer_dlq_routed`（达到上限进 DLQ）
4. `message_consumer_ack_failed`（ack/nack 异常时）

**常量**（`app/constants.py`）：
- `DLX_EXCHANGE = "food_healing_dlx"`
- `DLX_QUEUE_PUSH_MSG = "task.push.msg.dlq"`
- `MQ_MAX_RETRIES = 3`
- `MQ_RETRY_BASE_DELAY = 5`

### 11.6 独立消费者进程（`tasks/run_consumer.py`）

- 注册全部 MQ 消费者（目前 `message_task` + `ai_task`），未来新增消费者在此注册即可
- 信号处理：SIGINT/SIGTERM 触发 `stop_event.set()`，优雅关闭连接
- Windows 平台用 `signal.signal()` fallback（不支持 `loop.add_signal_handler`）
- 启动方式：`uv run fh-consumer` 或 `uv run python -m app.tasks.run_consumer`

### 11.7 验收对照

| 验收项 | 状态 | 实现位置 |
|---|---|---|
| `uv sync` 一键装好全部依赖 | ✅ | `pyproject.toml` + `uv.lock` |
| 三条进程可分开通过 uv run 正常启动 | ✅ | `app/cli.py` + `tasks/run_consumer.py` + `tasks/run_scheduler.py` |
| 全接口统一异常返回 | ✅ | `app/exceptions.py` + `middleware.py` 全局处理器 |
| 完整日志记录 | ✅ | `utils/logger.py` 双 handler + 文件轮转 |
| 每日自动 AI 简报推送异步流程完整跑通 | ✅ | `tasks/run_scheduler.py` → `ai_service.trigger_daily_summary_task` → MQ（`task.ai.daily` 路由键）→ `tasks/ai_task._handle_daily_summary_task` → `generate_daily_summary` 写 Mongo `ai_daily_report` + 推送 `system_message`（msg_type=ai） |
