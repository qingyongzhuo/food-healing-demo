# 食愈校园 — 你的 AI 食堂搭子

> Food Healing Campus — AI-powered campus canteen companion

一个专为大学生打造的智能饮食管理平台。拍照识菜、AI 营养搭配、饮食日记、个性化推荐，让你的每一餐都吃得明明白白。

## ✨ 功能

- 📷 **拍照识菜** — 拍一张食材照，AI 推荐成品菜 + 营养数据 + 搭配建议
- 🤖 **AI 营养师对话** — 跟"小愈"聊聊今天的饮食，获取个性化建议
- 📊 **营养追踪** — 环形图 + 营养进度条，实时掌握今日摄入
- 🍽️ **餐次管理** — 早/午/晚/加餐，自由添加食物到菜盘
- 👤 **个人中心** — 身体数据、营养目标、头像昵称管理
- 🏆 **排行榜**（规划中）— 同学饮食 PK，互相监督
- 📅 **周报**（规划中）— AI 生成每周饮食总结

## 🛠️ 技术栈

### 前端
- React 19 + Vite 8
- Tailwind CSS 4 + 液态玻璃设计系统
- Zustand 状态管理
- Framer Motion 动画
- Phosphor Icons

### 后端
- Python 3.11+ / FastAPI
- PostgreSQL + Redis + RabbitMQ
- SQLAlchemy 2.0 异步 ORM
- Qwen-VL 视觉识别
- JWT 鉴权
- Docker 部署

## 📁 项目结构

```
food-healing/
├── frontend-v2/       # React 前端
│   ├── src/
│   │   ├── components/   # UI 组件
│   │   ├── stores/       # Zustand 状态
│   │   ├── hooks/        # 自定义 Hook
│   │   ├── lib/          # API / 工具函数
│   │   └── data/         # 食物数据
│   └── vite.config.js
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── routes/       # API 路由
│   │   ├── services/     # 业务逻辑
│   │   ├── models/       # ORM + Pydantic
│   │   └── utils/        # 工具函数
│   ├── Dockerfile
│   └── pyproject.toml
└── docs/              # 设计文档
```

## 🚀 快速开始

### 前端
```bash
cd frontend-v2
npm install
npm run dev
```

### 后端
```bash
cd backend
cp .env.example .env   # 编辑 .env 填入 API Key
uv sync
uv run uvicorn app.main:app --reload
```

### Docker
```bash
cd backend
docker build -t food-healing-backend .
docker run -d -p 8000:8000 --env-file .env food-healing-backend
```

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)
