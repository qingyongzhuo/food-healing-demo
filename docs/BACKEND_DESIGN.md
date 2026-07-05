# 食愈校园 — 后端技术设计文档

> 版本：v2.2（Phase 0 联调对齐版，覆盖 P0–P3 全功能；本版统一字段为 snake_case + RESTful 路径 + 合并 AI 对话请求体）
> 日期：2026-07-03
> 维护：后端组
> 状态：**设计文档**（本文档描述目标架构，当前实现进度以 `backend/CLAUDE.md` 为准）
> **实现差异**：当前实现使用 PostgreSQL 作为唯一关系型数据库（8 张表全部在 PG），未使用 MySQL。MongoDB 用于 AI 对话历史等非结构化数据。RabbitMQ 已确认选型。Nacos 为可选组件。
> 上一版：v2.1（v1.0 → v2.0 升级基础设施与双 AI 平台；v2.1 切换 uv 管理并补充生产服务器信息；v2.2 Phase 0 联调解决 16 处契约不一致，详见 `docs/接口契约统一.md`）
> 配套文档：`docs/后端技术规范.md`（工程规范细则）、`docs/接口契约统一.md`（v2.2 唯一契约源）、`backend/CLAUDE.md`（当前实现导航）

---

## 1. 概述

### 1.1 项目定位（V2 升级）

"食愈校园"从初赛的 **AI 食堂搭子** 升级为 **"会成长、会记忆、会陪伴的校园饮食伙伴"**：

- **会成长**：长期沉淀用户习惯（口味/过敏/目标/健康档案/AI 人格），用得越久越懂你；
- **会记忆**：每次 AI 对话都基于用户画像 + 最近 N 轮对话上下文，模型像"记得"用户；
- **会陪伴**：情绪日记 + AI 治愈话语 + 餐次提醒 + 周报陪伴，把饮食工具变成校园生活伙伴。

后端仍为 **Python + FastAPI** 单体内聚服务（单校单食堂、用户 <1 万，无需微服务），但基础设施从 SQLite 升级为 **PostgreSQL + Redis + MinIO + RabbitMQ + Nacos（可选）** 全套，AI 从单模型升级为 **通义千问 VL + 百练双平台多模型路由**。

### 1.2 技术栈（V2）

| 层 | 选型 | 用途 |
|---|---|---|
| Web 框架 | FastAPI 0.115+ | 异步、OpenAPI、Pydantic 校验 |
| ASGI | uvicorn[standard]（开发）/ gunicorn + uvicorn workers（生产） | |
| AI 视觉 | 阿里通义千问 VL（dashscope SDK） | 拍照识菜、外卖截图识别 |
| AI 对话 | 阿里百练平台（openai SDK 改 base_url，兼容 OpenAI 接口） | 对话/周报/情绪/陪伴 |
| 关系库 | PostgreSQL 16 | 用户、社交、评价、菜单、过敏、**user_habits**（唯一关系库，含时序 JSONB） |
| 文档库 | MongoDB | AI 对话历史、识图日志、每日简报（可选，空则 graceful 降级） |
| 缓存 | Redis 7 | 识图结果缓存、对话短期上下文、热门菜 ZSET、限流计数、会话 |
| 对象存储 | MinIO（S3 兼容） | 原图、分享卡片图、头像 |
| 消息队列 | RabbitMQ | 识图异步化、消息推送、每日简报生成 |
| 配置中心 | Nacos 2.x（可选） | 食堂菜单/推荐策略/AI prompt 模板动态下发（**单服务不做服务注册**） |
| 限流 | slowapi | 防止 AI 接口被滥用 |
| 配置 | pydantic-settings + python-dotenv | 环境变量管理 |
| 图片处理 | Pillow | 校验、压缩、格式转换 |

> **模型名说明**：本文档中所有 `qwen-vl-max-latest`、`qwen3.7-plus`、`qwen3.7-max`、`qwen3.7-flash` 等模型名，**均以阿里云百炼控制台最新可用为准**。代码中模型名集中在 `app/config.py`，切换只改配置。

### 1.3 设计原则（V2）

1. **最小改动**：前端 `matcher()`、`calcNutrition()`、`mealDisplay` 等纯前端逻辑**保留不动**，后端只新增/升级接口。
2. **生产就绪**：统一响应、统一错误码、结构化日志、限流、超时重试、配置外置、双 API Key 管理。
3. **基础设施合理用，不堆砌**：每项组件都有明确职责，OSS 存图、MQ 削峰、Redis 缓存、MySQL/Pg 分工、Nacos 配置中心。
4. **数据量假设**：单校单食堂、用户 <1 万、菜品库 ~50 量级（静态扩展至 ~200）、单用户日记录 <50 条、周报 7 天聚合。**不涉及**全表扫描或批量更新，无需特别评估。
5. **性能优先级**：先并发度 → 再缓存 → 再批处理。AI 调用是慢操作（VL 1–4s，文本 0.5–3s），靠异步 MQ + Redis 缓存 + 并发信号量应对。
6. **记忆机制**：长期记忆（MySQL `user_habits`）+ 短期记忆（Redis 1h TTL）双层架构，每次对话拼进 system prompt。

---

## 2. 系统架构

### 2.1 架构总览（ASCII）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              浏览器（用户）                              │
│   Vue3(CDN) + Tailwind(CDN) + 自定义 CSS（纯静态）                      │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  菜盘管理(localStorage)  matcher()  addFood()                   │   │
│   │  generateAiText() ──→ /api/chat(SSE)  PWA 离线                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└──────────────┬───────────────────────────────┬──────────────────────────┘
               │ HTTP/JSON + SSE                │ OSS 上传(预签名URL)
               ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI 单体内聚后端（uvicorn/gunicorn）             │
│                                                                         │
│  ┌─── Routes 层 ─────────────────────────────────────────────────────┐  │
│  │ recognize / chat(SSE) / recommend / weekly-report                 │  │
│  │ preferences / menu / leaderboard / mood / health / sport          │  │
│  │ share-card / voice-to-tray / admin/*                              │  │
│  └─────────────────────────┬─────────────────────────────────────────┘  │
│  ┌─── Services 层 ─────────▼──────────────────────────────────────────┐  │
│  │ Recognize / Chat / Recommend / Report / Habit / Mood              │  │
│  │ Health / Sport / Share / Voice / Leaderboard / Menu / Admin       │  │
│  └────┬─────────────┬──────────────┬───────────────┬────────────┬────┘  │
│  ┌────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐ ┌──────▼─────┐ ┌─────▼────┐  │
│  │ AI 适配器  │ │ Repo 层   │ │ Redis 客户端 │ │  Nacos 客户端│ │ MQ 生产者 │  │
│  │ VL+百练   │ │ MySQL+Pg  │ │  缓存/限流   │ │  配置下发    │ │ 异步任务  │  │
│  └────┬──────┘ └────┬─────┘ └──────┬──────┘ └────────────┘ └─────┬────┘  │
│  ┌────▼──────────────────────────────────────────────────────────▼────┐  │
│  │  中间件：CORS / 限流(slowapi) / 请求日志 / 错误处理 / 鉴权           │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└────────┬──────────────┬──────────────┬──────────────┬─────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
   │通义千问VL  │  │ 阿里百练   │  │ 阿里云 OSS │  │   Nacos   │
   │ dashscope │  │ OpenAI兼容│  │ 图存储     │  │ 配置中心   │
   │ qwen-vl-  │  │ qwen3.7-  │  └───────────┘  └───────────┘
   │ max/plus  │  │ plus/max/ │
   └───────────┘  │ flash     │
                  └───────────┘
         │
         ▼
   ┌────────────────────────────────────────────────────────┐
   │  MQ（识图异步/周报生成/定时推送）                       │
   │  Worker 消费 → 调 VL/百练 → 写 Redis/MySQL/Pg          │
   └────────────────────────────────────────────────────────┘
         │
         ▼
   ┌────────────────┐   ┌──────────────────────┐
   │  MySQL 8.0     │   │ PostgreSQL 16         │
   │ users / habits │   │ nutrition_log(JSONB)  │
   │ socials / menu │   │ weekly_report 分析    │
   │ allergies      │   │ 窗口函数聚合          │
   └────────────────┘   └──────────────────────┘
```

### 2.2 数据流示例：拍照识菜（异步化 V2）

```
用户选图
  → 前端校验大小(≤5MB) + 压缩
  → POST /api/recognize-dish (multipart/form-data)
  → 后端校验文件 → 计算 image_hash
  → Redis 查 hash 缓存 → 命中直接返回结果（省钱）
  → 未命中：上传 OSS → 投递 MQ 任务 → 返回 {task_id}
  → 前端轮询 GET /api/recognize/result/{task_id}
  → MQ Worker 消费 → 调通义千问 VL(qwen-vl-max-latest)
  → 失败降级 qwen-vl-plus
  → VL 返回 → foods 库模糊匹配 → 写 Redis 缓存(hash→结果) → 写 MySQL 识图记录
  → 前端轮询命中 → 返回结构化 Dish + alternatives
  → 前端 addFood(dish) 入盘
```

### 2.3 数据流示例：AI 对话（SSE + 双层记忆）

```
用户问"我今天蛋白够不够"
  → 前端 POST /api/chat (Accept: text/event-stream)
  → 后端取 user_habits（长期记忆，MySQL）
  → 后端取 Redis 最近 N 轮对话（短期记忆，1h TTL）
  → 拼装 system prompt = 习惯摘要 + 最近对话 + 营养上下文
  → 路由模型：日常对话+多模态 → qwen3.7-plus
  → 百练流式调用（OpenAI SDK 改 base_url）
  → 逐 token SSE 推回前端
  → 同时把本轮 Q/A 追加写 Redis 短期记忆
  → 异步触发 conversation_summary 摘要更新（每 N 轮一次，回写 user_habits）
```

---

## 3. 后端目录结构

```
food-healing-demo/
├── index.html
├── js/
├── css/
└── docs/
    └── BACKEND_DESIGN.md          # 本文档

backend/                            # 后端工程
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app 实例、中间件挂载、路由注册
│   ├── config.py                  # pydantic-settings 配置（双 API Key + Nacos）
│   ├── deps.py                    # 依赖注入（DB session、user_id、Redis、Nacos）
│   ├── schemas/                   # Pydantic 模型（输入/输出契约）
│   │   ├── common.py             # 统一响应、分页、错误码
│   │   ├── dish.py               # Dish, RecognizeResult, RecognizeTask
│   │   ├── chat.py               # ChatRequest, ChatChunk
│   │   ├── meal.py               # TrayItem, MealPlan, NutritionSummary
│   │   ├── preference.py         # UserPreferences, UserHabits
│   │   ├── report.py             # WeeklyReport, DailySummary
│   │   ├── menu.py               # CanteenMenu, MenuItem
│   │   ├── leaderboard.py        # LeaderboardEntry
│   │   ├── mood.py               # MoodLog
│   │   ├── health.py             # HealthProfile
│   │   ├── sport.py              # SportRecord
│   │   └── share.py              # ShareCard
│   ├── routes/                    # 路由层（薄，只做参数校验 + 调 service）
│   │   ├── recognize.py          # POST /api/recognize-dish, GET /api/recognize/result/{task_id}
│   │   ├── chat.py               # POST /api/chat（SSE）
│   │   ├── recommend.py          # GET  /api/recommend
│   │   ├── report.py             # GET  /api/weekly-report
│   │   ├── preference.py         # POST /api/preferences
│   │   ├── menu.py               # GET  /api/menu
│   │   ├── leaderboard.py        # GET  /api/leaderboard
│   │   ├── mood.py               # POST /api/mood
│   │   ├── health.py             # GET/POST /api/health/profile
│   │   ├── sport.py             # GET/POST /api/sport/records (v2.2 改路径)
│   │   ├── share.py             # POST /api/share-card (v2.2 改方法)
│   │   ├── voice.py             # POST /api/voice-to-tray
│   │   └── admin.py             # B 端：/api/admin/*
│   ├── services/                  # 业务逻辑层
│   │   ├── recognize_service.py
│   │   ├── chat_service.py
│   │   ├── recommend_service.py
│   │   ├── report_service.py
│   │   ├── habit_service.py      # user_habits 读写、摘要生成
│   │   ├── mood_service.py
│   │   ├── health_service.py
│   │   ├── sport_service.py
│   │   ├── share_service.py
│   │   ├── voice_service.py
│   │   ├── leaderboard_service.py
│   │   ├── menu_service.py
│   │   └── admin_service.py
│   ├── ai/                        # AI 适配层（V2 新增双平台）
│   │   ├── __init__.py
│   │   ├── vl_client.py          # 通义千问 VL 调用（dashscope SDK）
│   │   ├── bailian_client.py     # 百练调用（openai SDK 改 base_url，流式）
│   │   ├── router.py             # 多模型路由：场景→模型
│   │   └── prompts.py            # Prompt 模板（可被 Nacos 动态下发覆盖）
│   ├── data/                      # 数据访问层（V2 拆 MySQL + Pg）
│   │   ├── __init__.py
│   │   ├── mysql_db.py           # MySQL 连接池（aiomysql）
│   │   ├── pg_db.py               # PostgreSQL 连接池（asyncpg）
│   │   ├── redis_client.py        # Redis 连接（redis-py async）
│   │   ├── oss_client.py         # OSS 上传/预签名 URL
│   │   ├── nacos_client.py       # Nacos 配置读取 + 监听
│   │   ├── mq_producer.py        # MQ 投递
│   │   └── repos/
│   │       ├── user_repo.py      # MySQL：users
│   │       ├── habit_repo.py     # MySQL：user_habits（重点）
│   │       ├── social_repo.py    # MySQL：社交关系
│   │       ├── menu_repo.py      # MySQL：canteen_menu
│   │       ├── allergy_repo.py   # MySQL：allergies
│   │       ├── rating_repo.py    # MySQL：菜品评价
│   │       ├── mood_repo.py      # MySQL：mood_logs
│   │       ├── health_repo.py    # MySQL：health_profiles
│   │       ├── sport_repo.py     # MySQL：sport_records
│   │       ├── nutrition_repo.py # PostgreSQL：nutrition_log（时序）
│   │       └── report_repo.py    # PostgreSQL：weekly_reports + 窗口函数
│   ├── middlewares/
│   │   ├── error_handler.py      # 全局异常 → 统一响应
│   │   ├── request_log.py        # 请求日志（含 request_id）
│   │   └── auth.py               # 鉴权（P0 简易 token，后续可扩展）
│   ├── workers/                  # MQ 消费者（V2 新增）
│   │   ├── __init__.py
│   │   ├── recognize_worker.py   # 识图异步任务
│   │   ├── report_worker.py      # 周报生成
│   │   └── push_worker.py        # 定时餐次提醒
│   └── utils/
│       ├── image.py              # 图片校验、压缩、base64、hash
│       └── time.py               # ISO8601/时区处理
├── data/
│   └── foods.json                # 菜品库（从前端 FOODS_DATA 搬迁并扩展）
├── tests/
├── .env.example                  # 含双 Key：DASHSCOPE_API_KEY、BAILIAN_API_KEY
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 4. 数据模型（Pydantic Schema）

> **v2.2 统一**：所有字段 snake_case（Pydantic 默认即可，无需 `alias` 转换）。前端 JS 调用时不转 camelCase，保持一致。
> 字段命名与前端 `foodTray` 中 item 完全对齐（`id/name/category/unit/kcal/protein/carb/fat`）。
> 完整字段表见 `docs/接口契约统一.md` §4。

### 4.1 通用

```python
# schemas/common.py
class ApiResponse(BaseModel):
    code: int = 0            # 0 成功，非 0 见错误码表
    message: str = "ok"
    data: Any | None = None

class ErrorDetail(BaseModel):
    code: int
    message: str
    detail: str | None = None
```

### 4.2 菜品 Dish

```python
# schemas/dish.py
class Dish(BaseModel):
    id: str                  # 预置库 id（如 f001）；识图未命中则 r+时间戳
    name: str
    category: Literal["主食","肉类","蔬菜","蛋奶","汤品","水果"]
    unit: str                # 如 "份(200g)"
    kcal: float
    protein: float
    carb: float
    fat: float

class RecognizeResult(Dish):
    confidence: float        # 0–1，VL 识别置信度
    matched: bool            # 是否命中预置菜品库
    alternatives: list[Dish] = []   # 多候选（最多 3 个）

class RecognizeTask(BaseModel):
    task_id: str             # 异步任务 ID（rec_ 前缀）
    status: Literal["pending","processing","done","failed"]
    progress: int = 0        # 0-100 百分比（v2.2 新增）
    dish: RecognizeResult | None = None     # done 时返回（v2.2 改字段名 dish，原 result）
    error: str | None = None               # failed 时返回（v2.2 新增）
```

### 4.3 菜盘 / 餐次 / 营养

```python
# schemas/meal.py
class TrayItem(Dish):
    tray_id: str              # 前端生成，后端只读（v2.2 改 snake_case）
    is_custom: bool = False  # v2.2 改 snake_case

class NutritionSummary(BaseModel):
    kcal: float
    protein: float
    carb: float
    fat: float

class MealPlan(BaseModel):
    breakfast: list[TrayItem] = []
    lunch: list[TrayItem] = []
    dinner: list[TrayItem] = []
    nutrition: NutritionSummary
    missing_categories: dict[str, list[str]] = {}  # v2.2 改 snake_case
```

### 4.4 对话

```python
# schemas/chat.py
class ChatMessage(BaseModel):
    role: Literal["user","assistant","system"]
    content: str

class ChatContext(BaseModel):
    """v2.2 合并前后端契约：context 嵌套"""
    food_tray: list[dict] = []          # [{name, category, kcal}] 摘要
    mode: Literal["daily","fitness","weight_loss"] = "daily"
    nutrition: NutritionSummary | None = None
    mode_target: NutritionSummary | None = None

class ChatRequest(BaseModel):
    """v2.2 合并方案：user_id + persona + messages + context
    user_habits 后端基于 user_id 自取，前端不传。"""
    user_id: str
    persona: Literal["canteen_aunt","senior_brother","senior_sister"] = "canteen_aunt"
    messages: list[ChatMessage] = []      # 最近 6 条，作为 fallback（主取 Redis 短期记忆）
    context: ChatContext | None = None

class ChatChunk(BaseModel):
    # SSE 单帧
    delta: str
    done: bool = False
```

### 4.5 用户偏好 + 用户习惯（V2 重点）

```python
# schemas/preference.py
class UserPreferences(BaseModel):
    """过敏/忌口/人设（前端表单写入，存 user_habits 子字段）"""
    user_id: str                                  # v2.2 改 snake_case
    allergens: list[str] = []          # ["花生","海鲜"]
    dislikes: list[str] = []           # ["香菜"]
    goal: Literal["daily","fitness","weight_loss"] = "daily"
    daily_kcal_target: int | None = None          # v2.2 改 snake_case
    persona: Literal["canteen_aunt","senior_brother","senior_sister"] = "canteen_aunt"  # v2.2 新增

class UserHabits(BaseModel):
    """用户习惯全量（user_habits 表 ORM 映射）"""
    user_id: str                                  # v2.2 改 snake_case
    taste_preferences: list[str] = []             # v2.2 改 snake_case
    allergens: list[str] = []
    dislikes: list[str] = []
    dietary_goal: Literal["daily","fitness","weight_loss","muscle_gain"] = "daily"  # v2.2 改 snake_case
    meal_preferences: dict = {}                   # v2.2 改 snake_case
    emotion_pattern: str | None = None            # v2.2 改 snake_case
    health_profile: dict = {}                     # v2.2 改 snake_case
    ai_personality: Literal["canteen_aunt","senior_brother","senior_sister"] = "canteen_aunt"  # v2.2 改 snake_case
    conversation_summary: str | None = None       # v2.2 改 snake_case
    recent_moods: list[dict] = []                 # v2.2 新增（最近 30 条情绪）
    recent_nutrition_trends: list[dict] = []      # v2.2 新增（最近 30 天营养趋势）
    mentioned_facts: list[dict] = []              # v2.2 新增（对话抽取的事实）
    updated_at: str                               # v2.2 改 snake_case, ISO8601
```

### 4.6 周报

```python
# schemas/report.py
class DailySummary(BaseModel):
    date: str                          # YYYY-MM-DD
    kcal: float
    protein: float
    carb: float
    fat: float
    kcal_target: float                 # v2.2 改 snake_case
    hit: bool                          # 是否在 90–110% 区间

class WeeklyReport(BaseModel):
    user_id: str                       # v2.2 改 snake_case
    week_start: str                   # v2.2 改 snake_case
    week_end: str                      # v2.2 改 snake_case
    daily: list[DailySummary]          # 7 条
    avg_kcal: float                    # v2.2 改 snake_case
    hit_days: int                      # v2.2 改 snake_case
    trend: Literal["up","down","flat"]
    ai_summary: str                    # v2.2 改 snake_case, AI 生成的周报总结（qwen3.7-max）
```

### 4.7 食堂菜单

```python
# schemas/menu.py
class MenuItem(Dish):
    price: float | None = None
    available: bool = True
    station: str | None = None         # 出餐窗口
    is_recommended: bool = False       # v2.2 新增：是否推荐（合并前端 recommended 字段）

class CanteenMenu(BaseModel):
    canteen: str                       # "main" / "east"
    date: str                          # YYYY-MM-DD
    breakfast: list[MenuItem] = []
    lunch: list[MenuItem] = []
    dinner: list[MenuItem] = []
```

### 4.8 榜单

```python
# schemas/leaderboard.py
class LeaderboardEntry(BaseModel):
    rank: int
    anonymous_name: str                # 如 "同学#A3F2"，v2.2 改 snake_case
    score: float                       # 营养均衡分
    hit_days: int                      # v2.2 改 snake_case
    mode: str
```

### 4.9 情绪日记

```python
# schemas/mood.py
class MoodLog(BaseModel):
    id: str
    user_id: str                       # v2.2 改 snake_case
    mood: Literal["happy","calm","neutral","sad","stressed"]
    note: str = ""
    created_at: str                    # v2.2 改 snake_case, ISO8601
    ai_comfort: str | None = None      # v2.2 改 snake_case, AI 治愈话语（qwen3.7-flash）
    suggestion: str | None = None     # v2.2 新增：可选建议（合并前端字段）
```

### 4.10 健康档案

```python
# schemas/health.py
class HealthProfile(BaseModel):
    user_id: str                       # v2.2 改 snake_case
    gender: Literal["male","female","other"] | None = None
    age: int | None = None
    height_cm: float | None = None     # v2.2 改 snake_case
    weight_kg: float | None = None     # v2.2 改 snake_case
    bmi: float | None = None
    activity_level: Literal["low","medium","high"] = "medium"  # v2.2 改 snake_case
    bmr: float | None = None           # 基础代谢（Mifflin-St Jeor）
    daily_kcal_target: int | None = None  # v2.2 改 snake_case
    updated_at: str                    # v2.2 改 snake_case
```

### 4.11 运动记录（V2 新增）

```python
# schemas/sport.py
class SportRecord(BaseModel):
    id: str
    user_id: str                       # v2.2 改 snake_case
    date: str                          # YYYY-MM-DD
    steps: int                         # 步数
    duration_min: int                  # v2.2 改 snake_case, 运动时长
    kcal_burned: float                 # v2.2 改 snake_case, 消耗热量
    kcal_quota: float                  # v2.2 改 snake_case, 换算的饮食配额（可多吃多少）
    source: Literal["manual","health_kit","mi_band"] = "manual"
    created_at: str                    # v2.2 改 snake_case
```

### 4.12 分享卡片（V2 新增）

```python
# schemas/share.py
class ShareCard(BaseModel):
    card_id: str                       # v2.2 改 snake_case
    user_id: str                       # v2.2 改 snake_case
    date: str
    nutrition: NutritionSummary
    dish_images: list[str] = []        # v2.2 改 snake_case, OSS URL
    card_image_url: str                # v2.2 改 snake_case, 生成的卡片图 OSS URL
    ai_comment: str                    # v2.2 改 snake_case, AI 生成的一句话点评
    created_at: str                     # v2.2 改 snake_case
```

---

## 5. 数据库表设计（V2 重点）

### 5.1 MySQL vs PostgreSQL 分工

| 数据 | 库 | 理由 |
|---|---|---|
| users（用户基础） | MySQL | 强一致、关系型 |
| **user_habits**（用户习惯） | MySQL | 单行读写、JSONB 字段 |
| social_relations（社交） | MySQL | 关系查询 |
| menu_items（食堂菜单） | MySQL | 关系型，Nacos 下发后落库 |
| allergies（过敏原字典） | MySQL | 字典表 |
| dish_ratings（菜品评价） | MySQL | 关系型 |
| mood_logs（情绪日记） | MySQL | 简单 CRUD |
| health_profiles（健康档案） | MySQL | 单用户单行 |
| sport_records（运动记录） | MySQL | 关系型 |
| **nutrition_log**（营养时序） | PostgreSQL | JSONB 存菜盘快照，时序聚合，窗口函数 |
| weekly_reports（周报缓存） | PostgreSQL | 窗口函数算趋势，与 nutrition_log 同库 |

### 5.2 user_habits 表（核心，V2 重点）

```sql
CREATE TABLE user_habits (
  user_id              VARCHAR(64)  PRIMARY KEY,
  taste_preferences    JSON         COMMENT '口味偏好 ["清淡","辣"]',
  allergies            JSON         COMMENT '过敏原 ["花生","海鲜"]',
  dislikes             JSON         COMMENT '忌口 ["香菜"]',
  dietary_goal         VARCHAR(32)  NOT NULL DEFAULT 'daily'
                       COMMENT 'daily/fitness/weight_loss/muscle_gain',
  meal_preferences     JSON         COMMENT '{"breakfast":"清淡","lunch":"吃饱"}',
  emotion_pattern      TEXT         COMMENT '情绪模式描述，如"考研压力大常熬夜"',
  health_profile       JSON         COMMENT '{"heightCm":175,"weightKg":68,"bmi":22.2,"activity":"medium"}',
  ai_personality       VARCHAR(32)  NOT NULL DEFAULT 'canteen_aunt'
                       COMMENT 'canteen_aunt/senior_brother/senior_sister',
  conversation_summary TEXT         COMMENT '最近 N 轮对话摘要，定时回写',
  updated_at           DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  KEY idx_habits_goal (dietary_goal),
  KEY idx_habits_personality (ai_personality)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户习惯长期记忆';
```

**字段职责说明**：

| 字段 | 来源 | 用途 |
|---|---|---|
| taste_preferences | 用户首次设置 + AI 推断 | 拼 system prompt：用户偏好口味 |
| allergies / dislikes | 用户表单 | 识图/推荐时过滤 + prompt 提醒 |
| dietary_goal | 用户选择 | 影响推荐策略与营养目标 |
| meal_preferences | 用户设置 | 不同餐次不同偏好 |
| emotion_pattern | 用户填写 + AI 摘要 | prompt 注入情绪背景 |
| health_profile | 健康档案同步 | BMI/活动量影响营养建议 |
| ai_personality | 用户选择 | 切换对话风格（食堂阿姨/学长/学姐） |
| conversation_summary | 每 N 轮异步生成 | 长期记忆，避免每次都翻历史 |

### 5.3 其他 MySQL 表

```sql
-- 用户基础
CREATE TABLE users (
  user_id     VARCHAR(64) PRIMARY KEY,
  nickname    VARCHAR(64),
  avatar_url  VARCHAR(512),
  created_at  DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_user_created (created_at)
) ENGINE=InnoDB CHARSET=utf8mb4;

-- 社交关系（拼饭/匿名榜）
CREATE TABLE social_relations (
  user_id      VARCHAR(64) NOT NULL,
  friend_id    VARCHAR(64) NOT NULL,
  relation     VARCHAR(32) DEFAULT 'friend',
  created_at   DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (user_id, friend_id),
  KEY idx_social_friend (friend_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

-- 食堂菜单（Nacos 下发后落库）
CREATE TABLE menu_items (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  canteen      VARCHAR(32) NOT NULL,
  dish_id      VARCHAR(32) NOT NULL,
  date         DATE NOT NULL,
  meal         VARCHAR(16) NOT NULL COMMENT 'breakfast/lunch/dinner',
  price        DECIMAL(6,2),
  station      VARCHAR(32),
  available    TINYINT(1) DEFAULT 1,
  KEY idx_menu_lookup (canteen, date, meal)
) ENGINE=InnoDB CHARSET=utf8mb4;

-- 过敏原字典
CREATE TABLE allergies (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  name         VARCHAR(32) NOT NULL UNIQUE,
  category     VARCHAR(32) COMMENT '坚果/海鲜/乳制品...'
) ENGINE=InnoDB CHARSET=utf8mb4;

-- 菜品评价
CREATE TABLE dish_ratings (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id      VARCHAR(64) NOT NULL,
  dish_id      VARCHAR(32) NOT NULL,
  rating       TINYINT NOT NULL COMMENT '1-5',
  comment      TEXT,
  created_at   DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_rating_dish (dish_id, created_at)
) ENGINE=InnoDB CHARSET=utf8mb4;

-- 情绪日记
CREATE TABLE mood_logs (
  id           VARCHAR(64) PRIMARY KEY,
  user_id      VARCHAR(64) NOT NULL,
  mood         VARCHAR(16) NOT NULL,
  note         TEXT,
  ai_comfort   TEXT,
  created_at   DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_mood_user (user_id, created_at)
) ENGINE=InnoDB CHARSET=utf8mb4;

-- 健康档案
CREATE TABLE health_profiles (
  user_id         VARCHAR(64) PRIMARY KEY,
  gender          VARCHAR(16),
  age             INT,
  height_cm       DECIMAL(5,1),
  weight_kg       DECIMAL(5,1),
  bmi             DECIMAL(4,1),
  activity_level  VARCHAR(16) DEFAULT 'medium',
  daily_kcal_target INT,
  updated_at      DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB CHARSET=utf8mb4;

-- 运动记录
CREATE TABLE sport_records (
  id           VARCHAR(64) PRIMARY KEY,
  user_id      VARCHAR(64) NOT NULL,
  date         DATE NOT NULL,
  steps        INT DEFAULT 0,
  duration_min INT DEFAULT 0,
  kcal_burned  DECIMAL(7,1),
  kcal_quota   DECIMAL(7,1) COMMENT '可换算的饮食配额',
  source       VARCHAR(16) DEFAULT 'manual',
  created_at   DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_sport_user_date (user_id, date)
) ENGINE=InnoDB CHARSET=utf8mb4;
```

### 5.4 PostgreSQL 时序表

```sql
-- 营养时序数据（菜盘快照）
CREATE TABLE nutrition_log (
  id          BIGSERIAL PRIMARY KEY,
  user_id     VARCHAR(64) NOT NULL,
  date        DATE NOT NULL,
  meal        VARCHAR(16) NOT NULL,
  tray_json   JSONB NOT NULL,         -- 完整 TrayItem[] 快照
  nutrition   JSONB NOT NULL,         -- {kcal,protein,carb,fat}
  mode        VARCHAR(16),
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_nutrition_user_date ON nutrition_log(user_id, date);
CREATE INDEX idx_nutrition_user_date_meal ON nutrition_log(user_id, date, meal);
-- JSONB GIN 索引（支持按菜品查）
CREATE INDEX idx_nutrition_tray_gin ON nutrition_log USING GIN(tray_json);

-- 周报缓存
CREATE TABLE weekly_reports (
  user_id      VARCHAR(64) NOT NULL,
  week         VARCHAR(8) NOT NULL,    -- 2026-W27
  report_json  JSONB NOT NULL,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, week)
);
```

### 5.5 索引设计总结

| 表 | 索引 | 用途 |
|---|---|---|
| user_habits | PK(user_id) | 主键查询 |
| user_habits | idx_habits_goal | 按目标分群分析 |
| mood_logs | idx_mood_user(user_id, created_at) | 用户情绪时间线 |
| menu_items | idx_menu_lookup(canteen, date, meal) | 今日菜单查询 |
| nutrition_log | idx_nutrition_user_date | 周报聚合 |
| nutrition_log | GIN(tray_json) | 按菜品反查消费记录 |
| sport_records | idx_sport_user_date | 运动配额累计 |

### 5.6 ER 关系（文字描述）

```
users (1) ── (1) user_habits        # 1:1，用户基础信息 + 习惯
users (1) ── (N) mood_logs          # 1:N 情绪日记
users (1) ── (1) health_profiles    # 1:1 健康档案
users (1) ── (N) sport_records      # 1:N 运动记录
users (1) ── (N) social_relations   # 1:N 社交关系（friend_id 反向）
users (1) ── (N) dish_ratings       # 1:N 菜品评价
users (1) ── (N) nutrition_log(Pg)  # 1:N 营养时序
users (1) ── (N) weekly_reports(Pg) # 1:N 周报缓存（按周）
menu_items (N) ── (1) dishes(foods.json)  # 菜单引用菜品库
```

---

## 6. 接口设计

> 统一响应格式：`{ "code": 0, "message": "ok", "data": <payload> }`
> 错误时：`{ "code": <非0>, "message": "<短描述>", "data": null }`
> 所有时间戳 ISO8601（UTC+8）。

### 6.1 POST /api/recognize-dish —— 拍照识菜（异步 V2）

**用途**：上传菜品照片，返回 task_id，前端轮询结果。

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | File | 是 | 图片 jpg/png/webp，≤5MB |
| user_id | string | 否 | 用于忌口过滤（v2.2 改 snake_case） |
| meal_hint | string | 否 | breakfast/lunch/dinner（v2.2 改 snake_case） |

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": { "task_id": "rec_8f2a3b4c5d6e" , "status": "pending" }
}
```

**错误**：`40001` 文件超限/格式错；`42901` 限流；`50005` OSS 上传失败；`50006` MQ 投递失败。

### 6.2 GET /api/recognize/result/{task_id} —— 轮询识图结果

**响应（pending）**：

```json
{ "code": 0, "message": "ok", "data": { "task_id":"rec_8f2a3b4c5d6e", "status":"pending", "progress": 30 } }
```

**响应（done）**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "rec_8f2a3b4c5d6e",
    "status": "done",
    "progress": 100,
    "dish": {
      "id": "f103",
      "name": "宫保鸡丁",
      "category": "肉类",
      "unit": "份(150g)",
      "kcal": 260,
      "protein": 18,
      "carb": 12,
      "fat": 15,
      "confidence": 0.92,
      "matched": true,
      "alternatives": [
        { "id":"f104","name":"宫保鸡丁(小)","category":"肉类","unit":"份(100g)","kcal":180,"protein":12,"carb":8,"fat":10 }
      ]
    }
  }
}
```

**响应（failed）**：

```json
{ "code": 0, "message": "ok", "data": { "task_id":"rec_8f2a3b4c5d6e", "status":"failed", "progress": 100, "error": "VL 模型超时" } }
```

**前端轮询策略**：v2.2 统一为 1.5s 间隔，最多 20 次（30s 硬约束正好达标），超时提示"识别超时"。

### 6.3 POST /api/chat —— AI 对话（SSE + 双层记忆）

**请求**：`application/json`，`Accept: text/event-stream`

```json
{
  "user_id": "u_demo",
  "persona": "canteen_aunt",
  "messages": [
    { "role": "user", "content": "我蛋白够不够？" },
    { "role": "assistant", "content": "你今天吃了鸡胸肉..." }
  ],
  "context": {
    "food_tray": [
      { "name":"鸡胸肉","category":"肉类","kcal":130 }
    ],
    "mode": "fitness",
    "nutrition": { "kcal": 130, "protein": 28, "carb": 1, "fat": 3 },
    "mode_target": { "kcal": 1800, "protein": 110, "carb": 220, "fat": 60 }
  }
}
```

> v2.2 合并方案：`user_id` + `persona` + `messages` + `context`。`user_habits` 后端基于 `user_id` 自取，前端不传。

**响应**（流式 `text/event-stream`）：

```
event: delta
data: {"delta":"蛋白","done":false}

event: delta
data: {"delta":"已经","done":false}

...

event: done
data: {"delta":"","done":true}
```

**降级**：客户端 `Accept: application/json` → 返回完整 JSON：

```json
{
  "code": 0,
  "message": "ok",
  "data": { "text": "你今天蛋白 28g，离健身目标 110g 还差不少……" }
}
```

**错误**：`50003` 模型调用失败；`42901` 限流。

### 6.4 GET /api/recommend —— 智能推荐补菜

**请求**：`GET /api/recommend?userId=u_demo&mode=fitness&tray=%5B...%5D`

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "gaps": ["蛋白质缺口 60g", "午餐缺蔬菜"],
    "suggestions": [
      { "id":"f108","name":"鸡胸肉","category":"肉类","unit":"份(100g)","kcal":130,"protein":28,"carb":1,"fat":3,"reason":"高蛋白低脂，补蛋白缺口" },
      { "id":"f205","name":"蒜蓉西兰花","category":"蔬菜","unit":"份(150g)","kcal":80,"protein":5,"carb":10,"fat":3,"reason":"补午餐缺的蔬菜类" }
    ]
  }
}
```

> 推荐算法**不调用 AI**，纯本地计算（基于 foods.json + 营养缺口 + user_habits 过敏过滤），延迟 < 50ms。

### 6.5 GET /api/weekly-report —— 饮食周报

**请求**：`GET /api/weekly-report?userId=u_demo&week=2026-W27`

**响应**：见 4.6 `WeeklyReport`。

**说明**：`aiSummary` 调用 `qwen3.7-max`（1M 上下文旗舰）生成，结果缓存到 PostgreSQL `weekly_reports` 表。聚合用 PostgreSQL 窗口函数：`SUM(...) OVER (PARTITION BY user_id, date)` 算每日合计，`AVG(...) OVER (ORDER BY date ROWS 3 PRECEDING)` 算趋势。

### 6.6 POST /api/preferences —— 过敏/忌口/人设管理

**请求**：

```json
{
  "user_id": "u_demo",
  "allergens": ["花生","海鲜"],
  "dislikes": ["香菜"],
  "goal": "fitness",
  "daily_kcal_target": 1800,
  "persona": "senior_brother"
}
```

**响应**：`{ "code": 0, "message": "ok", "data": { "saved": true } }`

**联动**：写入 `user_habits` 表对应字段；识图/推荐/对话在组装 prompt 时会注入忌口列表，命中则标注警告。

### 6.7 GET /api/menu —— 食堂今日菜单

**请求**：`GET /api/menu?canteen=main&date=2026-07-03`

**响应**：见 4.7 `CanteenMenu`。

**说明**：菜单数据由 Nacos 配置中心动态下发，落库 `menu_items` 表；接口直接查库。

### 6.8 GET /api/leaderboard —— 同学搭配匿名榜

**请求**：`GET /api/leaderboard?mode=fitness&limit=10`

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    { "rank":1, "anonymous_name":"同学#A3F2", "score":92.5, "hit_days":6, "mode":"fitness" }
  ]
}
```

**评分**：营养均衡分 = 100 − Σ|实际占比 − 目标占比| × 权重（蛋白/碳水/脂肪 各 0.3，热量 0.1），按周累计平均。匿名名：`同学#` + 用户 id 哈希后 4 位。热门菜品用 Redis ZSET 排行。

### 6.9 POST /api/mood —— 情绪日记

**请求**：

```json
{ "user_id": "u_demo", "mood": "stressed", "note": "今天作业好多" }
```

**响应**（v2.2 合并方案：完整 MoodLog + suggestion 可选）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "m1690123456789",
    "user_id": "u_demo",
    "mood": "stressed",
    "note": "今天作业好多",
    "created_at": "2026-07-03T14:30:00+08:00",
    "ai_comfort": "辛苦啦，先去吃点热的，胃暖了心也会跟着暖一点～",
    "suggestion": "要不要来份热汤暖暖胃？"
  }
}
```

**说明**：`ai_comfort` 调用 `qwen3.7-flash`（低延迟低成本），同步返回，`max_tokens=80`；`suggestion` 可选，由模型决定是否返回。

### 6.10 GET/POST /api/health/profile —— 健康档案

**GET 请求**：`GET /api/health/profile?user_id=u_demo`

**POST 请求**：

```json
{
  "user_id": "u_demo",
  "gender": "male",
  "age": 20,
  "height_cm": 175,
  "weight_kg": 68,
  "activity_level": "medium"
}
```

**响应**：见 4.10 `HealthProfile`。

**说明**：BMR 用 Mifflin-St Jeor 公式：
- 男：`10×体重 + 6.25×身高 − 5×年龄 + 5`
- 女：`10×体重 + 6.25×身高 − 5×年龄 − 161`
- `daily_kcal_target = BMR × 活动系数（低1.375/中1.55/高1.725）`
- BMI = 体重 / (身高/100)²，自动算并同步到 `user_habits.health_profile`

### 6.11 GET/POST /api/sport/records —— 运动数据接入（V2 新增）

**GET 请求**：`GET /api/sport/records?user_id=u_demo&date=2026-07-03`（查询运动记录列表）

**POST 请求**（提交运动记录）：

```json
{
  "user_id": "u_demo",
  "date": "2026-07-03",
  "steps": 8500,
  "duration_min": 30,
  "source": "mi_band"
}
```

**响应**（POST 返回单条 SportRecord，GET 返回数组）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "s1690123456789",
    "user_id": "u_demo",
    "date": "2026-07-03",
    "steps": 8500,
    "duration_min": 30,
    "kcal_burned": 490.0,
    "kcal_quota": 343.0,
    "source": "mi_band",
    "created_at": "2026-07-03T20:00:00+08:00"
  }
}
```

**换算**：`kcal_burned = steps × 0.04 + duration_min × 5`；`kcal_quota = kcal_burned × 0.7`（70% 可换算饮食额度）。

### 6.12 POST /api/share-card —— 分享卡片（V2 新增，v2.2 改 POST）

**请求**（前端提交菜盘摘要 + 营养总计）：

```json
{
  "user_id": "u_demo",
  "date": "2026-07-03",
  "tray_summary": [
    { "name":"鸡胸肉","category":"肉类","kcal":130 }
  ],
  "nutrition": { "kcal": 1850, "protein": 95, "carb": 220, "fat": 60 }
}
```

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "card_id": "card_8f2a3b4c",
    "user_id": "u_demo",
    "date": "2026-07-03",
    "nutrition": { "kcal": 1850, "protein": 95, "carb": 220, "fat": 60 },
    "dish_images": ["https://oss.../img1.jpg"],
    "card_image_url": "https://oss.../card_8f2a.png",
    "ai_comment": "今天蛋白达标了，是会吃的一天！",
    "created_at": "2026-07-03T21:00:00+08:00"
  }
}
```

**流程**：取前端提交数据 → 调 `qwen3.7-flash` 生成点评 → Pillow 合成卡片图 → 上传 OSS → 返回 URL。

### 6.13 POST /api/voice-to-tray —— 语音转菜盘（V2 新增）

**请求**：`multipart/form-data` 上传语音文件，或 `application/json` 传语音转写文本。

```json
{ "user_id": "u_demo", "text": "我今天中午吃了一份宫保鸡丁和一碗米饭" }
```

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "tray": [
      { "id":"f103","name":"宫保鸡丁","category":"肉类","unit":"份(150g)","kcal":260,"protein":18,"carb":12,"fat":15 },
      { "id":"f001","name":"米饭","category":"主食","unit":"份(200g)","kcal":230,"protein":5,"carb":48,"fat":1 }
    ]
  }
}
```

**说明**：调 `qwen3.7-plus`（多模态均衡，OCR 强）做语义抽取 → 匹配 foods 库。

### 6.14 B 端管理后台（v2.2 补全所有接口）

> 所有 `/api/admin/*` 接口除 `/api/admin/login` 外均需 `Authorization: Bearer {admin_token}` 鉴权。

#### 6.14.1 POST /api/admin/login —— 管理员登录

**请求**：

```json
{ "password": "xxx" }
```

**响应**：

```json
{ "code": 0, "message": "ok", "data": { "admin_token": "adm_xxx" } }
```

#### 6.14.2 GET /api/admin/overview —— 概览

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "recognize_count_today": 328,
    "online_users": 47,
    "avg_nutrition_score": 82
  }
}
```

#### 6.14.3 GET /api/admin/dish-heat —— 菜品热度（Redis ZSET）

**请求**：`GET /api/admin/dish-heat?range=week`

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    { "dish_id":"f103","name":"宫保鸡丁","heat":980 },
    { "dish_id":"f108","name":"鸡胸肉","heat":760 }
  ]
}
```

#### 6.14.4 GET /api/admin/unsold —— 滞销菜

**请求**：`GET /api/admin/unsold?days=7`

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    { "dish_id":"f405","name":"凉拌苦瓜","count":8,"rating":3.2 }
  ]
}
```

#### 6.14.5 GET /api/admin/nutrition-stats —— 营养统计

**请求**：`GET /api/admin/nutrition-stats?date=2026-07-03`

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "avg_kcal": 1850,
    "avg_protein": 78,
    "user_count": 1234
  }
}
```

#### 6.14.6 GET /api/admin/canteen-stats —— 食堂统计

**请求**：`GET /api/admin/canteen-stats?date=2026-07-03`

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "date": "2026-07-03",
    "top_dishes": [
      { "dish_id":"f103","name":"宫保鸡丁","count":156,"rating":4.6 }
    ],
    "slow_dishes": [
      { "dish_id":"f405","name":"凉拌苦瓜","count":8,"rating":3.2 }
    ],
    "nutrition_stats": {
      "avg_kcal": 1850,
      "avg_protein": 78,
      "user_count": 1234
    }
  }
}
```

#### 6.14.7 POST /api/admin/menu —— 菜单下发（Nacos）

**请求**：管理员编辑的菜单 JSON（CanteenMenu 结构）

**响应**：`{ "code": 0, "message": "ok", "data": { "published": true } }`

#### 6.14.8 GET /api/admin/reviews —— 评价列表

**响应**：dish_reviews 列表

#### 6.14.9 POST /api/admin/reviews/{id}/reply —— 评价回复

**请求**：`{ "reply": "..." }`  **响应**：`{ "code": 0, "data": { "replied": true } }`

#### 6.14.10 DELETE /api/admin/reviews/{id} —— 隐藏不当评价

**响应**：`{ "code": 0, "data": { "hidden": true } }`

---

## 7. AI 集成方案（V2 双平台 + 多模型路由）

### 7.1 模型路由表

| 场景 | 平台 | 模型 | 理由 |
|---|---|---|---|
| 拍照识菜（主） | 通义千问 VL | `qwen-vl-max-latest` | 视觉旗舰，准确度高 |
| 拍照识菜（降级） | 通义千问 VL | `qwen-vl-plus` | 主模型失败/限流时兜底，成本低 |
| 外卖截图识别 | 通义千问 VL | `qwen-vl-max-latest` | OCR 强，处理截图 |
| 日常对话 + 多模态 | 百练 | `qwen3.7-plus` | 多模态均衡，OCR 强 |
| 周报/复杂营养推演 | 百练 | `qwen3.7-max` | 纯文本旗舰，1M 上下文 |
| 高频短回复/情绪治愈 | 百练 | `qwen3.7-flash` | 低延迟低成本 |
| 语音转菜盘语义抽取 | 百练 | `qwen3.7-plus` | 多模态均衡，理解力够 |
| 对话摘要生成（异步） | 百练 | `qwen3.7-flash` | 短文本摘要，低成本 |

> **模型名以阿里云百炼控制台最新可用为准**。代码中模型名集中在 `app/config.py`，路由表见 `app/ai/router.py`。

### 7.2 双平台接入方式

**通义千问 VL**（dashscope SDK）：
- 用于识菜、外卖截图，调用同步/异步任务
- 客户端封装在 `app/ai/vl_client.py`

**阿里百练**（兼容 OpenAI 接口，用 openai SDK 改 base_url）：
- 用于对话、周报、情绪、陪伴
- 客户端封装在 `app/ai/bailian_client.py`
- 调用方式：`OpenAI(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", api_key=BAILIAN_API_KEY)`

### 7.3 Prompt 模板设计

Prompt 模板放在 `app/ai/prompts.py`，**可被 Nacos 动态下发覆盖**（Nacos 优先级 > 本地）：

- `RECOGNIZE_PROMPT`：识菜 system prompt（返回严格 JSON）
- `CHAT_SYSTEM_TEMPLATE`：对话 system prompt（含 `{habits}`、`{history}`、`{nutrition}` 占位符）
- `REPORT_PROMPT`：周报 system prompt（含 `{daily_summary}` 占位符）
- `MOOD_COMFORT_PROMPT`：情绪治愈话语 prompt
- `SUMMARY_PROMPT`：对话摘要生成 prompt

### 7.4 识菜 Prompt 要点

System：
```
你是食堂菜品识别助手。用户会发一张食堂打饭的照片。
请识别图中可见的菜品，返回严格 JSON，schema：
{ "dishes": [ { "name":"...","category":"主食|肉类|蔬菜|蛋奶|汤品|水果","unit":"份(g)","kcal":0,"protein":0,"carb":0,"fat":0 } ] }
要求：
1. name 用食堂常见菜名（如"宫保鸡丁"而非"鸡肉丁炒花生"）
2. category 必须是 6 类之一
3. 营养值按每份估算，单位克数写在 unit 里
4. 只返回 JSON，不要任何解释文字
```

User（图片 + 文字）：`请识别这道菜。{mealHint ? "用餐场景：" + mealHint : ""}`

### 7.5 图片传参与预处理

OSS URL 或 base64 data URI 二选一。MQ Worker 用 **OSS URL**（避免大 base64 传参）。预处理（Pillow）：
1. 校验 magic bytes，拒绝伪装扩展名
2. 长边 > 1024px 等比缩放（控制 token）
3. 转 JPEG quality=85（若原图透明保留 PNG）
4. 校验最终 ≤ 5MB

### 7.6 超时与重试

| 参数 | VL | 百练对话 |
|---|---|---|
| 连接超时 | 5s | 5s |
| 读取超时 | 30s | 15s（首 token） |
| 总超时 | 40s | 20s |
| 重试 | 2 次，指数退避 1s/2s | 2 次 |
| 重试条件 | 网络错误、5xx、429 | 同 |
| 降级 | `qwen-vl-max` → `qwen-vl-plus` | `qwen3.7-plus` → `qwen3.7-flash` |

### 7.7 Token 控制

- 识菜：图片 token 由 dashscope 按分辨率计费，靠 7.5 缩放控制
- 对话：system prompt < 800 token，Redis 短期记忆保留最近 4 轮，`max_tokens=512`
- 周报：输入约 7 条 DailySummary（< 500 token），`max_tokens=300`
- 情绪：`max_tokens=80`
- 摘要：`max_tokens=150`

### 7.8 并发与限流

- VL/百练客户端用 `asyncio.Semaphore` 控制并发（默认 5）
- 接口层 slowapi 限流：
  - `/api/recognize-dish` 按 IP 10 次/分钟
  - `/api/chat` 按 user 20 次/分钟
  - `/api/mood` 按 user 30 次/分钟

---

## 8. 用户习惯记忆机制（V2 重点章节）

### 8.1 双层记忆架构

```
┌─────────────────────────────────────────────────────────┐
│                  用户提问 "我蛋白够不够"                  │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│  ChatService 组装上下文                                  │
│                                                          │
│  ① 长期记忆（MySQL user_habits）                        │
│     ├─ tastePreferences: ["清淡","辣"]                  │
│     ├─ allergens: ["花生"]                               │
│     ├─ dietaryGoal: "fitness"                           │
│     ├─ healthProfile: {bmi:22.2, activity:"high"}       │
│     ├─ aiPersonality: "senior_brother"                  │
│     └─ conversationSummary: "用户最近在健身增肌..."      │
│                                                          │
│  ② 短期记忆（Redis, key=chat:ctx:{userId}, TTL=1h）     │
│     └─ 最近 N 轮对话原文（默认 N=4）                     │
│                                                          │
│  ③ 当前请求上下文                                        │
│     └─ tray + nutrition + message                       │
│                                                          │
│  拼装 system prompt → 调百练 → 流式返回                  │
└──────────────────────────┬──────────────────────────────┘
                           ▼
              异步：本轮 Q/A 写入 Redis 短期记忆
              每 N 轮触发摘要生成 → 回写 user_habits.conversation_summary
```

### 8.2 system prompt 拼装流程

```
SYSTEM PROMPT 模板（CHAT_SYSTEM_TEMPLATE）：

你是「{aiPersonality}」，一个陪伴 {userNickname} 在校园食堂吃饭的 AI 营养搭子。

【用户长期画像】
- 口味偏好：{tastePreferences}
- 过敏原：{allergens}（务必提醒避开）
- 忌口食材：{dislikes}
- 饮食目标：{dietaryGoal}
- 各餐偏好：{mealPreferences}
- 情绪状态：{emotionPattern}
- 健康档案：BMI {bmi}，活动量 {activity}
- 最近对话摘要：{conversationSummary}

【最近对话】
{recentHistory}

【当前菜盘营养】
{kcal}kcal / 蛋白 {protein}g / 碳水 {carb}g / 脂肪 {fat}g
模式：{mode}

请基于以上信息，用 {aiPersonality} 的语气风格回答用户问题。
语气示例：
- 食堂阿姨：热情、关心、爱念叨"多吃点"
- 学长：经验分享、鼓励、偶尔皮一下
- 学姐：温柔、细心、照顾情绪
```

### 8.3 短期记忆 Redis 结构

```
Key:    chat:ctx:{userId}
Type:   List（双向列表，左进右出保持 N 轮）
TTL:    3600s（1 小时）
Value:  JSON 序列化的 {role, content, ts}

示例：
LPUSH chat:ctx:u_demo '{"role":"user","content":"我蛋白够不够","ts":"..."}'
LPUSH chat:ctx:u_demo '{"role":"assistant","content":"你还差 60g...","ts":"..."}'
LTRIM chat:ctx:u_demo 0 7    # 保留最近 4 轮（8 条）
EXPIRE chat:ctx:u_demo 3600
```

### 8.4 conversation_summary 摘要生成策略

- **触发时机**：每 6 轮对话触发一次（异步 MQ 任务，不阻塞响应）
- **生成方式**：取 Redis 最近 6 轮 + 旧 summary → 调 `qwen3.7-flash` → 输出新摘要（≤ 150 token）
- **回写**：`UPDATE user_habits SET conversation_summary = ? WHERE user_id = ?`
- **Prompt**：

```
请把以下对话浓缩成一段不超过 150 字的用户画像摘要，保留：
- 用户的核心饮食诉求
- 提到的具体菜品/营养偏好
- 情绪状态变化
旧摘要：{oldSummary}
最近对话：{recentDialog}
输出：直接给出新摘要，不要解释。
```

### 8.5 AI 人格切换

`user_habits.ai_personality` 三选一：

| 值 | 风格 | 适用场景 |
|---|---|---|
| `canteen_aunt` | 食堂阿姨，热情、念叨"多吃点" | 默认，温馨陪伴 |
| `senior_brother` | 学长，经验分享、鼓励 | 健身增肌用户 |
| `senior_sister` | 学姐，温柔、照顾情绪 | 情绪压力大用户 |

切换后立即生效（下次对话即用新人格）。

---

## 9. 数据存储方案

### 9.1 存储分工总表

| 数据 | 存储 | 理由 |
|---|---|---|
| 菜品库（~200 条） | `data/foods.json` + Redis 缓存 | 静态、低频变更、前端共享 |
| 用户基础信息 | MySQL `users` | 关系型 |
| 用户习惯（长期记忆） | MySQL `user_habits` | **V2 核心**，JSON 字段 |
| 社交关系 | MySQL `social_relations` | 关系查询 |
| 食堂菜单 | MySQL `menu_items`（Nacos 下发） | 关系型 |
| 过敏原字典 | MySQL `allergies` | 字典表 |
| 菜品评价 | MySQL `dish_ratings` | 关系型 |
| 情绪日记 | MySQL `mood_logs` | 简单 CRUD |
| 健康档案 | MySQL `health_profiles` | 单用户单行 |
| 运动记录 | MySQL `sport_records` | 关系型 |
| 营养时序（菜盘快照） | PostgreSQL `nutrition_log` | JSONB + 窗口函数 |
| 周报缓存 | PostgreSQL `weekly_reports` | 同库聚合 |
| 识图结果缓存 | Redis `recognize:{image_hash}` | 省钱，TTL 7 天 |
| 对话短期记忆 | Redis `chat:ctx:{userId}` | TTL 1h |
| 热门菜品 ZSET | Redis `dish:heat:{week}` | 排行榜 |
| 限流计数 | Redis `ratelimit:{ip/user}:{route}` | slowapi 后端 |
| 原图/卡片图 | OSS | 大文件存储 |

### 9.2 Redis Key 命名规范

| Key 模式 | 类型 | TTL | 用途 |
|---|---|---|---|
| `recognize:{md5(image)}` | String(JSON) | 7d | 识图结果缓存 |
| `chat:ctx:{userId}` | List | 1h | 对话短期记忆 |
| `dish:heat:{week}` | ZSET | 7d | 热门菜品排行 |
| `ratelimit:{ip}:{route}` | String | 60s | 限流计数 |
| `menu:{canteen}:{date}` | String(JSON) | 1h | 今日菜单缓存 |
| `leaderboard:{mode}` | ZSET | 1h | 匿名榜缓存 |

### 9.3 菜品库 foods.json 结构

从前端 `js/main.js` 中 `FOODS_DATA` 搬迁，**保留完全相同的 id 体系**（f001/f101/f201/f301/f401/f501），扩展 `aliases` 字段辅助模糊匹配：

```json
[
  {
    "id": "f103",
    "name": "宫保鸡丁",
    "aliases": ["宫爆鸡丁","宫保鸡丁丁","kung pao chicken"],
    "category": "肉类",
    "unit": "份(150g)",
    "kcal": 260,
    "protein": 18,
    "carb": 12,
    "fat": 15
  }
]
```

**匹配规则**（`recognize_service`）：
1. VL 返回 name 与 foods.json 的 `name + aliases` 归一化（去空格、转小写）后精确匹配 → `matched=true`，用库内精确值
2. 模糊匹配（编辑距离 ≤ 2 或包含关系）→ `matched=true`，`alternatives` 取同类别邻近项
3. 完全无匹配 → `matched=false`，用 VL 估算值，`id = "r" + 时间戳`

### 9.4 数据同步策略

前端菜盘存 localStorage，后端要生成周报/分享卡必须拿到历史。**V2 选方案 B（定时同步）**：

- 前端每次 `saveState()` 时静默 POST `/api/tray/sync`（接口未在 P0 列出，可加）
- 后端写入 PostgreSQL `nutrition_log`（JSONB 快照）
- 周报直接查库，不依赖前端推送

---

## 10. 关键技术点

### 10.1 异步任务 MQ

**识图异步化**：
- 上传 → 算 hash → 查 Redis → 命中直接返回；未命中 → 投 MQ → 返回 task_id
- Worker 消费 → 调 VL → 写 Redis + MySQL → 前端轮询
- 优势：用户不阻塞等待 VL 4s，接口响应 < 200ms

**周报生成**：
- 每周一首次访问触发 → 投 MQ → Worker 调 `qwen3.7-max` → 写 PostgreSQL `weekly_reports`
- 避免用户首次打开周报等 5s+

**定时推送**：
- 餐次时间提醒（11:30/17:30）→ MQ 定时任务 → 推送（PWA Push / WebSocket）

### 10.2 Redis 缓存策略

| 场景 | 策略 |
|---|---|
| 识图结果 | hash→结果，TTL 7 天，命中省钱 |
| 菜单 | `menu:{canteen}:{date}`，TTL 1h，Nacos 变更时主动失效 |
| 热门菜品 | ZSET，每次识图/入盘 ZINCRBY |
| 对话上下文 | List，TTL 1h，LRTRIM 保 N 轮 |
| 周报 | 查 Pg 后缓存 1h |

### 10.3 限流（slowapi）

```python
# 契约示意
limiter = Limiter(key_func=get_remote_address, storage_uri="redis://...")
@app.post("/api/recognize-dish")
@limiter.limit("10/minute")
async def recognize(...): ...
```

触发限流返回 `429` + 错误码 `42901`。Redis 作为限流存储后端，支持多 worker 共享计数。

### 10.4 CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,   # 开发 ["*"]，生产具体域名
    allow_methods=["GET","POST"],
    allow_headers=["*"],
    allow_credentials=False,
)
```

开发期前端 `file://` 或本地静态服务器，CORS 必须 `allow_origins=["*"]` 或显式包含 `null`。

### 10.5 配置中心 Nacos

- **用途**：食堂菜单、推荐策略、AI prompt 模板动态下发
- **单服务不做服务注册**（无需 Nacos Discovery）
- 客户端在 `app/data/nacos_client.py`，启动时拉取配置 + 监听变更
- 配置优先级：Nacos > 本地 .env（仅限动态配置项）
- 监听变更后：菜单落 MySQL，prompt 模板覆盖 `app/ai/prompts.py` 内存缓存

### 10.6 SSE 流式

```python
# 契约示意
from fastapi.responses import StreamingResponse
@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        chat_service.stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"}
    )
```

Nginx 反代需 `proxy_buffering off`，避免 SSE 被缓冲。

### 10.7 图片压缩

- 前端预压缩：长边 ≤ 1280px
- 后端二次压缩：Pillow 长边 ≤ 1024px，JPEG quality=85
- OSS 上传用预签名 URL，避免大文件经后端中转

### 10.8 错误处理中间件

```python
@app.exception_handler(Exception)
async def global_handler(request, exc):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"code":50000,"message":"internal error","data":None})
```

自定义 `BizError(code, message)` 在 service 层抛出明确错误。

### 10.9 日志

- 结构化 JSON 日志（生产接 ELK / Loki）
- 关键字段：`request_id`（中间件 UUID）、`user_id`、`route`、`latency_ms`、`status`
- AI 调用单独 logger：`model`、`prompt_tokens`、`completion_tokens`、`duration_ms`、`success`
- 敏感信息脱敏：图片 base64 不入日志，只记 `image_size_kb` 和 `mime`

### 10.10 API Key 管理（V2 双 Key）

- `.env` 不入库（.gitignore），`.env.example` 提供模板
- 通过 `pydantic-settings` 读取，**绝不硬编码**
- 生产用环境变量注入
- **双 Key**：`DASHSCOPE_API_KEY`（VL）+ `BAILIAN_API_KEY`（百练），职责分离便于独立轮换

```env
# .env.example
# ===== AI 双平台 =====
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx        # 通义千问 VL
BAILIAN_API_KEY=sk-xxxxxxxxxxxxxxxx          # 阿里百练
QWEN_VL_MODEL_PRIMARY=qwen-vl-max-latest
QWEN_VL_MODEL_FALLBACK=qwen-vl-plus
BAILIAN_MODEL_CHAT=qwen3.7-plus
BAILIAN_MODEL_REPORT=qwen3.7-max
BAILIAN_MODEL_FLASH=qwen3.7-flash
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ===== 数据库（生产服务器 <your-server-ip>，密码 <password>，端口默认）=====
MYSQL_DSN=mysql://root:<password>@<your-server-ip>:3306/food_healing?charset=utf8mb4
PG_DSN=postgresql://postgres:<password>@<your-server-ip>:5432/food_healing
REDIS_URL=redis://:<password>@<your-server-ip>:6379/0

# ===== MQ（RabbitMQ）=====
RABBITMQ_URL=amqp://guest:<password>@<your-server-ip>:5672/

# ===== OSS =====
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=food-healing-images
OSS_ACCESS_KEY_ID=xxxxxxxx
OSS_ACCESS_KEY_SECRET=xxxxxxxx

# ===== Nacos =====
NACOS_SERVER=<your-server-ip>:8848
NACOS_NAMESPACE=dev
NACOS_USERNAME=nacos
NACOS_PASSWORD=<password>

# ===== 应用 =====
CORS_ORIGINS=["*"]
RATE_LIMIT_RECOGNIZE=10/minute
RATE_LIMIT_CHAT=20/minute
MAX_IMAGE_SIZE_MB=5
LOG_LEVEL=INFO
ENV=dev
```

---

## 11. 依赖清单（uv 管理）

> **V2 升级**：依赖管理从 `pip + requirements.txt` 切换为 **uv + pyproject.toml + uv.lock**。
> uv（Astral 出品，Rust 实现）比 pip 快 10–100x，`uv.lock` 锁定全部依赖（含传递依赖）的精确版本与 hash，跨机器复现一致。
> 完整规范见 `docs/后端技术规范.md` §2。

### 11.1 添加依赖（uv add 风格）

新增依赖时一律用 `uv add`，自动更新 `pyproject.toml` + `uv.lock`：

```bash
# Web 框架
uv add "fastapi>=0.115,<0.116"
uv add "uvicorn[standard]>=0.30,<0.31"
uv add "python-multipart>=0.0.9,<0.1"
uv add "gunicorn>=22,<23"

# AI 双平台
uv add "dashscope>=1.20,<2"          # 通义千问 VL
uv add "openai>=1.30,<2"              # 百练（兼容 OpenAI 接口，改 base_url）

# 图片处理
uv add "Pillow>=10,<11"

# 限流
uv add "slowapi>=0.1,<0.2"

# 配置
uv add "pydantic-settings>=2.3,<3"
uv add "python-dotenv>=1.0,<2"

# MySQL
uv add "aiomysql>=0.2,<0.3"
uv add "PyMySQL>=1.1,<2"              # 同步兜底
uv add "SQLAlchemy>=2.0,<3"
uv add "alembic>=1.13,<2"            # 迁移

# PostgreSQL
uv add "asyncpg>=0.29,<0.30"
uv add "psycopg2-binary>=2.9,<3"     # Alembic 同步迁移用

# Redis
uv add "redis[hiredis]>=5.0,<6"      # async redis

# OSS
uv add "oss2>=2.18,<3"

# MQ（RabbitMQ 选型）
uv add "aio-pika>=9,<10"

# Nacos
uv add "nacos-sdk-python>=0.1,<0.2"

# 日志
uv add "structlog>=24,<25"
```

### 11.2 添加 dev 依赖（不进生产镜像）

```bash
uv add --dev "pytest>=8,<9"
uv add --dev "pytest-asyncio>=0.23,<0.24"
uv add --dev "pytest-cov>=5,<6"
uv add --dev "httpx>=0.27,<0.28"
uv add --dev "ruff>=0.5,<0.6"
uv add --dev "mypy>=1.10,<2"
uv add --dev "types-Pillow" "types-PyMySQL"
```

### 11.3 pyproject.toml 片段

```toml
[project]
name = "food-healing-backend"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "dashscope>=1.20,<2",
    "openai>=1.30,<2",
    "Pillow>=10,<11",
    "slowapi>=0.1,<0.2",
    "pydantic-settings>=2.3,<3",
    "aiomysql>=0.2,<0.3",
    "SQLAlchemy>=2.0,<3",
    "alembic>=1.13,<2",
    "asyncpg>=0.29,<0.30",
    "redis[hiredis]>=5.0,<6",
    "oss2>=2.18,<3",
    "aio-pika>=9,<10",
    "nacos-sdk-python>=0.1,<0.2",
    "structlog>=24,<25",
    # ... 完整见后端技术规范 §2.3
]

[project.optional-dependencies]
dev = ["pytest>=8,<9", "pytest-asyncio>=0.23,<0.24", "ruff>=0.5,<0.6", "mypy>=1.10,<2"]

[tool.uv]
managed = true
```

### 11.4 与 requirements.txt 的关系

- **`pyproject.toml` + `uv.lock` 是唯一真实来源**，必须提交 git
- `requirements.txt` 仅作为**导出产物**，用于 Docker / 不支持 uv 的旧脚本：

```bash
# 导出（不含 dev 依赖）
uv export --no-dev --format requirements-txt -o requirements.txt
```

- **禁止手工编辑 `requirements.txt`**
- 版本号用 `>=X,<X+1` 锁主次版本，patch 跟随 `uv lock --upgrade`

---

## 12. 配置与部署

### 12.0 服务器信息（生产）

| 项 | 值 |
|---|---|
| **服务器地址** | `<your-server-ip>` |
| 部署目录 | `/opt/food-healing/backend` |
| Python | 3.12（由 uv 自动管理） |
| uv 二进制 | `/usr/local/bin/uv` |

**基础设施组件端口（全部默认）**：

| 组件 | 端口 | 密码 |
|---|---|---|
| Redis | 6379 | <password> |
| RabbitMQ | 5672 | <password> |
| MySQL | 3306 | <password> |
| PostgreSQL | 5432 | <password> |
| Nacos | 8848 | <password> |
| FastAPI | 8000 | — |
| Nginx | 80 / 443 | — |

> **注意**：密码 `<password>` 仅用于本赛事单机部署，**绝不用于真实生产**。生产环境必须用强密码 + Vault / KMS 管理。
> 完整部署规范见 `docs/后端技术规范.md` §14。

### 12.1 本地开发（uv 管理）

> **V2 升级**：本地开发从 `pip + venv` 切换为 **uv**。uv 自动管理 `.venv`，无需手动 `python -m venv`。
> 完整规范见 `docs/后端技术规范.md` §2。

```bash
cd backend

# 安装 uv（如未装）
# macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

uv sync --extra dev               # 自动创建 .venv + 装好全部依赖（含 dev）
cp .env.example .env              # 填入双 API Key 与连接配置
uv run uvicorn app.main:app --reload --port 8000
```

访问 `http://localhost:8000/docs` 查看 OpenAPI 文档。

**常用 uv 命令**：

| 场景 | 命令 |
|---|---|
| 添加运行时依赖 | `uv add <package>` |
| 添加 dev 依赖 | `uv add --dev <package>` |
| 升级所有依赖 | `uv lock --upgrade` |
| 在虚拟环境中运行 | `uv run <cmd>` |
| 导出 requirements.txt | `uv export --no-dev -o requirements.txt` |
| 锁文件一致性校验 | `uv lock --check` |

### 12.2 生产部署（uv + gunicorn）

**用 uv 直接装依赖**（推荐，不需要预装 Python）：

```bash
# 服务器（<your-server-ip>）上
cd /opt/food-healing/backend
uv sync --no-dev                  # 只装运行时依赖
uv run gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
```

**systemd 服务**（`/etc/systemd/system/food-healing.service`）：

```ini
[Unit]
Description=Food Healing Backend
After=network.target

[Service]
Type=exec
User=foodhealing
WorkingDirectory=/opt/food-healing/backend
EnvironmentFile=/opt/food-healing/backend/.env.production
ExecStart=/usr/local/bin/uv run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 60
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now food-healing
sudo journalctl -u food-healing -f
```

**Worker 数量**：CPU 密集（图片预处理）+ IO 密集（VL/百练）混合，建议 `2 × CPU + 1`。

**反向代理**：Nginx 前置，处理 TLS、静态前端、`/api/*` 反代到 uvicorn、SSE 长连接（`proxy_buffering off`）。

```nginx
server {
    listen 80;
    server_name food-healing.example.edu.cn;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;             # SSE 必须
        proxy_read_timeout 60s;
    }

    location / {
        root /opt/food-healing-demo;     # 前端静态文件
        try_files $uri $uri/ /index.html;
    }
}
```

### 12.3 环境变量检查清单（V2）

> 生产服务器 `<your-server-ip>`，端口全部默认，密码统一 `<password>`。下方"默认"列即为该服务器的实际值。

| 变量 | 必填 | 默认（生产） | 说明 |
|---|---|---|---|
| DASHSCOPE_API_KEY | 是 | — | 通义千问 VL |
| BAILIAN_API_KEY | 是 | — | 阿里百练（对话/周报/情绪） |
| QWEN_VL_MODEL_PRIMARY | 否 | qwen-vl-max-latest | 识菜主模型 |
| QWEN_VL_MODEL_FALLBACK | 否 | qwen-vl-plus | 识菜降级 |
| BAILIAN_MODEL_CHAT | 否 | qwen3.7-plus | 对话 |
| BAILIAN_MODEL_REPORT | 否 | qwen3.7-max | 周报 |
| BAILIAN_MODEL_FLASH | 否 | qwen3.7-flash | 情绪/摘要 |
| BAILIAN_BASE_URL | 否 | https://dashscope.aliyuncs.com/compatible-mode/v1 | 百练兼容端点 |
| MYSQL_DSN | 是 | mysql://root:<password>@<your-server-ip>:3306/food_healing?charset=utf8mb4 | MySQL 连接串 |
| PG_DSN | 是 | postgresql://postgres:<password>@<your-server-ip>:5432/food_healing | PostgreSQL 连接串 |
| REDIS_URL | 是 | redis://:<password>@<your-server-ip>:6379/0 | Redis |
| RABBITMQ_URL | 是 | amqp://guest:<password>@<your-server-ip>:5672/ | RabbitMQ 连接串 |
| OSS_ENDPOINT | 是 | oss-cn-hangzhou.aliyuncs.com | OSS endpoint |
| OSS_BUCKET | 是 | food-healing-images | OSS bucket |
| OSS_ACCESS_KEY_ID | 是 | — | OSS AK |
| OSS_ACCESS_KEY_SECRET | 是 | — | OSS SK |
| NACOS_SERVER | 否 | <your-server-ip>:8848 | Nacos 地址 |
| NACOS_NAMESPACE | 否 | dev | Nacos 命名空间 |
| NACOS_USERNAME | 否 | nacos | Nacos 用户名 |
| NACOS_PASSWORD | 否 | <password> | Nacos 密码 |
| CORS_ORIGINS | 否 | ["*"] | 生产改具体域名 |
| RATE_LIMIT_RECOGNIZE | 否 | 10/minute | |
| RATE_LIMIT_CHAT | 否 | 20/minute | |
| MAX_IMAGE_SIZE_MB | 否 | 5 | |
| LOG_LEVEL | 否 | INFO | |
| ENV | 否 | dev | dev / staging / prod |

### 12.4 与前端同源部署（推荐）

生产时把 `food-healing-demo/` 前端静态文件交给 FastAPI 托管：

```python
app.mount("/", StaticFiles(directory="../food-healing-demo", html=True), name="static")
```

这样前端请求 `/api/*` 同源，彻底消除 CORS 问题。

### 12.5 基础设施部署清单

**统一部署在服务器 `<your-server-ip>`，端口全部默认，密码统一 `<password>`（仅本赛事单机部署用）。**

| 组件 | 版本 | 端口 | 密码 | 备注 |
|---|---|---|---|---|
| MySQL | 8.0 | 3306 | <password> | charset=utf8mb4 |
| PostgreSQL | 16 | 5432 | <password> | 启用 JSONB |
| Redis | 7 | 6379 | <password> | 持久化可选 |
| RabbitMQ | 3.x | 5672 | <password> | 已选型 |
| Nacos | 2.x | 8848 | <password> | 单机即可，不做服务注册 |
| FastAPI | — | 8000 | — | gunicorn + uvicorn workers |
| Nginx | — | 80 / 443 | — | 反代 + 静态前端 |
| OSS | — | — | AccessKey | 阿里云托管，独立 bucket |

> **密码 `<password>` 仅限赛事单机部署**，真实生产必须用强密码 + Vault / KMS 管理。

---

## 13. 与前端对接约定

### 13.1 统一响应格式

```typescript
interface ApiResponse<T> {
  code: number;        // 0 成功
  message: string;
  data: T | null;
}
```

前端统一封装 fetch wrapper：
- `code === 0` → 返回 `data`
- `code !== 0` → 抛错，按错误码 toast

### 13.2 错误码表（v2.2 扩展为 5 段）

> 完整错误码表见 `docs/接口契约统一.md` §6。本表保留兼容旧码。

| 段 | 范围 | 含义 |
|---|---|---|
| 1xxxx | 10000-19999 | 业务错误（参数/状态/资源） |
| 2xxxx | 20000-29999 | AI 平台错误（VL/百练） |
| 3xxxx | 30000-39999 | 数据库错误（MySQL/Pg/Redis） |
| 4xxxx | 40000-49999 | 限流 / 鉴权 / 网关 |
| 5xxxx | 50000-59999 | 系统内部错误 |

| code | HTTP | 含义 | 前端处理 |
|---|---|---|---|
| 0 | 200 | 成功 | 正常消费 data |
| **1xxxx 业务** | | | |
| 10001 | 400 | 请求参数缺失 | toast 具体原因 |
| 10002 | 400 | 参数格式错误（含文件超限） | toast 具体原因 |
| 10003 | 404 | 资源不存在（用户/菜品/任务） | toast |
| 10004 | 409 | 状态冲突（如拼饭已满） | toast |
| 10005 | 422 | 业务校验失败 | 表单内联提示 |
| 10006 | 422 | 模式/分类枚举不合法 | 表单内联提示 |
| **2xxxx AI** | | | |
| 20001 | 502 | VL 调用失败（超时/限流） | toast "识别服务繁忙，重试" |
| 20002 | 502 | VL 识别结果无法解析 | 提示"没认出来，试试手写添加" |
| 20003 | 502 | 百练对话调用失败 | 降级到本地 `generateAiText()` |
| 20004 | 502 | 百练周报生成失败 | toast "周报稍后再试" |
| 20005 | 502 | 百练情绪治愈调用失败 | 返回兜底文案 |
| 20006 | 502 | 百练摘要生成失败 | 保留旧摘要兜底 |
| **3xxxx DB** | | | |
| 30001 | 500 | MySQL 连接失败 | toast "服务异常" |
| 30002 | 500 | PostgreSQL 连接失败 | toast "服务异常" |
| 30003 | 500 | Redis 连接失败 | toast "服务异常" |
| 30004 | 500 | 数据写入失败 | toast "保存失败，重试" |
| 30005 | 500 | 数据查询失败 | toast "查询失败" |
| **4xxxx 限流鉴权** | | | |
| 40001 | 400 | 请求参数错误（兼容旧码，等同 10002） | toast |
| 40101 | 401 | 未鉴权 / token 缺失 | 跳登录 |
| 40301 | 403 | 无权限 | toast |
| 40401 | 404 | 资源不存在（兼容旧码，等同 10003） | toast |
| 40801 | 408 | 识图任务超时 | toast "识别超时，重试" |
| 42201 | 422 | 参数校验失败（兼容旧码） | 表单内联提示 |
| 42901 | 429 | 触发限流 | toast "操作太频繁，稍后再试" |
| 42902 | 429 | AI 接口限流（严限） | toast "AI 累了，歇会儿" |
| **5xxxx 系统** | | | |
| 50000 | 500 | 服务内部错误 | toast "服务异常" |
| 50001 | 502 | VL 调用失败（兼容旧码，等同 20001） | toast |
| 50002 | 502 | 识别结果无法解析（兼容旧码，等同 20002） | toast |
| 50003 | 502 | 百练模型调用失败（兼容旧码，等同 20003） | 降级 |
| 50004 | 504 | 网关超时 | toast "网络慢了点" |
| 50005 | 502 | OSS 上传失败 | toast "图片上传失败，重试" |
| 50006 | 502 | MQ 投递失败 | toast "排队中，稍后再查" |

> 兼容旧码（4xxxx 段中的 40001/40401/42201 与 5xxxx 段中的 50001-50006）保留向后兼容，新接口优先用 1xxxx/2xxxx 段。

### 13.3 识图异步轮询流程（v2.2 调整为 1.5s/20 次）

```
前端 recognizeDish(file):
  res = POST /api/recognize-dish
  task_id = res.data.task_id        # v2.2 改 snake_case
  setTimeout(poll, 1500)            # v2.2 改 1.5s

poll():
  res = GET /api/recognize/result/{task_id}
  if res.data.status == "done":
     addFood(res.data.dish)          # v2.2 改字段名 dish
  elif res.data.status == "failed":
     toast("识别失败：" + res.data.error)
  else:
     if 轮询次数 < 20:                # v2.2 改 20 次（30s 硬约束）
        setTimeout(poll, 1500)
     else:
        toast("识别超时")
```

### 13.4 关键对齐点：识图返回字段 vs `addFood` 入参（v2.2 字段全 snake_case）

前端 `addFood(food)`（`js/main.js`）会 `push({ ...food, tray_id, is_custom:false })`。后端返回的 `data.dish` 必须能直接作为 `addFood` 入参：

| 前端 addFood 需要 | 后端返回是否提供 | 备注 |
|---|---|---|
| id | ✅ | 命中库用 f-id，未命中用 r-时间戳 |
| name | ✅ | |
| category | ✅ | 必须是 6 类之一 |
| unit | ✅ | 如 "份(150g)" |
| kcal | ✅ | |
| protein | ✅ | |
| carb | ✅ | |
| fat | ✅ | |
| confidence | ⛔ 不传给 addFood | 仅前端 UI 用 |
| matched | ⛔ 不传给 addFood | 前端决定是否提示"是不是这道？" |
| alternatives | ⛔ 不传给 addFood | 前端单独存 |

### 13.5 其他对齐点

- **模式 key**：前端 `MODES` 用 `daily / fitness / weight_loss`（注意 `weight_loss` 是下划线），后端枚举必须一致
- **分类枚举**：`['主食','肉类','蔬菜','蛋奶','汤品','水果']`，后端 `Literal` 完全照搬
- **餐次 key**：`breakfast / lunch / dinner`，与前端 `STRUCTURES` 一致
- **营养字段**：`kcal / protein / carb / fat`（carb 不是 carbohydrate），全链路统一
- **时间格式**：所有时间 ISO8601 带时区（`+08:00`）

### 13.6 前端改造点（v2.2 接口路径已对齐）

| 文件 | 改动 | 说明 |
|---|---|---|
| `js/main.js` `generateAiText()` | 新增 `generateAiTextRemote()` 调 `/api/chat`（SSE） | 原函数降级保留 |
| `index.html` | 弹窗新增"📷 拍照识菜"入口 | 调 `/api/recognize-dish` 异步轮询 |
| `js/main.js` | 新增 `recognizeDish(file)` + `pollResult(task_id)` | fetch + FormData + 1.5s 间隔轮询 |
| `js/main.js` | 周报页（新增） | 调 GET `/api/weekly-report?user_id=&week=` |
| `js/main.js` | 忌口设置（新增） | 调 `/api/preferences` |
| `js/main.js` | 用户习惯设置（新增） | 调 `/api/preferences` 写 user_habits |
| `js/main.js` | 情绪日记（新增） | 调 `/api/mood` |
| `js/main.js` | 健康档案（新增） | 调 GET/POST `/api/health/profile` |
| `js/main.js` | 运动记录（新增） | 调 GET/POST `/api/sport/records` |
| `js/main.js` | 分享卡片（新增） | 调 POST `/api/share-card`，展示 OSS 图 |
| `js/main.js` | 食堂菜单（新增） | 调 `/api/menu` |
| `js/main.js` | 匿名榜（新增） | 调 `/api/leaderboard` |
| `js/main.js` | 语音转菜盘（新增） | 调 `/api/voice-to-tray` |
| `index.html` | PWA manifest + service worker | 离线访问 |
| `js/admin.js` | B 端管理后台（新增） | 调 `/api/admin/*` |

`matcher()`、`calcNutrition()`、`mealDisplay`、营养环、模式切换等**完全不动**。

---

## 附录 A：风险与对策（V2 更新）

| 风险 | 影响 | 对策 |
|---|---|---|
| VL 识别准确率不足 | 体验差 | 模糊匹配回退 + alternatives 候选 + 手写添加兜底 |
| 双平台 API 限流/欠费 | 服务不可用 | 限流前置 + 模型降级 + 监控告警 + 双 Key 独立 |
| SSE 在代理下断连 | 对话中断 | 客户端自动重连 + 降级返回完整 JSON |
| user_habits 摘要生成失败 | 长期记忆滞后 | 异步重试 + 保留旧摘要兜底 |
| Redis 短期记忆丢失 | 对话上下文断 | 降级：从 MySQL 最近 mood_logs 推断 |
| Nacos 不可用 | 配置失效 | 本地 .env 兜底 + 启动时拉取缓存 |
| MQ 积压 | 识图延迟 | 监控队列长度 + 告警 + 限流降级 |
| MySQL/Pg 双库一致性 | 数据不一致 | 业务边界清晰，避免跨库事务；周报等只读 Pg |

## 附录 B：P0–P3 功能清单

| 优先级 | 功能 | 接口 | 依赖 |
|---|---|---|---|
| **P0** | 拍照识菜（OSS+MQ 异步+Redis 缓存） | `/api/recognize-dish` + `/api/recognize/result/{id}` | VL + OSS + MQ + Redis |
| **P0** | AI 营养搭子对话（SSE+用户习惯记忆） | `/api/chat` | 百练 + user_habits + Redis |
| **P1** | 智能推荐补菜 | `/api/recommend` | foods.json + user_habits |
| **P1** | AI 周报 | `/api/weekly-report` | 百练 max + Pg 窗口函数 |
| **P1** | 过敏/忌口管理 | `/api/preferences` | MySQL user_habits |
| **P1** | 多模态输入（语音转菜盘、外卖截图） | `/api/voice-to-tray` | 百练 plus / VL |
| **P1** | 分享卡片 | `/api/share-card` | 百练 flash + OSS + Pillow |
| **P2** | 食堂今日菜单 | `/api/menu` | MySQL + Nacos |
| **P2** | 同学搭配匿名榜 | `/api/leaderboard` | Redis ZSET + Pg |
| **P2** | 拼饭 | （social 模块扩展） | MySQL social_relations |
| **P2** | 菜品评价 | （扩展 `/api/dish/rating`） | MySQL dish_ratings |
| **P2** | 餐次时间提醒 | （MQ 定时 + PWA Push） | MQ + PWA |
| **P2** | 情绪日记 + AI 治愈话语 | `/api/mood` | 百练 flash |
| **P3** | 健康档案（BMI/目标） | `/api/health/profile` | MySQL health_profiles |
| **P3** | 运动数据接入（步数换 kcal 配额） | `/api/sport/record` | MySQL sport_records |
| **P3** | PWA 离线 | service worker + manifest | 前端 + 缓存 |
| **P3** | B 端管理后台 | `/api/admin/*` | MySQL 聚合 + Redis ZSET |

---

**文档结束。请评审后回复修改意见，评审通过后进入实现阶段。**
