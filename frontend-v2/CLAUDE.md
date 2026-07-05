# 食愈前端 — Claude.md

> 给 AI 协作助手的工程导航文档。读这一份就能快速定位代码、理解约定。

## 1. 项目概述

**食愈校园** 前端 — 面向校园学生的饮食记录 + AI 营养陪伴 App。Vue3 CDN 模式已废弃，当前为 **React 19 + Vite** 重构版（`frontend-v2`）。

- **定位**：移动端 H5，max-w-lg 居中，iOS 原生极简风格
- **设计语言**：iOS 18 液态玻璃（仅卡片模糊），纯白背景，苹果系统色
- **核心功能**：每日四餐记录（早/午/晚/零食）+ 营养目标 + AI 对话陪伴 + 拍照识菜 + 个人中心

## 2. 技术栈

| 层 | 技术 | 版本 | 说明 |
|---|---|---|---|
| 框架 | React | 19.2 | 函数组件 + Hooks |
| 构建 | Vite | 8.1 | 开发 `npm run dev`，生产 `npm run build` |
| 样式 | TailwindCSS | 4.3 | `@import "tailwindcss"` + CSS 变量 |
| 状态 | Zustand | 5.0 | `persist` 中间件持久化 |
| 路由 | 无 | - | 用 `activeTab` 状态切换页面（非 SPA router） |
| 动画 | Framer Motion | 12.42 | 页面切换 + 弹窗 + 进度条 |
| 图标 | @phosphor-icons/react | 2.1 | `regular` 细线性（iOS 风格） |
| 通知 | react-hot-toast | 2.6 | 顶部居中，液态玻璃样式 |
| 日期 | date-fns | 4.4 | 格式化日期 |

**已移除**：liquid-glass-react（与 Vue3 CDN 不兼容，改用 CSS 变量实现毛玻璃）

## 3. 目录结构

```
frontend-v2/
├── src/
│   ├── main.jsx               # React 入口
│   ├── App.jsx                # 根组件，按 activeTab 切换首页/我的
│   ├── index.css              # 全局样式 + CSS 变量 + 深色模式 + .ios-toggle
│   │
│   ├── components/
│   │   ├── AuthView.jsx       # 登录/注册页（独立全屏，无 Tab）
│   │   ├── DiaryHeader.jsx    # 首页顶部：日期 + 头像 + 设置
│   │   ├── NutritionOverview.jsx  # 营养概览卡片：大数字 + 三进度条 + 添加按钮
│   │   ├── MealCard.jsx       # 单餐卡片（早/午/晚/零食）
│   │   ├── FoodSlidePanel.jsx # 底部滑出食物选择面板
│   │   ├── FoodTag.jsx        # 食物分类标签
│   │   ├── GlassCard.jsx      # 液态玻璃卡片封装
│   │   ├── PhotoRecognition.jsx# 拍照识菜弹窗（上传 + 轮询）
│   │   ├── BottomTab.jsx       # 底部 5 Tab 导航（首页/统计/拍照/消息/我的）
│   │   ├── AiFloatingButton.jsx# 右下角 AI 悬浮按钮
│   │   ├── AiDrawer.jsx        # AI 对话右滑抽屉（SSE 流式）
│   │   └── ProfileView.jsx     # 我的页面（用户信息 + 营养目标 + 设置）
│   │
│   ├── stores/
│   │   ├── authStore.js       # token + user + login/register/logout（persist）
│   │   ├── mealStore.js       # meals 今日餐食 + useUserStore 营养目标（persist）
│   │   └── uiStore.js         # activeTab + theme + showAiDrawer + 通知开关（persist）
│   │
│   ├── lib/
│   │   ├── api.js             # 后端 API 封装（fetch + SSE + 401 处理）
│   │   └── nutrition.js       # 营养计算 + AI 摘要生成
│   │
│   ├── hooks/
│   │   ├── useChat.js         # AI 对话 SSE 状态管理
│   │   └── usePhotoRecognition.js  # 拍照识菜轮询状态
│   │
│   └── data/
│       └── foods.js           # 59 条食物数据 + DEFAULT_TARGET + MEAL_SLOTS
│
├── index.html
├── vite.config.js             # 端口 5173，proxy /api /static → :8000
└── package.json
```

## 4. 页面结构

### 4.1 页面切换逻辑

无 React Router，用 Zustand `activeTab` 状态切换：

```jsx
// App.jsx
{activeTab === 'profile' ? <ProfileView /> : <HomePage />}
```

| activeTab | 页面 | 组件 |
|---|---|---|
| `home` | 首页（默认） | DiaryHeader + NutritionOverview + MealCard ×4 |
| `stats` | 数据统计 | ⏳ 未实现 |
| `photo` | 拍照识菜 | 弹窗（不切页，openPhotoModal） |
| `message` | 消息 | ⏳ 未实现 |
| `profile` | 我的 | ProfileView |

### 4.2 首页布局（`activeTab === 'home'`）

```
DiaryHeader          # 日期 + 营养摘要 + 头像/设置
NutritionOverview    # 大号热量数字 + 3 条进度条 + 添加餐食按钮
MealCard × 4         # 早餐 / 午餐 / 晚餐 / 零食
BottomTab            # 固定底部
AiFloatingButton     # 右下角悬浮
AiDrawer             # 右滑抽屉（点击悬浮按钮）
```

### 4.3 我的页面（`activeTab === 'profile'`）

```
用户信息玻璃卡片      # 头像 + 昵称 + 「私人营养师记录账号」标签 + 编辑资料
营养目标玻璃卡片      # 大号热量 + 蛋白质/碳水/脂肪进度 + 一键切换方案按钮
数据管理玻璃卡片      # 收藏食材 / 数据备份 / 清除缓存
系统设置玻璃卡片      # 深浅色开关 / 饮食提醒 / AI 推送 / 隐私 / 关于 / 退出登录
BottomTab            # 固定底部（"我的"高亮）
```

### 4.4 弹窗

- `EditProfileModal`：编辑资料（昵称/头像/身高/体重/年龄/性别）
- `GoalModal`：调整营养方案（减脂 1600 / 维持 2000 / 增肌 2400 kcal）
- `PhotoRecognition`：拍照识菜（上传 + 进度 + 结果展示）
- `FoodSlidePanel`：底部滑出食物选择

## 5. 设计系统（`index.css`）

### 5.1 颜色规范

| 用途 | CSS 变量 | 值 |
|---|---|---|
| 页面背景 | `--bg-primary` | `#F7F8FA` |
| 卡片背景（液态玻璃） | `--glass-bg` | `rgba(255,255,255,0.72)` |
| 玻璃模糊 | `--glass-blur` | `blur(18px) saturate(1.4)` |
| 系统蓝（按钮/选中） | `--accent` | `#007AFF` |
| 健康绿 | `--success` | `#34C759` |
| 预警橙 | `--warning` | `#FF9500` |
| 危险红 | `--danger` | `#FF3B30` |
| 一级正文 | `--text-primary` | `#1D1D1F` |
| 辅助文字 | `--text-secondary` | `#86868B` |
| 分割线 | `--border-color` | `#E5E5EA` |

**食物分类色**（仅小标签）：`--cat-staple/meat/veg/egg/soup/fruit`

### 5.2 圆角层级

| 类 | 变量 | 值 | 用途 |
|---|---|---|---|
| sm | `--radius-sm` | 8px | 标签 |
| md | `--radius-md` | 12px | 按钮 |
| lg | `--radius-lg` | 16px | 卡片 |
| xl | `--radius-xl` | 20px | 大卡片 |
| full | `--radius-full` | 9999px | 头像/开关 |

### 5.3 深色模式

`[data-theme="dark"]` 切换全部 CSS 变量，由 `uiStore.theme` + `App.jsx` 同步到 `document.documentElement`。

### 5.4 通用类

- `.glass-card` / `.glass-card-strong` — 液态玻璃卡片
- `.btn-primary` — 蓝色实心主按钮
- `.btn-secondary` — 浅灰描边次按钮
- `.ios-toggle` / `.ios-toggle.is-on` — iOS 原生开关
- `.font-number` — 等宽数字
- `.overlay-backdrop` — 遮罩层

## 6. API 接口对接（`lib/api.js`）

### 6.1 基础约定

- **BaseURL**：`/api`（Vite proxy 到 `localhost:8000`）
- **鉴权**：`Authorization: Bearer <token>`（从 `localStorage.token` 取）
- **统一响应**：`{ code, message, data }`，`code !== 0` 抛 `ApiError`
- **401 处理**：清 `localStorage.token` + 调 `authStore.logout()`，UI 自动跳登录页

### 6.2 已对接接口

| 前端方法 | 后端接口 | 说明 |
|---|---|---|
| `login(nickname, password)` | POST `/api/auth/login` | 登录（nickname 作账号） |
| `register(nickname, password, phone)` | POST `/api/auth/register` | 注册（phone 选填） |
| `logout()` | POST `/api/auth/logout` | 登出（调后端删 Redis 会话） |
| `getProfile()` | GET `/api/auth/me` | 查当前用户 |
| `updateProfile(data)` | PUT `/api/auth/profile` | 改昵称 |
| `changePassword(old, new)` | PUT `/api/auth/password` | 改密码 |
| `uploadAvatar(file)` | POST `/api/auth/avatar` | 上传头像（FormData） |
| `submitRecognize(file)` | POST `/api/recognize-dish` | 提交识菜（FormData） |
| `pollRecognize(taskId)` | GET `/api/recognize/result/{taskId}` | 轮询识菜结果 |
| `recognizeWithPolling(file, opts)` | - | 封装：提交 + 轮询（最多 20 次，30s 超时） |
| `streamChat(body, handlers)` | POST `/api/chat?stream=true` | SSE 流式对话 |
| `getPreferences()` | GET `/api/preferences` | ⏳ 后端占位 |
| `updatePreferences(data)` | PUT `/api/preferences` | ⏳ 后端占位 |
| `getUserProfile()` | GET `/api/user/profile` | ✅ 用户中心（Phase 3） |
| `updateUserProfile(data)` | PUT `/api/user/profile` | ✅ 编辑基础资料（昵称/头像/手机号/主题） |
| `updateUserBody(data)` | PUT `/api/user/body` | ✅ 调整身体数据（身高/体重/性别/年龄） |
| `updateUserTarget(data)` | PUT `/api/user/target` | ✅ 修改营养目标（kcal/蛋白/碳水/脂肪/类型） |
| `listCollectFoods()` | GET `/api/user/collect` | ✅ 获取收藏食材列表 |
| `toggleCollectFood(foodId)` | POST `/api/user/collect/{foodId}` | ✅ 收藏/取消收藏（toggle） |
| `uploadCameraImage(file)` | POST `/api/camera/upload` | ✅ 拍照识菜上传（阶段 6，FormData） |
| `getCameraResult(taskId)` | GET `/api/camera/result?task_id=xxx` | ✅ 查询识菜结果 |
| `listCameraLogs(limit, skip)` | GET `/api/camera/logs?limit&skip` | ✅ 查询历史识别记录 |

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

### 7.1 `authStore`（persist: `food-auth`）

```js
{
  token, user, isLoggedIn, authLoading, authError,
  login(nickname, password),         // async，调 api.login
  register(nickname, password, phone), // async，调 api.register（phone 选填）
  fetchProfile(),
  async logout(),    // 调 api.logout() 删后端会话 + 清 token + 重置 state
  setUser(user),
}
```

**注**：`user.user_id` 为 number 类型（后端 BIGINT）。401 时 `api.js` 自动调 `authStore.logout()`，组件层不处理。

### 7.2 `mealStore`（persist: `food-meals`）

```js
{
  meals: { breakfast: [], lunch: [], dinner: [], snack: [] },
  todayDate,
  history: {},
  addFood(mealSlot, food),
  removeFood(mealSlot, foodId),
  clearMeal(mealSlot),
  getNutrition(),    // 返回 { kcal, protein, carb, fat }
  _ensureToday(),    // 跨天自动归档到 history
}

// useUserStore（persist: `food-user`）
{
  target: { kcal: 2000, protein: 60, carb: 260, fat: 65 },
  setTarget(target),
}
```

### 7.3 `uiStore`（persist: `food-ui`）

```js
{
  activeTab: 'home',         // home/stats/photo/message/profile
  showAiDrawer: false,
  theme: 'light',            // light/dark
  notifyMeal: true,
  notifyAi: true,
  showSlidePanel: false, activeMeal: null,
  showPhotoModal: false,
  setActiveTab(tab),
  openAiDrawer(), closeAiDrawer(),
  toggleTheme(),
  setNotify(key, value),
  openSlidePanel(mealSlot), closeSlidePanel(),
  openPhotoModal(), closePhotoModal(),
}
```

## 8. 开发规范

### 8.1 组件规范

- **函数组件 + Hooks**，不用 class
- **样式优先级**：Tailwind 类 > CSS 变量 inline style > 独立 CSS 类
- **颜色必须用 CSS 变量**（`var(--accent)`），禁止硬编码 `#007AFF`
- **图标用 Phosphor `regular` 细线性**：`<Icon size={18} weight="regular" color="var(--accent)" />`
- **动画用 Framer Motion**：`transition={{ ease: [0.32, 0.72, 0, 1], duration: 0.3 }}`

### 8.2 设计禁令

- ❌ **禁止紫光、霓虹发光、渐变背景**
- ❌ **禁止 liquid-glass-react**（用 CSS 变量实现毛玻璃）
- ❌ **禁止大面积彩色**（彩色仅用于进度条、分类标签、状态提示）
- ❌ **禁止堆砌装饰插画**（iOS 原生设置页简约气质）
- ✅ 仅卡片用液态玻璃，页面纯白背景
- ✅ 大量留白，信息分层

### 8.3 状态规范

- **持久化数据**用 `persist` 中间件（auth/meals/user/ui）
- **临时 UI 状态**用 `useState`（弹窗显隐、表单输入）
- **跨组件共享**才放 Zustand，否则用 props 传递
- **401 处理**：`api.js` 自动调 `authStore.logout()`，组件层不处理

### 8.4 文件组织

- 一个组件一个文件，文件名 = 组件名（PascalCase）
- 组件内私有子组件可同文件（如 `ProfileView.jsx` 内的 `EditProfileModal`）
- 公共工具放 `lib/`，自定义 Hook 放 `hooks/`

## 9. 常用命令

```powershell
# 进入前端目录
cd d:\desktop\Trae\food-healing-demo\frontend-v2

# 安装依赖
npm install

# 启动开发服务（端口 5173，自动 proxy 到后端 8000）
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

**开发流程**：
1. 启动后端：`cd backend && uv run uvicorn app.main:app --reload`
2. 启动前端：`cd frontend-v2 && npm run dev`
3. 浏览器访问 `http://localhost:5173`

## 10. 数据约定

### 10.1 食物数据（`data/foods.js`）

```js
{ id: 'f001', name: '白米饭', category: '主食', unit: '份(200g)', kcal: 230, protein: 5, carb: 50, fat: 1 }
```

- 6 大分类：主食 / 肉类 / 蔬菜 / 蛋奶 / 汤品 / 水果
- 59 条预置数据
- `DEFAULT_TARGET = { kcal: 2000, protein: 60, carb: 260, fat: 65 }`
- `MEAL_SLOTS = [{ key: 'breakfast', label: '早餐', icon: ... }, ...]`

### 10.2 餐时槽位

| key | label | 时间段（自动判断） |
|---|---|---|
| breakfast | 早餐 | < 10:00 |
| lunch | 午餐 | 10:00-14:00 |
| dinner | 晚餐 | 14:00-20:00 |
| snack | 零食 | ≥ 20:00 |

## 11. 常见任务导航

| 我想... | 看哪里 |
|---|---|
| 加新页面 | `uiStore.activeTab` 加值 + `App.jsx` 条件渲染 |
| 加新组件 | `components/` 新建 + 用 `GlassCard` 包裹 |
| 改主题色 | `index.css` `:root` CSS 变量 |
| 加深色模式适配 | `index.css` `[data-theme="dark"]` 覆盖变量 |
| 对接新后端接口 | `lib/api.js` 加方法 + 组件调 |
| 加持久化状态 | `stores/` 新建或扩展 + `persist` 中间件 |
| 改底部 Tab | `components/BottomTab.jsx` 的 `TABS` 数组 |
| 改营养目标 | `stores/mealStore.js` 的 `useUserStore.target` |
| 加弹窗 | Framer Motion `AnimatePresence` + `glass-card-strong` |

## 12. 已知问题 + 待办

- **数据统计页**（`activeTab === 'stats'`）：未实现
- **消息页**（`activeTab === 'message'`）：未实现
- **食物收藏列表**：ProfileView 点击「收藏食材」仅 toast，未实现列表页
- **数据备份**：仅 toast，未对接后端
- **清除缓存**：仅 toast，未实际清理
- **通知推送**：开关已就绪，后端推送未实现
- **隐私设置**：仅 toast，未实现

## 13. 协作约定

- **改前端 API 调用必须同步看后端** `backend/app/routes/`
- **改 CSS 变量必须同步深色模式**（`[data-theme="dark"]`）
- **新增组件必须用 `GlassCard`** 保持液态玻璃一致性
- **构建前跑 `npm run build`** 确保 0 error（warning 可接受）
- **后端接口变更** → 同步更新本文件 §6.2 表格
