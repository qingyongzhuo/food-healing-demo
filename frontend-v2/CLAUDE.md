# 食愈前端 — Claude.md

> 给 AI 协作助手的工程导航文档。读这一份就能快速定位代码、理解约定。
> 最后核对日期：2026-07-05（与 `frontend-v2` 实际代码一一对照）。

## 1. 项目概述

**食愈校园** 前端 — 面向校园学生的饮食记录 + AI 营养陪伴 App。Vue3 CDN 模式已废弃，当前为 **React 19 + Vite** 重构版（`frontend-v2`）。

- **定位**：移动端 H5，max-w-lg 居中，iOS 原生极简风格
- **设计语言**：纯白纸色背景 + 扁平白底卡片 + 苹果系统色；玻璃模糊仅用于浮层（Tab 栏、抽屉 Header、弹窗）
- **核心功能**：每日四餐记录（早/午/晚/加餐）+ 营养目标 + AI 对话陪伴 + 拍照识菜 + 消息通知 + 个人中心

## 2. 技术栈

| 层 | 技术 | 版本 | 说明 |
|---|---|---|---|
| 框架 | React | 19.2 | 函数组件 + Hooks |
| 构建 | Vite | 8.1 | 开发 `npm run dev`，生产 `npm run build` |
| 样式 | TailwindCSS | 4.3 | `@import "tailwindcss"` + CSS 变量 |
| 状态 | Zustand | 5.0 | `persist` 中间件持久化 |
| 路由 | 无 | - | 用 `activeTab` 状态切换页面（非 SPA router） |
| 动画 | Framer Motion | 12.42 | 页面切换 + 弹窗 + 进度条；统一用 `useReducedMotion()` 尊重系统偏好 |
| 图标 | @phosphor-icons/react | 2.1 | `regular` 细线性（iOS 风格） |
| 通知 | react-hot-toast | 2.6 | 顶部居中，玻璃样式 |
| 日期 | date-fns | 4.4 | 格式化日期 |
| 类型 | TypeScript | 6.0（dev） | 仅 devDependency，源码仍为 JSX |

**已移除**：liquid-glass-react（与 Vue3 CDN 不兼容，毛玻璃用 CSS 变量实现）

## 3. 目录结构

```
frontend-v2/
├── src/
│   ├── main.jsx               # React 入口
│   ├── App.jsx                # 根组件：未登录→AuthView；登录→按 activeTab 切页
│   ├── index.css              # 全局样式 + CSS 变量 + 深色模式 + .ios-toggle
│   │
│   ├── components/
│   │   ├── AuthView.jsx          # 登录/注册页（独立全屏，无 Tab）
│   │   ├── DiaryHeader.jsx       # 首页顶部：日期 + AI 摘要 + 头像/设置
│   │   ├── NutritionOverview.jsx # 营养概览：大热量数字 + 3 进度条 + 添加按钮
│   │   ├── MealCard.jsx          # 单餐卡片（早/午/晚/加餐）
│   │   ├── FoodSlidePanel.jsx    # 底部滑出食物选择面板
│   │   ├── FoodTag.jsx           # 食物标签（含分类色）
│   │   ├── GlassCard.jsx         # 扁平白底卡片封装（.card / .card-strong）
│   │   ├── PhotoRecognition.jsx  # 拍照识菜弹窗（上传 + 轮询 + 结果 + 加入餐次）
│   │   ├── BottomTab.jsx         # 底部 5 Tab 导航（首页/统计/拍照/消息/我的）
│   │   ├── AiFloatingButton.jsx  # 右下角 AI 悬浮按钮（仅首页显示）
│   │   ├── AiDrawer.jsx          # AI 营养师独立全屏页（右滑入，SSE 流式 + 拍照识别）
│   │   ├── NotificationsView.jsx # 消息通知页（分类切换 + 详情弹窗 + 一键清空）
│   │   └── ProfileView.jsx       # 我的页（用户信息 + 营养目标 + 数据管理 + 系统设置）
│   │
│   ├── stores/
│   │   ├── authStore.js          # token + user + login/register/logout（persist: food-auth）
│   │   ├── mealStore.js          # meals 今日餐食 + history 跨天归档（persist: food-meals）
│   │   ├── userStore.js          # 营养目标 target（persist: food-user）— 独立文件
│   │   ├── uiStore.js            # activeTab + theme + showAiDrawer + 通知开关（persist: food-ui）
│   │   └── notificationStore.js  # 本地通知列表 + 已读/清空（persist: food-notifications）
│   │
│   ├── lib/
│   │   ├── api.js                # 后端 API 封装（fetch + SSE + 401 处理 + ApiError.level）
│   │   └── nutrition.js          # calcNutrition + getBarColor + generateAiSummary
│   │
│   ├── hooks/
│   │   ├── useChat.js            # AI 对话 SSE 状态管理（增量拼接 + 取消）
│   │   └── usePhotoRecognition.js# 拍照识菜轮询状态（含 abort 卸载中断）
│   │
│   └── data/
│       └── foods.js              # 45 条食物数据 + CATEGORIES + CATEGORY_META + CAT_TEXT_VAR + DEFAULT_TARGET + MEAL_SLOTS
│
├── index.html                  # 字体：Geist / Geist Mono / Noto Sans SC
├── vite.config.js              # 端口 5173，proxy /api /static → :8000
├── .gitignore                  # node_modules / dist / *.log / 编辑器目录
└── package.json
```

## 4. 页面结构

### 4.1 页面切换逻辑（`App.jsx`）

未登录直接渲染 `<AuthView />`；登录后用 Zustand `activeTab` 切换：

```jsx
{activeTab === 'profile' ? <ProfileView />
 : activeTab === 'message' ? <NotificationsView />
 : activeTab === 'stats' ? <StatsPlaceholder />
 : <HomePage />}
```

| activeTab | 页面 | 组件 |
|---|---|---|
| `home` | 首页（默认） | DiaryHeader + NutritionOverview + MealCard ×4 |
| `stats` | 数据统计 | 占位提示「数据统计功能即将上线」（未实现） |
| `photo` | 拍照识菜 | **不切页**，点击 Tab 调 `openPhotoModal()` 弹窗 |
| `message` | 消息通知 | NotificationsView（分类切换 + 详情弹窗） |
| `profile` | 我的 | ProfileView |

**常驻浮层**：BottomTab（z-40）、AiFloatingButton（仅 home 页，z-20）、AiDrawer（z-50）、PhotoRecognition（z-50）、FoodSlidePanel（z-50）。

### 4.2 首页布局（`activeTab === 'home'`）

```
DiaryHeader          # 日期 + AI 摘要 + 头像/设置按钮
NutritionOverview    # 大热量数字 + 3 条进度条 + AI 提示文案 + 添加餐食按钮
MealCard × 4         # 早餐 / 午餐 / 晚餐 / 加餐
BottomTab            # 固定底部
AiFloatingButton     # 右下角悬浮（仅首页）
AiDrawer             # 全屏覆盖（点击悬浮按钮触发）
PhotoRecognition     # 弹窗（点击底部拍照 Tab 触发）
FoodSlidePanel       # 底部滑出（点击 MealCard 添加食物触发）
```

### 4.3 我的页面（`activeTab === 'profile'`，`ProfileView.jsx`）

```
用户信息大卡片       # 头像 + 昵称 + 「食愈会员」标签 + 编辑资料
营养目标卡片         # 大热量数字 + 蛋白/碳水/脂肪进度 + 调整身体方案按钮
数据管理卡片         # 收藏食材 / 数据备份 / 清除缓存（均 toast 占位）
系统设置卡片         # 深浅色开关 / 饮食提醒 / AI 推送 / 隐私 / 关于 / 退出登录
BottomTab           # 固定底部（"我的"高亮）
```

挂载时调 `api.getUserProfile()` 拉取完整 profile（含 `body_target`），同步到 `authStore.user` 和 `userStore.target`。

### 4.4 消息通知页（`activeTab === 'message'`，`NotificationsView.jsx`）

```
顶部玻璃栏           # 标题 + 一键清空按钮
横向分类标签         # 全部通知 / 饮食提醒 / AI 营养推送
消息列表             # 卡片：图标 + 标题 + 时间 + 正文 + 「查看详情 / 忽略」
详情弹窗             # 玻璃卡，whitespace-pre-line 渲染 detail
一键清空确认弹窗     # 二次确认，清空后不可恢复
```

数据来自 `notificationStore`，初始有 5 条 mock 通知。

### 4.5 弹窗 / 全屏页

| 组件 | 触发 | 形态 |
|---|---|---|
| `EditProfileModal` | ProfileView「编辑资料」 | 底部弹起卡片（昵称/头像/身高/体重/年龄/性别） |
| `GoalModal` | ProfileView「调整身体方案」 | 底部弹起卡片（减脂 1600 / 维持 2000 / 增肌 2400 kcal） |
| `PhotoRecognition` | BottomTab 拍照按钮 | **居中弹窗**（不是全屏页），含拍照/相册/识别中/结果/餐次选择 |
| `FoodSlidePanel` | MealCard 添加按钮 / NutritionOverview 按钮 | 底部滑出半屏面板 |
| `AiDrawer` | AiFloatingButton | **独立全屏页**（右滑入，覆盖整个 max-w-lg 区域） |
| `DetailModal` / `ConfirmDialog` | NotificationsView | 居中玻璃弹窗 |

## 5. 设计系统（`index.css`）

### 5.1 颜色规范

| 用途 | CSS 变量 | 值 |
|---|---|---|
| 页面背景（暖白纸色） | `--bg-primary` | `#F7F6F3` |
| 卡片白底 | `--bg-secondary` | `#FFFFFF` |
| 浅灰块/输入框底 | `--bg-tertiary` | `#F2F3F5` |
| 玻璃浮层背景 | `--glass-bg-strong` | `rgba(255,255,255,0.80)` |
| 玻璃模糊 | `--glass-blur` | `blur(18px) saturate(1.4)` |
| 系统蓝（按钮/选中） | `--accent` | `#007AFF` |
| 品牌色（Sunset Coral，仅 logo/小面积点缀） | `--brand` | `#E07856` |
| 健康绿 | `--success` | `#34C759` |
| 预警橙 | `--warning` | `#FF9500` |
| 危险红 | `--danger` | `#FF3B30` |
| 一级正文 | `--text-primary` | `#1D1D1F` |
| 辅助文字 | `--text-secondary` | `#86868B` |
| 三级文字 | `--text-tertiary` | `#AEAEB2` |
| 分割线 | `--border-color` | `#E5E5EA` |

**营养进度条色**：`--nut-protein`（绿）/ `--nut-carb`（米黄 #E8D9C6）/ `--nut-fat`（浅橙 #FFD9B8）

**食物分类色**（仅小标签，低饱和）：`--cat-staple/meat/veg/egg/soup/fruit` + 对应 `*-text` 文字色

### 5.2 圆角层级

| 类 | 变量 | 值 | 用途 |
|---|---|---|---|
| sm | `--radius-sm` | 8px | 标签 |
| md | `--radius-md` | 12px | 按钮 |
| lg | `--radius-lg` | 16px | 普通卡片（`.card`） |
| xl | `--radius-xl` | 20px | 大卡片（`.card-strong`） |
| full | `--radius-full` | 9999px | 头像/开关 |

### 5.3 卡片与玻璃规范（重要）

- **内容卡片**用扁平白底：`.card`（白底 + #EAEAEA 细边框 + 微阴影 + 16px 圆角）、`.card-strong`（同上 + 20px 圆角 + 稍重阴影）。`<GlassCard>` 组件封装这两个类。
- **玻璃模糊仅用于浮层**：`.glass-overlay`（`--glass-bg-strong` + `backdrop-filter`）— BottomTab、AiDrawer Header/输入栏、NotificationsView Header、AiFloatingButton、FoodSlidePanel。
- **不再有** `.glass-card` 类。设计上「卡片用白底、浮层用玻璃」是硬规则。

### 5.4 深色模式

`[data-theme="dark"]` 切换全部 CSS 变量（背景转纯黑 `#000000`，文字反白，玻璃改深色折射）。由 `uiStore.theme` + `App.jsx` 同步到 `document.documentElement.dataset.theme`。品牌色在深色模式稍亮一档（`#F08A6A`）保证对比度。

### 5.5 通用类

- `.card` / `.card-strong` — 扁平白底卡片
- `.glass-overlay` — 玻璃浮层（仅浮层用）
- `.btn-primary` — 蓝色实心主按钮（页面唯一强视觉主按钮）
- `.btn-secondary` — 浅灰描边次按钮
- `.btn-brand` — Sunset Coral 品牌按钮（仅 logo 区/品牌记忆点）
- `.ios-toggle` / `.ios-toggle.is-on` — iOS 原生开关
- `.font-number` — 等宽数字（Geist Mono + tabular-nums）
- `.overlay-backdrop` — 弹窗遮罩（rgba(0,0,0,0.25) + blur(6px)）
- `.scrollbar-none` — 隐藏滚动条（按需用，不全局隐藏）
- `.safe-top` / `.safe-bottom` — iOS 安全区 padding

## 6. API 接口对接（`lib/api.js`）

### 6.1 基础约定

- **BaseURL**：`/api`（Vite proxy 到 `localhost:8000`）
- **鉴权**：`Authorization: Bearer <token>`（从 `localStorage.token` 取）
- **统一响应**：`{ code, message, data }`，`code !== 0` 抛 `ApiError`
- **ApiError 结构**：`{ message, code, level }`，level ∈ `business` / `network` / `client` / `server` / `timeout`
- **401 处理**：动态 `import('react-hot-toast')` + 动态 `import('../stores/authStore')` 调 `resetAuth()`（不用 `logout`，避免循环请求后端）。组件层不处理。

### 6.2 已对接接口

| 前端方法 | 后端接口 | 说明 |
|---|---|---|
| `login(nickname, password)` | POST `/api/auth/login` | 登录（nickname 作账号） |
| `register(nickname, password, phone)` | POST `/api/auth/register` | 注册（phone 选填） |
| `logout()` | POST `/api/auth/logout` | 登出（调后端删 Redis 会话） |
| `getProfile()` | GET `/api/auth/me` | 查当前用户 |
| `updateProfile(data)` | PUT `/api/auth/profile` | 改昵称（旧接口） |
| `changePassword(old, new)` | PUT `/api/auth/password` | 改密码 |
| `uploadAvatar(file)` | POST `/api/auth/avatar` | 上传头像（FormData） |
| `submitRecognize(file)` | POST `/api/recognize-dish` | 提交识菜（FormData） |
| `pollRecognize(taskId)` | GET `/api/recognize/result/{taskId}` | 轮询识菜结果 |
| `recognizeWithPolling(file, opts)` | - | 封装：提交 + 轮询（最多 40 次 × 1.5s ≈ 60s，60s 硬超时） |
| `streamChat(body, handlers)` | POST `/api/chat?stream=true` | SSE 流式对话 |
| `getPreferences()` | GET `/api/preferences` | 后端占位 |
| `updatePreferences(data)` | PUT `/api/preferences` | 后端占位 |
| `getUserProfile()` | GET `/api/user/profile` | 用户中心（Phase 3，含 body_target） |
| `updateUserProfile(data)` | PUT `/api/user/profile` | 编辑基础资料（昵称/头像/手机号/主题） |
| `updateUserBody(data)` | PUT `/api/user/body` | 调整身体数据（height_cm/weight_kg/age/gender） |
| `updateUserTarget(data)` | PUT `/api/user/target` | 修改营养目标（daily_kcal/protein_g/carb_g/fat_g/target_type） |
| `listCollectFoods()` | GET `/api/user/collect` | 收藏食材列表 |
| `toggleCollectFood(foodId)` | POST `/api/user/collect/{foodId}` | 收藏/取消收藏（toggle） |
| `uploadCameraImage(file)` | POST `/api/camera/upload` | 拍照识菜上传（阶段 6，FormData） |
| `getCameraResult(taskId)` | GET `/api/camera/result?task_id=xxx` | 查询识菜结果 |
| `listCameraLogs(limit, skip)` | GET `/api/camera/logs?limit&skip` | 查询历史识别记录 |

### 6.3 SSE 协议（`streamChat`）

```js
streamChat(
  { persona, messages, context },
  {
    onDelta: (text) => {},      // 增量文本
    onDone: () => {},           // 完成
    onError: (err) => {},       // 错误
  }
);
// 返回 AbortController，可调 .abort() 取消
```

**事件解析**（与后端对齐）：
- `event: delta` → `onDelta(payload.delta)`
- `event: done` / `data: [DONE]` → `onDone()`
- `event: heartbeat` → 忽略

## 7. 状态管理（Zustand）

### 7.1 `authStore`（persist: `food-auth`，仅持久化 `token/user/isLoggedIn`）

```js
{
  token, user, isLoggedIn, authLoading, authError,
  resetAuth(),               // 仅清状态不发请求（401 自动登出用）
  clearAuthError(),          // 切换模式/改输入时清错误
  initAuth(),                // 应用启动校验 token：fetchProfile 失败时由 handleUnauthorized 处理
  async login(nickname, password),
  async register(nickname, password, phone),  // phone 选填
  async fetchProfile(),
  async logout(),            // 调 api.logout() + resetAuth() + persist.clearStorage()
  setUser(user),
}
```

**注**：`user.user_id` 为 number（后端 BIGINT）。401 由 `api.js` 自动调 `resetAuth()`，组件层不处理。

### 7.2 `mealStore`（persist: `food-meals`，持久化 `meals/todayDate/history`）

```js
{
  meals: { breakfast: [], lunch: [], dinner: [], snack: [] },
  todayDate,
  history: {},               // 跨天自动归档
  addFood(mealSlot, food),   // food._id 用 crypto.randomUUID()（带 fallback）
  removeFood(mealSlot, foodId),
  clearMeal(mealSlot),
  getNutrition(),            // 返回 { kcal, protein, carb, fat }；跨天返回 0
  _ensureToday(),            // 跨天自动归档到 history
}
```

### 7.3 `userStore`（persist: `food-user`，独立文件 `stores/userStore.js`）

```js
{
  target: { kcal: 2000, protein: 60, carb: 260, fat: 65 },  // 来自 DEFAULT_TARGET
  setTarget(target),
}
```

**注**：`mealStore.js` 末尾 `export { useUserStore } from './userStore'`，组件既可从 `mealStore` 也可从 `userStore` 导入（保持向后兼容）。

### 7.4 `uiStore`（persist: `food-ui`，**仅持久化 `theme/notifyMeal/notifyAi`**）

```js
{
  activeMeal: null,
  showSlidePanel: false,
  showProfile: false,
  chatExpanded: false,
  activeTab: 'home',         // home/stats/photo/message/profile
  showAiDrawer: false,
  showPhotoModal: false,
  theme: 'light',            // light/dark
  notifyMeal: true,
  notifyAi: true,
  openSlidePanel(mealSlot), closeSlidePanel(),
  toggleProfile(), toggleChat(),
  setActiveTab(tab),
  openAiDrawer(), closeAiDrawer(),
  openPhotoModal(), closePhotoModal(),
  toggleTheme(),
  setNotify(key, value),
}
```

### 7.5 `notificationStore`（persist: `food-notifications`，纯本地 mock）

```js
{
  notifications: [...],          // 初始 5 条 mock：diet/ai × positive/warning
  getByCategory(category),       // '全部通知' / '饮食提醒' / 'AI 营养推送'
  markAsRead(id),
  markAllRead(),
  removeAll(),
  remove(id),
  unreadCount(),
}
```

**通知结构**：`{ id, type: 'diet'|'ai', tone: 'positive'|'warning', title, body, time, icon: 'alarm'|'ai'|'plate', read, detail }`

## 8. 开发规范

### 8.1 组件规范

- **函数组件 + Hooks**，不用 class
- **样式优先级**：Tailwind 类 > CSS 变量 inline style > 独立 CSS 类
- **颜色必须用 CSS 变量**（`var(--accent)`），禁止硬编码 `#007AFF`
- **图标用 Phosphor `regular` 细线性**：`<Icon size={18} weight="regular" color="var(--accent)" />`（中心拍照按钮、Tab 选中态用 `weight="fill"`）
- **动画用 Framer Motion**：`transition={{ ease: [0.32, 0.72, 0, 1], duration: 0.3 }}`，必须用 `useReducedMotion()` 在「减少动效」时禁用动画
- **新组件内容卡片**用 `<GlassCard>` / `<GlassCard strong>` 包裹（实际是扁平白底，不是玻璃）

### 8.2 设计禁令

- **禁止紫光、霓虹发光、渐变背景**（品牌 logo 区允许 Sunset Coral 渐变作为唯一例外）
- **禁止 liquid-glass-react**（用 CSS 变量实现毛玻璃）
- **禁止大面积彩色**（彩色仅用于进度条、分类标签、状态提示）
- **禁止内容卡片用毛玻璃**（毛玻璃仅用于浮层：Tab 栏、抽屉 Header、弹窗）
- **禁止堆砌装饰插画**（iOS 原生设置页简约气质）
- ✅ 页面纯白纸色背景，大量留白，信息分层

### 8.3 状态规范

- **持久化数据**用 `persist` 中间件（auth/meals/user/ui/notifications）
- **临时 UI 状态**用 `useState`（弹窗显隐、表单输入）
- **跨组件共享**才放 Zustand，否则用 props 传递
- **401 处理**：`api.js` 自动调 `authStore.resetAuth()`，组件层不处理
- **状态更新用不可变模式**，避免直接修改前一个 state 引用
- **store 重置**用 `persist.clearStorage()`，不要手动操作 localStorage

### 8.4 文件组织

- 一个组件一个文件，文件名 = 组件名（PascalCase）
- 组件内私有子组件可同文件（如 `ProfileView.jsx` 内的 `EditProfileModal`、`GoalModal`；`NotificationsView.jsx` 内的 `NotificationCard`、`DetailModal`、`ConfirmDialog`）
- 公共工具放 `lib/`，自定义 Hook 放 `hooks/`，状态放 `stores/`，静态数据放 `data/`

### 8.5 ID 与时间规范

- 食物条目 `_id` 用 `crypto.randomUUID()`（带 `Date.now()+Math.random` fallback）
- ID 生成禁止用 `Date.now() + Math.random` 拼接（易碰撞）
- 跨天判断用 ISO 日期 `new Date().toISOString().slice(0, 10)`

## 9. 项目运行

### 9.1 前置条件

| 依赖 | 最低版本 | 说明 |
|---|---|---|
| Node.js | 18+ | 推荐 20 LTS；Vite 8 要求 Node 18+ |
| npm | 9+ | 随 Node 安装；或用 pnpm/yarn 替代 |
| 浏览器 | Chrome / Edge / Safari 最新版 | 需支持 `backdrop-filter`、`100dvh`、`crypto.randomUUID` |

> 后端服务**非必须**：前端可独立启动浏览 UI，但登录/注册/AI 对话/拍照识菜等接口功能需要后端在 `localhost:8000` 提供服务。当前仓库根目录未见 `backend/`，如需联调请先准备后端。

### 9.2 开发模式（日常使用）

```powershell
# 1. 进入前端目录
cd frontend-v2

# 2. 安装依赖（首次或拉取新依赖后执行）
npm install

# 3. 启动开发服务
npm run dev
```

启动成功后控制台会显示：

```
  VITE v8.1.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

浏览器访问 **http://localhost:5173** 即可。开发服务热更新（HMR）自动生效，改代码无需手动刷新。

**端口与代理**（`vite.config.js`）：
- 前端服务端口：`5173`
- API 代理：`/api` 和 `/static` 自动转发到 `http://localhost:8000`（后端）
- 即前端调 `/api/auth/login` 实际请求 `http://localhost:8000/api/auth/login`，避免跨域

### 9.3 联调后端

如果后端服务已就绪（监听 8000 端口）：

```powershell
# 终端 1：启动后端（按后端实际命令，FastAPI 示例）
cd backend
uv run uvicorn app.main:app --reload --port 8000

# 终端 2：启动前端
cd frontend-v2
npm run dev
```

打开 http://localhost:5173，登录后所有 `/api/*` 请求会经 Vite proxy 转发到后端。

### 9.4 生产构建与预览

```powershell
# 构建生产包（输出到 dist/，0 error 才算成功）
npm run build

# 本地预览生产构建（启动独立服务，端口默认 4173）
npm run preview
```

预览访问 **http://localhost:4173**。生产预览**不会**走 Vite proxy，如需联调后端需自行配置环境变量或反向代理。

> 仓库内已存在 `dist.tar.gz`，是历史构建产物压缩包，不影响运行；建议在 `.gitignore` 中追加 `*.tar.gz` 避免误提交。

### 9.5 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| `npm install` 报版本错误 | Node 版本过低，升级到 18+ |
| 启动后页面空白 | 浏览器控制台看报错；多为缓存问题，清 localStorage 后重试 |
| 登录提示「网络好像不太顺畅」 | 后端未启动或不在 8000 端口；检查 `vite.config.js` proxy 配置 |
| 登录后立刻被登出 | 后端返回 401，`api.js` 自动调 `resetAuth`；确认 token 有效 |
| 拍照识菜一直转圈 | 后端识别接口超时（>60s 自动失败）；检查 `/api/recognize-dish` |
| AI 对话无响应 | 后端 SSE 接口 `/api/chat?stream=true` 未就绪 |
| 样式错乱 / 颜色异常 | 检查 `index.css` CSS 变量是否被覆盖；深色模式看 `[data-theme="dark"]` |
| 端口 5173 被占用 | Vite 会自动切换到 5174/5175；或修改 `vite.config.js` 的 `server.port` |

### 9.6 完整命令速查

| 命令 | 用途 |
|---|---|
| `npm install` | 安装依赖（首次 / 拉取新代码后） |
| `npm run dev` | 启动开发服务（HMR + proxy） |
| `npm run build` | 生产构建到 `dist/` |
| `npm run preview` | 本地预览生产构建 |
| `npm run build && npm run preview` | 构建并预览（一行命令） |

## 10. 数据约定

### 10.1 食物数据（`data/foods.js`）

```js
{ id: 'f001', name: '白米饭', category: '主食', unit: '份(200g)', kcal: 230, protein: 5, carb: 50, fat: 1 }
```

- **6 大分类**：主食 / 肉类 / 蔬菜 / 蛋奶 / 汤品 / 水果
- **45 条预置数据**：主食 10 + 肉类 11 + 蔬菜 10 + 蛋奶 6 + 汤品 5 + 水果 3
- **导出**：
  - `FOODS_DATA` — 食物数组
  - `CATEGORIES` — `['主食', '肉类', '蔬菜', '蛋奶', '汤品', '水果']`
  - `CATEGORY_META` — `{ emoji, color }` 映射
  - `CAT_TEXT_VAR` — 分类标签文字色 CSS 变量映射（深一档保证可读）
  - `DEFAULT_TARGET = { kcal: 2000, protein: 60, carb: 260, fat: 65 }`
  - `MEAL_SLOTS` — 见下表

### 10.2 餐时槽位（`MEAL_SLOTS`）

| key | label | emoji | timeLabel |
|---|---|---|---|
| breakfast | 早餐 | 🌅 | 06:00-09:00 |
| lunch | 午餐 | ☀️ | 11:00-13:00 |
| dinner | 晚餐 | 🌙 | 17:00-19:00 |
| snack | **加餐** | 🍎 | 随时 |

**自动判断当前餐次**（`NutritionOverview.jsx` 的 `getCurrentMealSlot()`）：

| 时段 | 槽位 |
|---|---|
| < 10:00 | breakfast |
| 10:00-14:00 | lunch |
| 14:00-20:00 | dinner |
| ≥ 20:00 | snack |

## 11. 常见任务导航

| 我想... | 看哪里 |
|---|---|
| 加新页面 | `uiStore.activeTab` 加值 + `App.jsx` 条件渲染 |
| 加新组件 | `components/` 新建 + 内容用 `<GlassCard>` 包裹 |
| 改主题色 | `index.css` `:root` CSS 变量 |
| 加深色模式适配 | `index.css` `[data-theme="dark"]` 覆盖变量 |
| 对接新后端接口 | `lib/api.js` 加方法 + 组件调 |
| 加持久化状态 | `stores/` 新建或扩展 + `persist` 中间件 |
| 改底部 Tab | `components/BottomTab.jsx` 的 `TABS` 数组 |
| 改营养目标 | `stores/userStore.js` 的 `target`（写入同时调 `api.updateUserTarget`） |
| 加弹窗 | Framer Motion `AnimatePresence` + `.overlay-backdrop` + `.card-strong` |
| 加通知 | `stores/notificationStore.js` 加 mock 或对接后端推送 |
| 改 AI 抽屉 | `components/AiDrawer.jsx`（独立全屏页，5 层结构） |

## 12. 已知问题 + 待办

- **数据统计页**（`activeTab === 'stats'`）：仅占位提示「即将上线」，未实现
- **食物收藏列表**：ProfileView 点击「我的收藏食材」仅 toast，未实现列表页
- **数据备份**：仅 toast，未对接后端
- **清除缓存**：仅 toast，未实际清理
- **通知推送**：开关已就绪，后端推送未实现（`notificationStore` 纯本地 mock）
- **隐私设置**：仅 toast，未实现
- **忘记密码 / 第三方登录**：AuthView 内 toast 占位
- **AI 历史分析存档**：AiDrawer 顶栏「历史」按钮 toast 占位
- **dist.tar.gz**：仓库内存在构建产物压缩包，应纳入 `.gitignore`（当前 `.gitignore` 仅忽略 `dist` 目录，未忽略 `dist.tar.gz`）

## 13. 协作约定

- **改前端 API 调用必须同步看后端路由**（后端目录当前不在本仓库，需另行确认）
- **改 CSS 变量必须同步深色模式**（`[data-theme="dark"]`）
- **新增内容卡片必须用 `<GlassCard>`**（保持扁平白底一致性，不要用玻璃）
- **新增浮层**（Tab/抽屉/弹窗 Header）才用 `.glass-overlay`
- **构建前跑 `npm run build`** 确保 0 error（warning 可接受）
- **后端接口变更** → 同步更新本文件 §6.2 表格
- **新增 store** → 同步更新本文件 §7 + 在 `stores/` 下独立文件
- **新增组件** → 同步更新本文件 §3 目录结构 + §4 页面结构
