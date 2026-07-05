# 食愈校园 — 前端技术设计文档

> 版本：v2.2（Phase 0 联调对齐版）
> 上一版：v2.0（v2.2 Phase 0 联调解决 16 处契约不一致，详见 `docs/接口契约统一.md`）
> 适用阶段：TRAE competition 初赛 → 决赛全功能落地（P0–P3 全做）
> 前端技术栈：Vue3（CDN）+ Tailwind（CDN）+ 自定义 CSS，纯静态，无构建工具
> 后端技术栈：Python + FastAPI，双 AI 平台（通义千问 VL 识图 + 阿里百练对话多模型路由）
> 量级：单校单食堂 <1 万用户
> 配套契约：`docs/接口契约统一.md`（v2.2 唯一契约源，前端字段全 snake_case，与后端一致）

---

## 1. 概述

### 1.1 产品定位升级

V1 定位"AI 食堂搭子"偏功能工具。V2 升级为 **"会成长、会记忆、会陪伴的校园饮食伙伴"**：

- **会成长**：长期跟踪健康档案、营养趋势、运动配额，周报月报看变化。
- **会记忆**：AI 搭子记得用户说过的"胃不舒服""对花生过敏""上周蛋白不够"，下次主动提起。
- **会陪伴**：AI 搭子有人设（食堂阿姨 / 学长 / 学姐），有情绪日记，有餐次提醒。

**差异化策略**：不做游戏化养成（竞品"食乐"已做），而做"治愈系陪伴 + 真懂你"——AI 搭子有人设、有长期记忆、有情绪温度。技术抓手是 `user_habits` 字段长期沉淀 + 人设化 prompt + SSE 流式打字感。

### 1.2 四大产品支柱

| 支柱 | 关键词 | 功能落点 |
|---|---|---|
| 看见（识） | 多模态输入 | 拍照识菜（异步轮询）、语音"我吃了红烧鸡和米饭"、外卖截图识别、手动 |
| 懂得（算） | 个性化营养 | 健康档案、过敏忌口、长期趋势、AI 周报（ECharts） |
| 陪伴（聊） | 有记忆的 AI 搭子 | 人设化对话、长期记忆、情绪日记、治愈话语、餐次提醒 |
| 连接（聚） | 校园社交 | 同学搭配匿名榜、拼饭、菜品评价、食堂今日菜单 + 推荐 |

### 1.3 设计原则（不可妥协）

1. **保留治愈系手机外壳**：所有 C 端新 UI 必须在 375×812 phone-frame 内呈现，桌面端不放大、不外溢。
2. **保留治愈系视觉**：新组件必须沿用 `Ma Shan Zheng` 标题字体、虚线 `#E8D5B7` 边框、暖橙 `#F97316` + 抹茶绿 `#84CC16` + 米纸 `#FEF9F0` 主色、圆角体系。
3. **CDN 模式不引构建工具**：所有新 JS 文件 `<script src>` 顺序加载，组件用 Vue3 全局 `app.component()` 或对象字面量挂载到 `window`。
4. **渐进增强**：后端不通时降级为现有本地行为（AI 文案回退到 `generateAiText()`，识菜回退到提示"网络不可用"），不能白屏。
5. **B 端后台破例**：食堂管理员视角的 B 端管理后台为独立桌面端页面，可破例桌面布局，但仍沿用治愈系色板与字体，保持品牌一致。
6. **性能优先级**：并发度 → 缓存 → 批处理。识图、AI 对话、推荐三者可并行触发，不串行 await。

### 1.4 非目标（明确不做）

- 不引入 Vue SFC、不引入 Vite / Webpack / Rollup
- 不引入 Pinia / Vuex（用 `reactive` 自建轻量 store）
- 不引入 TypeScript
- 不做游戏化养成系统（与竞品区隔）
- 不替换现有 `matcher()` 餐次匹配算法（保留前端餐次匹配，AI 后端只补充建议）

---

## 2. 现有架构分析（精简版）

### 2.1 现状

```
food-healing-demo/
├── index.html          # 375×812 phone-frame：状态栏 / 刘海 / Home 指示条
├── js/main.js          # 单 createApp，含 FOODS_DATA(47道菜)、matcher()、generateAiText()、addFood()、localStorage 持久化；现有"添加菜品"弹窗两 tab（搜索/自定义）
└── css/style.css       # 治愈系手写风：暖橙#F97316 / 抹茶绿#84CC16 / 米纸#FEF9F0 / 虚线#E8D5B7；Ma Shan Zheng 标题 / 霞鹜文楷 / Noto Sans SC 正文 / Fraunces 数字
```

### 2.2 优点（必须保留）

| 维度 | 现状 | 保留理由 |
|---|---|---|
| 视觉系统 | CSS 变量集中、字体分工清晰 | V2 新组件必须复用，不另起体系 |
| 手机外壳 | phone-frame 含状态栏 / 刘海 / 摄像头 / Home 指示条，375×812 固定 | C 端身份感来源 |
| 业务闭环 | FOODS_DATA + matcher + generateAiText + 营养环 + 餐次卡 + 菜盘 | 端到端可演示，P0 直接挂载 |
| 持久化 | foodTray / currentMode 走 localStorage | 重启不丢菜盘 |
| 动画细节 | fade-in-up / 打字机光标 / 达标 celebrate / tagPop / refresh spin / 超标脉冲 / 纸张 noise | 治愈感来源 |
| 可访问性 | role / aria-* 齐备、`prefers-reduced-motion` 兜底 | 保留并扩展 |

### 2.3 痛点（V2 需改造）

| 痛点 | V2 影响 |
|---|---|
| `main.js` 单文件 ~630 行耦合 | P0–P3 共十余功能会让 setup 内 ref 数量从 20+ 涨到 80+ |
| 无 API 层 | 双 AI 平台无法接入 |
| AI 文案 `generateAiText()` 是 if-else 模板 | 无法真实对话、无人设、无记忆 |
| 无路由 | 周报 / 菜单 / 榜单 / 设置 / B 端后台无处安放 |
| 无组件复用 | 弹窗 / 营养环 / AI 气泡都是字符串模板 |
| 无统一错误 / loading | 后端失败无 fallback UI |
| 无 token / 用户身份 | 社交功能（拼饭、榜单）需要身份 |
| AI 搭子无记忆载体 | `user_habits` 字段缺失，无法实现"真懂你" |

---

## 3. 功能改造清单（P0–P3 全功能）

> 每个功能给出：UI 设计 + 交互流程 + 状态变更 + 对应后端接口。重点详写标注的功能。

### 3.1 【重点】P0-1 拍照识菜（异步轮询 UI）

#### 3.1.1 UI 设计

现有"添加菜品"弹窗的 Tab 行追加第三个 tab：

```
[🔍 搜索] [✏️ 自定义] [📷 拍照]
```

三 tab 等分宽度会过窄，Tab 标题改为图标 + 短文字。Tab 选中态沿用现有 `--color-orange` 背景 + 白字。已选清单（`.tray-summary`）三 tab 共享，保持不动。

#### 3.1.2 关键 HTML 结构示意

```html
<div class="modal-body">
  <!-- 已选清单（三 tab 共用，保持不动） -->

  <!-- 拍照识菜 tab -->
  <div v-if="modalTab === 'photo'">
    <!-- 空态：上传区 -->
    <div class="photo-dropzone" v-if="!photoPreview && !recognizeTaskId">
      <input type="file" accept="image/*" capture="environment" @change="onPhotoPick">
      <div class="dropzone-hint">
        <svg><!-- 相机 SVG --></svg>
        <p class="empty-title">拍一张食堂菜品</p>
        <p class="empty-desc">AI 帮你认菜名 + 估营养</p>
      </div>
    </div>

    <!-- 识别中：异步轮询进度（关键差异点） -->
    <div v-if="recognizeTaskId && !recognizedDish && !recognizeError" class="photo-loading">
      <div class="loading-ring"></div>
      <p class="loading-title">AI 正在认菜... 预计 5~15 秒</p>
      <p class="loading-desc">{{ recognizeStatusText }}</p>
      <div class="loading-progress">
        <div class="loading-bar" :style="{ width: recognizeProgress + '%' }"></div>
      </div>
      <button @click="cancelRecognize" class="text-btn">取消</button>
    </div>

    <!-- 识别结果（可编辑确认） -->
    <div v-if="recognizedDish" class="photo-result">
      <img :src="photoPreview" class="photo-thumbnail">
      <div class="form-card">
        <p class="form-card-title">识别结果（可修改）</p>
        <input v-model="recognizedDish.name" class="input-field">
        <select v-model="recognizedDish.category"><!-- 6 个分类 --></select>
        <div class="grid grid-cols-2 gap-3">
          <input v-model.number="recognizedDish.kcal" type="number">
          <input v-model.number="recognizedDish.protein" type="number">
          <input v-model.number="recognizedDish.carb" type="number">
          <input v-model.number="recognizedDish.fat" type="number">
        </div>
        <input v-model="recognizedDish.unit" class="input-field">
        <p v-if="recognizedDish.confidence < 0.6" class="low-confidence">🤔 不太确定，请核对</p>
      </div>
      <button @click="confirmRecognizedDish" class="add-btn">确认添加到菜盘</button>
      <button @click="resetPhoto" class="text-btn">重新拍一张</button>
    </div>

    <!-- 失败态 -->
    <div v-if="recognizeError" class="photo-error">
      <p>识别失败：{{ recognizeError }}</p>
      <button @click="resetPhoto">重试</button>
    </div>
  </div>
</div>
```

#### 3.1.3 交互流程（异步轮询，V2 关键变化）

V1 设计为同步 `POST /api/recognize-dish` 直接返回结果。V2 因通义千问 VL 推理耗时 5~15 秒，改为**异步轮询**避免 HTTP 长连接超时：

1. 用户切到拍照 tab → 显示拖拽上传区（点击触发 `<input type="file" accept="image/*" capture="environment">`，移动端调起后置相机）。
2. 选图 → 前端做压缩（见 §12）→ 显示缩略预览 → 调 `POST /api/recognize-dish` 提交任务。
3. 后端立即返回 `{ task_id }`（不阻塞）→ 前端进入 loading 态，显示进度条（前端用模拟进度，0→80% 在前 3 秒线性增长，80% 后等待真实结果）。
4. 前端启动轮询 `GET /api/recognize/result/{task_id}`，间隔 1.5 秒，最多轮询 20 次（30 秒超时）。
5. 后端返回 `{ status: 'pending' }` → 继续轮询；返回 `{ status: 'done', dish: {...} }` → 填充 `recognizedDish` 表单（可编辑）。
6. 用户修改后点"确认添加到菜盘" → 调用现有 `addFood(recognizedDish)` 复用既有添加逻辑 → `showToast('✓ 已添加：' + name)` → 关闭弹窗。
7. 失败 / 超时 → 显示错误 + 重试按钮，不阻塞其他 tab。
8. **用户取消**：调 `POST /api/recognize/cancel/{task_id}`（可选，后端可忽略，task 自然过期）。

#### 3.1.4 状态变更（新增到 setup）

| 状态 | 类型 | 说明 |
|---|---|---|
| `modalTab` | ref<string> | 增加 `'photo'` 可选值 |
| `photoPreview` | ref<string \| null> | base64 缩略图 |
| `recognizeTaskId` | ref<string \| null> | 异步任务 id |
| `recognizeProgress` | ref<number> | 模拟进度 0–100 |
| `recognizeStatusText` | ref<string> | "排队中" / "识别中" / "估算营养" |
| `recognizedDish` | ref<Food \| null> | 复用 Food 字段 + confidence |
| `recognizeError` | ref<string> | 错误文案 |
| `pollingTimer` | ref<number \| null> | 轮询定时器，组件卸载时清除 |

#### 3.1.5 对应后端接口（异步轮询契约，v2.2 统一 snake_case）

```
POST /api/recognize-dish
请求: multipart/form-data, 字段 file (图片), user_id?, meal_hint?
响应: {
  code: 0, message: 'ok',
  data: { task_id: 'rec_xxx', status: 'pending' }
}

GET /api/recognize/result/{task_id}
响应（pending）: {
  code: 0, data: { task_id, status: 'pending', progress: 30 }
}
响应（done）: {
  code: 0, data: {
    task_id, status: 'done', progress: 100,
    dish: {
      id: 'r1690123456789',  // 后端生成，r 前缀表识菜（未命中库）
      name: string,
      category: '主食'|'肉类'|'蔬菜'|'蛋奶'|'汤品'|'水果',
      unit: string,
      kcal: number, protein: number, carb: number, fat: number,
      confidence: number,        // 0~1，VL 置信度
      matched: boolean,          // v2.2 新增：是否命中预置库
      alternatives: [Dish]       // v2.2 新增：多候选（最多 3 个）
    }
  }
}
响应（failed）: { code: 0, data: { task_id, status: 'failed', progress: 100, error: string } }

POST /api/recognize/cancel/{task_id}  (可选)
响应: { code: 0, message: 'ok', data: { cancelled: true } }
```

字段映射：`data.dish` 直接喂给现有 `addFood()`（字段完全一致，后端按 §8.2 对齐）。`confidence < 0.6` 时前端在表单标题加"🤔 不太确定，请核对"。`matched=false` 时前端可弹"是不是这道？"候选 alternatives。

---

### 3.2 【重点】P0-2 AI 营养搭子对话（SSE 流式 + 人设 + 记忆）

#### 3.2.1 UI 设计

现有 `.ai-bubble` 升级为可对话气泡区。**V2 关键新增：人设头像 + 记忆提示气泡**。

```html
<div class="ai-chat-panel">
  <!-- 顶部人设条（V2 新增） -->
  <div class="persona-bar">
    <span class="persona-avatar" v-html="persona.avatar"></span>
    <div>
      <p class="persona-name">{{ persona.name }}</p>
      <p class="persona-tagline">{{ persona.tagline }}</p>
    </div>
    <button class="persona-switch" @click="openPersonaPicker">切换</button>
  </div>

  <!-- 对话历史区（滚动） -->
  <div class="chat-history" ref="chatHistoryRef">
    <div v-for="msg in chatMessages" :key="msg.id" class="chat-msg" :class="msg.role">
      <!-- 记忆提示气泡：AI 主动提起过去 -->
      <div v-if="msg.role === 'assistant' && msg.memoryHint" class="memory-hint">
        <span class="memory-icon">🧠</span>
        <span>{{ msg.memoryHint }}</span>
      </div>
      <span v-if="msg.role === 'assistant'" class="ai-bubble-icon" v-html="aiIcon"></span>
      <div class="chat-bubble" :class="msg.role">
        <span :class="{ 'typing-cursor': msg.streaming }">{{ msg.text }}</span>
      </div>
    </div>
  </div>

  <!-- 输入区 -->
  <div class="chat-input-bar">
    <input v-model="chatInput" placeholder="问我点什么，比如 这餐蛋白够吗？"
           @keyup.enter="sendChat" :disabled="chatSending">
    <button @click="sendChat" :disabled="chatSending || !chatInput.trim()">
      <span v-html="sendIcon"></span>
    </button>
  </div>
</div>
```

视觉延续：

- assistant 气泡沿用现有 `.ai-bubble` 样式（暖黄渐变 + 虚线边框 + `Ma Shan Zheng` 字体 + `rotate(-0.3deg)`）。
- user 气泡用对偶配色：暖橙渐变 `linear-gradient(135deg, #F97316 0%, #FB923C 100%)` + 白字 + 右下角尖角。
- 输入区贴 phone-frame 底部（home indicator 上方），白底 + 顶部 1px 虚线分隔。
- 打字机光标 `.typing-cursor::after` 完全复用现有 CSS。
- **记忆提示气泡**（V2 新增）：浅蓝 `--color-blue` 10% 背景 + 虚线边框 + `🧠` 图标，置于 assistant 气泡上方，文案如"想起你说过胃不舒服"。
- **人设条**：置于对话区顶部，头像用 emoji（阿姨 👩‍🍳 / 学长 🧑‍🎓 / 学姐 👩‍🎓），名字用 `Ma Shan Zheng`，slogan 用 `霞鹜文楷`。

#### 3.2.2 交互流程

1. 应用启动时检查 `userPersona` 是否已设置：
   - 未设置 → 弹出人设选择 modal（首次进入强制选，见 §9）。
   - 已设置 → 用本地 `generateAiText()` 生成欢迎语（保留打字机效果）作为 `chatMessages` 第一条 assistant 消息，文案带人设口吻。
2. 用户输入 → push 一条 user 消息 → 清空输入框 → push 一条占位 assistant 消息（`streaming: true`，文本为空）。
3. 调 `POST /api/chat`（SSE 流式）→ 后端逐 token 返回 → 前端把 token 追加到占位消息的 `text` → 触发打字机光标动画。
4. SSE 流中可能收到 `memory_hint` 事件 → 前端在该 assistant 消息上挂 `memoryHint` 字段，渲染记忆气泡。
5. SSE `[DONE]` 事件 → 标记 `streaming: false` → 自动滚动到底部。
6. 失败 → 把占位消息替换为"AI 暂时没空，等下再问吧～"，并保留用户问题可重发。

#### 3.2.3 对话上下文策略（v2.2 统一 snake_case + 人设 ID）

每次请求带：

- `user_id`：用户标识，后端据此取 `user_habits`（长期记忆）+ Redis 短期记忆
- `persona`：当前人设 id（`canteen_aunt` / `senior_brother` / `senior_sister`，v2.2 改为完整 snake_case），后端据此切 prompt 模板。
- `messages`：最近 6 条消息（user / assistant 交替），过长会自动截断。后端可作为 fallback（主取 Redis）。
- `context`：当前菜盘摘要（`food_tray` 简化成 `{name, category, kcal}` 数组）+ 当前模式 + 营养总计 + 模式目标。
- `user_habits`：**前端不传**，由后端基于 `user_id` 从库中拉取（避免隐私与一致性问题）。前端只持久化 `allergens / healthProfile / persona` 用于本地拦截和离线兜底。

#### 3.2.4 状态变更（新增到 setup）

| 状态 | 类型 | 说明 |
|---|---|---|
| `chatMessages` | ref<Array<{id, role, text, streaming, memoryHint}>> | 完整对话历史 |
| `chatInput` | ref<string> | 输入框 |
| `chatSending` | ref<boolean> | 防止重复发送 |
| `chatHistoryRef` | ref<HTMLElement \| null> | 自动滚动控制 |
| `userPersona` | ref<string> | `'canteen_aunt' \| 'senior_brother' \| 'senior_sister'`（v2.2 改），持久化 |
| `personaPickerOpen` | ref<boolean> | 人设选择 modal 开关 |

#### 3.2.5 对应后端接口（v2.2 合并方案）

```
POST /api/chat
Content-Type: application/json
Accept: text/event-stream
响应: text/event-stream (SSE)

请求体（v2.2 合并 user_id + persona + messages + context）:
{
  user_id: 'u_demo',
  persona: 'canteen_aunt' | 'senior_brother' | 'senior_sister',
  messages: [{role: 'user'|'assistant', content: string}, ...],
  context: {
    food_tray: [{name, category, kcal}, ...],
    mode: 'daily'|'fitness'|'weight_loss',
    nutrition: {kcal, protein, carb, fat},
    mode_target: {kcal, protein, carb, fat}
  }
  // user_habits 后端基于 user_id 自取，前端不传
}

SSE 事件流（多事件类型）:
event: delta
data: {"delta":"今","done":false}

event: delta
data: {"delta":"天","done":false}

event: memory_hint
data: {"hint":"你上周说胃不舒服"}

event: heartbeat
data: {"type":"heartbeat"}

event: done
data: {"delta":"","done":true}

降级: POST /api/chat?stream=false → 一次性返回
{ code:0, data: { text: string, memory_hint?: string } }
```

前端实现：`fetch` + `ReadableStream` + `TextDecoder` 自行解析（兼容性比 EventSource 好，且支持 POST）。降级方案：SSE 不通时回退 `POST /api/chat?stream=false` 一次性返回完整文本。

---

### 3.3 【重点】P1 多模态输入（语音 / 外卖截图 / 手动）

V2 把"看见"支柱做多模态。拍照识菜（§3.1）已是主入口，本节补语音 / 截图 / 手动。

#### 3.3.1 UI 设计

在"添加菜品"弹窗的 Tab 行追加第四、五 tab（拍照 tab 之后）：

```
[🔍 搜索] [✏️ 自定义] [📷 拍照] [🎙️ 语音] [🍱 截图]
```

五 tab 等分宽度更窄，改为可滚动 Tab + 仅图标 + 下方小字（点击展开）。或把"搜索 / 自定义"合并为"手动"二级 tab。最终交互：Tab 行可横向滑动，宽度 60px/个。

```html
<!-- 语音 tab -->
<div v-if="modalTab === 'voice'">
  <div v-if="!voiceRecording && !voiceResult" class="voice-idle">
    <button class="voice-record-btn" @click="startRecord">
      <span class="voice-mic-icon">🎙️</span>
      <p>点一下，说出你吃了什么</p>
      <p class="voice-example">例："我中午吃了红烧鸡和一碗米饭"</p>
    </button>
  </div>
  <div v-if="voiceRecording" class="voice-recording">
    <div class="voice-wave"><!-- 波形动画 --></div>
    <p>正在听... 说完点停止</p>
    <button @click="stopRecord">停止</button>
  </div>
  <div v-if="voiceParsing" class="voice-parsing">
    <div class="loading-ring"></div>
    <p>正在解析你说的菜...</p>
  </div>
  <div v-if="voiceResult && voiceResult.dishes.length" class="voice-result">
    <p class="result-title">听出来这些菜，核对一下：</p>
    <div v-for="d in voiceResult.dishes" :key="d.id" class="voice-result-item">
      <input type="checkbox" v-model="d.checked">
      <span>{{ d.name }}</span>
      <span class="voice-result-meta">{{ d.kcal }} kcal</span>
    </div>
    <button @click="addVoiceResult" class="add-btn">加到菜盘</button>
  </div>
</div>

<!-- 截图 tab -->
<div v-if="modalTab === 'screenshot'">
  <div class="screenshot-dropzone">
    <input type="file" accept="image/*" @change="onScreenshotPick">
    <p class="empty-title">上传外卖订单截图</p>
    <p class="empty-desc">AI 识别订单里的菜品 + 估算营养</p>
  </div>
  <!-- 识别流程同拍照 tab，复用异步轮询组件 -->
</div>
```

#### 3.3.2 交互流程

- **语音**：调 `webkit SpeechRecognition` 录音 → 转文字 → POST `/api/parse-text-meal`（输入"我吃了红烧鸡和米饭"，后端用百练对话抽取菜品列表）→ 返回多道菜 → 用户勾选确认 → 批量 `addFood`。
- **截图**：与拍照同走异步轮询，但后端 prompt 不同（识别订单文字而非菜品图像），接口 `POST /api/recognize-receipt`。
- **降级**：浏览器不支持 SpeechRecognition（iOS Safari 部分版本）→ 语音 tab 显示"当前浏览器不支持，请改用搜索"。

#### 3.3.3 状态变更

| 状态 | 类型 |
|---|---|
| `voiceRecording` / `voiceParsing` | ref<boolean> |
| `voiceResult` | ref<{dishes: Array<Food & {checked}>} \| null> |
| `screenshotTaskId` | ref<string \| null> |

#### 3.3.4 对应后端接口（v2.2 snake_case）

```
POST /api/voice-to-tray  （别名 /api/parse-text-meal）
请求: { user_id: string, text: string, mode: string }
响应: { code:0, data: { tray: Food[] } }

POST /api/recognize-receipt
请求: multipart/form-data, 字段 file (图片), user_id?
响应: { code:0, data: { task_id: 'rec_xxx', status: 'pending' } }
// 轮询同 GET /api/recognize/result/{task_id}
```

---

### 3.4 P1 智能推荐补菜

#### 3.4.1 UI 设计

在菜盘下方（"添加食堂菜品"按钮上方）插入可关闭推荐卡，沿用 `.missing-hint` 风格（暖橙 10% 背景 + 虚线边框 + `Ma Shan Zheng` 标题）。

```html
<div v-if="recommendation" class="recommend-card fade-in-up">
  <button class="close-x" @click="recommendation = null">✕</button>
  <div class="recommend-icon">💡</div>
  <div class="recommend-content">
    <p class="recommend-title">AI 建议加点</p>
    <p class="recommend-name">{{ recommendation.name }}</p>
    <p class="recommend-reason">{{ recommendation.reason }}</p>
  </div>
  <button @click="addRecommend" class="recommend-add">＋ 加到菜盘</button>
</div>
```

#### 3.4.2 交互流程

- 菜盘变化后 debounce 3 秒调 `GET /api/recommend`（带模式 + 菜盘摘要 + user_habits 由后端拉取）。
- 后端返回推荐菜品 + 理由（如"今天蛋白少了 15g，来份鸡胸肉补一下"）。
- 用户点"加到菜盘" → `addFood(recommendation.dish)` → 推荐卡消失。
- 用户点 ✕ 关闭 → 当日内不再显示同款推荐（localStorage `dismissed_rec_YYYYMMDD` 记录菜品 id）。
- **记忆联动**：推荐理由可体现长期习惯，如"你最近总缺蛋白，今天又少了"。

#### 3.4.3 接口（v2.2 统一为 gaps + suggestions 数组）

```
GET /api/recommend?user_id=u_demo&mode=daily&tray=<URL-encoded JSON>
响应: {
  code:0, data: {
    gaps: string[],                         // 营养缺口分析
    suggestions: [{ ...Dish, reason: string }]  // 多候选，前端取 suggestions[0]
  }
}
```

---

### 3.5 P1 AI 周报（ECharts）

#### 3.5.1 UI 设计

顶部 nav-bar 头像左边加 📅 图标按钮，点击路由到 `/weekly-report`（P1 起引入 Vue Router）。

周报页内容：

- 顶部一周总览：日均 kcal / 达标天数 / 最佳一天。
- ECharts 折线图（CDN 按需引入）：x 轴 7 天，y 轴 kcal，目标线虚线。
- 三营养素堆叠柱状图。
- AI 周报文字段（后端总结，带人设口吻）。
- 底部"分享到朋友圈"按钮（与 §3.7 共享卡片组件复用）。

#### 3.5.2 数据来源

前端每天结束时把当日 `foodTray` + 营养总计存到 localStorage（key: `weekly_history_YYYYMMDD`）做本地兜底。**v2.2 改为后端从 PostgreSQL `nutrition_log` 聚合**，前端不传 7 天 body，仅带 `user_id` + `week` query。

#### 3.5.3 接口（v2.2 改 GET）

```
GET /api/weekly-report?user_id=u_demo&week=2026-W27
响应: {
  code:0, data: WeeklyReport {
    user_id, week_start, week_end,
    daily: [DailySummary],     // 7 条
    avg_kcal, hit_days,
    trend: 'up'|'down'|'flat',
    ai_summary: string         // AI 周报总结（qwen3.7-max，带人设口吻）
  }
}
```

ECharts CDN：`https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js`，仅周报页按需引入（不在 index.html 顶部 preload）。

---

### 3.6 P1 过敏 / 忌口管理

#### 3.6.1 UI 设计

顶部 nav-bar 头像点击进入设置页 `/settings`。

设置页内容：

- 忌口食材 chip 多选（花生 / 海鲜 / 牛奶 / 麸质 / 鸡蛋 / 坚果 / 牛肉 / 辛辣）。
- 自定义忌口输入框。
- 模式目标 kcal 微调滑块（可选，默认沿用模式预设）。

视觉沿用 `.filter-chip` 风格，选中态用 `--color-red`（忌口用红色警示色，区别于橙黄）。

#### 3.6.2 数据流

- 忌口列表存 localStorage `allergens` + 同步上传后端 `user_habits.allergens`。
- 用户添加菜品时（含识菜返回的），前端先匹配忌口：命中则弹"⚠️ 这道菜含 XX，确认要加吗？"拦截。
- 后端在推荐 / AI 对话时也避开。

#### 3.6.3 接口（v2.2 加 user_id + persona）

```
POST /api/preferences
请求: {
  user_id: string,
  allergens: string[],
  dislikes?: string[],
  goal?: 'daily'|'fitness'|'weight_loss',
  daily_kcal_target?: number,
  persona?: 'canteen_aunt'|'senior_brother'|'senior_sister'
}
响应: { code:0, message: 'ok', data: { saved: true } }
// 后端写入 user_habits 表
```

---

### 3.7 P1 分享卡片生成

#### 3.7.1 UI 设计

底部"添加食堂菜品"按钮上方加"📤 分享今日搭配"按钮。点击后：

1. 弹出全屏 modal，内含一张 1:1.2 比例的卡片预览。
2. 卡片内容：今日日期 / 三餐搭配缩略 / 营养环静态版 / AI 一句话点评 / "食愈校园"水印。
3. 卡片视觉必须延续治愈系：米纸背景 + 虚线边框 + `Ma Shan Zheng` 标题。
4. 底部"保存到相册" + "复制文案"两个按钮。

#### 3.7.2 实现方案

使用 `html2canvas`（CDN）把 DOM 转为 PNG。降级：加载失败提供"复制文案"按钮让用户截图分享。

#### 3.7.3 接口（v2.2 改 POST，提交数据生成卡片）

```
POST /api/share-card
请求: {
  user_id: string,
  date: 'YYYY-MM-DD',
  tray_summary: [{ name, category, kcal }],
  nutrition: { kcal, protein, carb, fat }
}
响应: {
  code:0, data: ShareCard {
    card_id, user_id, date, nutrition,
    dish_images: [string],     // OSS URL
    card_image_url: string,   // 生成的卡片图 OSS URL
    ai_comment: string,        // AI 一句话点评（qwen3.7-flash）
    created_at: string
  }
}
```

前端拿到 `card_image_url` 后展示，"保存到相册"按钮直接下载该 URL。"复制文案"按钮复制 `ai_comment`。

---

### 3.8 P2 食堂今日菜单页

#### 3.8.1 UI 设计

顶部 nav-bar 加"🍜 菜单"入口，路由到 `/menu`。

菜单页结构：

- 顶部 tab 切换：早 / 午 / 晚（按当前时间自动选中）。
- 菜品列表：每项含图（缺省用分类 emoji）+ 名 + 营养 + "加入菜盘"按钮。
- "今日推荐"高亮：3 道菜标红心 ❤️。

#### 3.8.2 接口（v2.2 响应对齐 CanteenMenu）

```
GET /api/menu?canteen=main&date=YYYY-MM-DD
响应: {
  code:0, data: CanteenMenu {
    canteen: 'main'|'east',
    date: 'YYYY-MM-DD',
    breakfast: [MenuItem],
    lunch: [MenuItem],
    dinner: [MenuItem]
  }
}
// MenuItem = Dish + { price?, available, station?, is_recommended }
// 推荐菜看 MenuItem.is_recommended 字段，前端高亮 ❤️
```

前端拿到后复用现有 `addFood()` 把菜单项加入菜盘。

---

### 3.9 【重点】P2 校园社交（同学搭配匿名榜 / 拼饭 / 菜品评价）

#### 3.9.1 UI 设计

入口同菜单页，新增 `/social` 路由，内含三个 tab：🏆 榜单 / 🍚 拼饭 / 💬 评价。

```html
<!-- 榜单 tab -->
<div class="leaderboard-list">
  <div class="my-rank" v-if="myRank">
    <p>我的排名 #{{ myRank.rank }}</p>
    <button @click="joinLeaderboard">上传我的今日搭配</button>
  </div>
  <div v-for="item in leaderboard.top" :key="item.nickname" class="rank-card">
    <span class="rank-num">{{ item.rank }}</span>
    <div class="rank-tray">
      <span v-for="f in item.tray_summary" :key="f.name" class="rank-food-chip">
        {{ categoryEmoji(f.category) }} {{ f.name }}
      </span>
    </div>
    <div class="rank-meta">
      <span class="rank-score">营养分 {{ item.score }}</span>
      <button @click="likeRank(item.nickname)" :class="{ liked: item.liked }">👍 {{ item.likes }}</button>
    </div>
  </div>
</div>

<!-- 拼饭 tab -->
<div class="pinfan-list">
  <button class="pinfan-create" @click="createPinfan">发起拼饭</button>
  <div v-for="p in pinfanList" :key="p.id" class="pinfan-card">
    <p class="pinfan-title">{{ p.host }} 想拼 {{ p.meal }}</p>
    <p class="pinfan-meta">📍 {{ p.canteen }} · ⏰ {{ p.time }} · 👥 {{ p.joined }}/{{ p.cap }}</p>
    <p class="pinfan-note">{{ p.note }}</p>
    <button @click="joinPinfan(p.id)" :disabled="p.joined >= p.cap">加入</button>
  </div>
</div>

<!-- 评价 tab -->
<div class="review-list">
  <div v-for="r in dishReviews" :key="r.id" class="review-card">
    <p class="review-dish">{{ r.dish_name }}</p>
    <div class="review-stars">★★★★☆</div>
    <p class="review-text">{{ r.text }}</p>
    <p class="review-author">{{ r.nickname }} · {{ r.time }}</p>
  </div>
</div>
```

视觉沿用治愈系：rank-card 用米纸底 + 虚线边框；pinfan-card 用暖橙 10% 背景；review-card 用白底圆角。

#### 3.9.2 交互流程

- **榜单**：用户点"上传我的今日搭配" → POST `/api/leaderboard/join`（带匿名 token）→ 后端返回排名 → 自己的卡片置顶高亮。
- **拼饭**：发起人填写餐次 / 食堂 / 时间 / 人数上限 / 备注 → 列表实时刷新（5 秒轮询或 SSE）。
- **评价**：在菜品详情或菜单页点菜品 → 写评价 → 列表展示匿名昵称。

#### 3.9.3 状态变更

| 状态 | 类型 |
|---|---|
| `leaderboard` / `myRank` | ref<object> |
| `pinfanList` | ref<Array> |
| `dishReviews` | ref<Array> |
| `socialTab` | ref<string> |

#### 3.9.4 接口（v2.2 snake_case 字段对齐）

```
GET /api/leaderboard?mode=fitness&limit=10
响应: {
  code:0, data: [
    { rank, anonymous_name, score, hit_days, mode }
  ]
}

POST /api/leaderboard/join
请求: { user_id, tray_summary: [...], mode }
响应: { code:0, data: { rank } }

GET /api/pinfan?date=YYYY-MM-DD&meal=lunch
POST /api/pinfan  (发起，请求 { user_id, meal, canteen, time, cap, note })
POST /api/pinfan/{id}/join  (响应 { joined, cap })

GET /api/dishes/{dish_id}/reviews
POST /api/dishes/{dish_id}/reviews  (请求 { user_id, rating, comment })
```

匿名 token 由后端首次访问时下发，前端存 localStorage，所有社交接口 Authorization 头携带。

---

### 3.10 P2 餐次时间提醒（Web Notification）

#### 3.10.1 UI 设计

设置页加"餐次提醒"开关 + 时间设置（早 7:30 / 午 11:30 / 晚 18:00 默认值）。

#### 3.10.2 实现方案

使用 Web Notification API：

- 首次开启请求 `Notification.requestPermission()`。
- `setInterval` 每分钟检查当前时间是否匹配餐次时间，命中且当天未提醒过则触发通知。
- 通知内容："该吃午餐啦～ AI 搭子已经为你准备好搭配建议"。
- 通知点击聚焦页面并滚动到对应餐次卡片。

降级：不支持 Notification 的浏览器用页面内 toast。

无后端接口。

---

### 3.11 P2 情绪日记 + AI 治愈话语

#### 3.11.1 UI 设计

底部加"😊 今天心情"快捷入口，点击进入情绪记录 modal：

- 5 个情绪 emoji 单选（😀 平静 / 😢 低落 / 😡 烦躁 / 😴 疲惫 / 🥰 开心）。
- 可选一句话描述输入框。
- 提交后 AI 返回治愈话语，显示在主页 AI 气泡上方临时浮层 3 秒后淡出。
- **V2 关键**：情绪数据写入 `user_habits.recent_moods`，AI 搭子后续对话可基于情绪状态调整口吻（如低落时更温柔）。

#### 3.11.2 接口（v2.2 合并方案：完整 MoodLog + suggestion）

```
POST /api/mood
请求: { user_id: string, mood: 'happy'|'calm'|'neutral'|'sad'|'stressed', note?: string }
响应: {
  code:0, data: {
    id: string,
    user_id: string,
    mood: string,
    note: string,
    created_at: string,        // ISO8601
    ai_comfort: string,        // AI 治愈话语（qwen3.7-flash）
    suggestion?: string       // 可选建议
  }
}
// 后端写入 user_habits.recent_moods
```

> v2.2 决策：合并前后端契约，后端 MoodLog 完整结构 + suggestion 可选字段。前端用 `ai_comfort` 显示治愈话语，`suggestion` 可选渲染为附加提示。

---

### 3.12 P3 健康档案（BMI / 目标）

#### 3.12.1 UI 设计

设置页增加"健康档案"分区：

- 身高 / 体重输入 → 自动算 BMI（前端计算 + 显示分级）。
- 目标选择：减脂 / 增肌 / 维持 / 控糖。
- 目标 kcal 自动推荐（可手动微调）。

#### 3.12.2 数据流

- 档案存 localStorage `health_profile` + 同步 `user_habits.profile`。
- 影响 `matcher()` 的模式目标（覆盖模式预设 kcal）。
- 周报页增加"目标达成度"维度。

#### 3.12.3 接口（v2.2 路径 /api/health/profile + snake_case）

```
GET /api/health/profile?user_id=u_demo
POST /api/health/profile
请求: {
  user_id: string,
  gender?: 'male'|'female'|'other',
  age?: number,
  height_cm?: number,
  weight_kg?: number,
  activity_level?: 'low'|'medium'|'high'
}
响应: {
  code:0, data: HealthProfile {
    user_id, gender, age, height_cm, weight_kg,
    bmi, activity_level, bmr, daily_kcal_target, updated_at
  }
}
```

> v2.2 决策：路径用 `/api/health/profile`（嵌套资源风格），后端自动算 BMI/BMR/daily_kcal_target。

---

### 3.13 P3 运动数据接入（步数换 kcal 配额）

#### 3.13.1 UI 设计

主页顶部营养环旁加"运动配额"小标签：

```
🎯 今日目标 1800 kcal  |  🏃 已得 220 kcal（5800 步）
```

#### 3.13.2 实现方案

- 优先 `navigator.permissions.query({name:'accelerometer'})` + `Sensor API`（实验性）。
- 降级：手动输入步数 / 接入 HealthKit（iOS）/ Google Fit（Android）通过 PWA。
- 步数 × 0.04 = kcal 配额，加到今日目标。

#### 3.13.3 接口（v2.2 路径 /api/sport/records + snake_case）

```
GET /api/sport/records?user_id=u_demo&date=YYYY-MM-DD
POST /api/sport/records
请求: {
  user_id: string,
  date: 'YYYY-MM-DD',
  steps: number,
  duration_min: number,
  source: 'manual'|'health_kit'|'mi_band'
}
响应: {
  code:0, data: SportRecord {
    id, user_id, date, steps, duration_min,
    kcal_burned, kcal_quota, source, created_at
  }
}
```

> v2.2 决策：路径用 `/api/sport/records`（嵌套资源风格），后端自动算 `kcal_burned = steps × 0.04 + duration_min × 5`，`kcal_quota = kcal_burned × 0.7`。

---

### 3.14 P3 PWA 离线

#### 3.14.1 实现方案

- `manifest.json`：定义图标 / 主题色（`#F97316`）/ 启动页。
- Service Worker：缓存 index.html / style.css / main.js / 常量 + FOODS_DATA。AI 调用走网络优先（network-first），失败回退缓存。
- 离线时显示"离线模式，仅可查看菜盘 + 本地菜品库"。

#### 3.14.2 降级

不支持 Service Worker 的浏览器（旧 iOS）正常使用在线模式，不报错。

---

### 3.15 【重点】P3 B 端管理后台（独立桌面端页面）

#### 3.15.1 定位

食堂管理员视角，**独立桌面端页面**，路由 `/admin`，独立入口 `admin.html`，与 C 端共用 `js/api.js` / `js/store.js` / 治愈系色板，但布局破例桌面端。

#### 3.15.2 入口

- C 端 `index.html` 底部加一个不起眼的"食堂管理员入口"链接（小字灰色），跳 `/admin`。
- `admin.html` 独立页面，加载 `js/admin/` 目录下的脚本。
- 简单口令登录（管理员 token 存 localStorage），不做完整账号体系（量级 <1 万，单人管理）。

#### 3.15.3 UI 设计（桌面端三栏布局）

```
┌─────────────────────────────────────────────────────────────┐
│  食愈校园 · 食堂管理后台            [今日 2026-07-03] [退出] │
├──────────┬──────────────────────────────────────────────────┤
│ 侧栏     │  主内容区                                        │
│          │                                                  │
│ 📊 概览  │  ┌─────────────┬─────────────┬─────────────┐    │
│ 🍲 菜品  │  │ 今日识别次数 │ 在线用户数  │ 平均营养分  │    │
│ 📈 热度  │  │    328      │    47       │    82       │    │
│ 🚫 滞销  │  └─────────────┴─────────────┴─────────────┘    │
│ 🥗 营养  │                                                  │
│ 📋 菜单  │  ┌────────────────────────────────────────┐     │
│ ⚙️ 设置  │  │  菜品热度 TOP 10（柱状图）              │     │
│          │  │  ECharts                               │     │
│          │  └────────────────────────────────────────┘     │
│          │                                                  │
│          │  ┌──────────────────┬─────────────────────┐    │
│          │  │ 滞销菜品（< 5 单）│ 营养统计（饼图）     │    │
│          │  │ - 苦瓜炒蛋 3 单  │ 蛋白 35% / 碳水 45%  │    │
│          │  │ - 凉拌海带 2 单  │ 脂肪 20%             │    │
│          │  └──────────────────┴─────────────────────┘    │
└──────────┴──────────────────────────────────────────────────┘
```

#### 3.15.4 功能模块

| 模块 | 功能 |
|---|---|
| 概览 | 今日识别次数 / 在线用户 / 平均营养分 / 实时识别流 |
| 菜品热度 | TOP 10 柱状图 + 列表（识别次数 / 加入菜盘次数 / 评分） |
| 滞销菜 | 7 天内 < 阈值订单的菜品（提示替换 / 改良） |
| 营养统计 | 学生整体营养均值 / 缺失项分布（饼图） |
| 菜单下发 | 早午晚菜单编辑 + 一键下发（写入 Nacos 配置中心） |
| 评价管理 | 查看菜品评价 + 回复 / 隐藏不当评价 |
| 设置 | 管理员口令 / 食堂信息 / 营养阈值 |

#### 3.15.5 菜单下发与 Nacos 联动

- 管理员在"菜单下发"页编辑今日菜单 → POST `/api/admin/menu`。
- 后端写入 Nacos 配置中心（data-id: `canteen_menu_YYYY-MM-DD`），C 端 GET `/api/menu` 实时拉取 Nacos 最新配置。
- 好处：菜单变更秒级生效，无需重启服务。

#### 3.15.6 状态变更（admin 独立 store）

| 状态 | 说明 |
|---|---|
| `adminStats` | 概览数据 |
| `dishHeat` | 菜品热度列表 |
| `unsoldDishes` | 滞销列表 |
| `nutritionStats` | 营养统计 |
| `menuDraft` | 菜单编辑草稿 |

#### 3.15.7 接口（v2.2 后端补全所有 admin 接口）

```
POST /api/admin/login                       (口令登录，返回 admin_token)
GET  /api/admin/overview                    (今日识别次数/在线用户/平均营养分)
GET  /api/admin/dish-heat?range=week        (菜品热度 TOP, Redis ZSET)
GET  /api/admin/unsold?days=7               (滞销菜列表)
GET  /api/admin/nutrition-stats?date=...     (营养统计 avg_kcal/avg_protein/user_count)
GET  /api/admin/canteen-stats?date=...      (食堂统计 top_dishes/slow_dishes/nutrition_stats)
POST /api/admin/menu                        (菜单下发到 Nacos)
GET  /api/admin/reviews                     (评价列表)
POST /api/admin/reviews/{id}/reply          (评价回复)
DELETE /api/admin/reviews/{id}              (隐藏不当评价)
```

admin 接口走单独的 admin token，与 C 端 user token 区分。除 `/api/admin/login` 外均需 `Authorization: Bearer {admin_token}`。

---

## 4. 状态管理升级

### 4.1 现状

`main.js` 把所有 `ref` 塞在 `setup()` 闭包里。V2 加十余功能后 ref 数量会从 20+ 涨到 80+，必须拆分。

### 4.2 升级方案：拆分轻量 store（不引第三方库）

新增 `js/store.js`，用 Vue3 `reactive` 创建全局 store，按域切分：

```javascript
// js/store.js  (示意，非完整实现)
const { reactive, ref } = Vue;

// 菜盘域（保留 localStorage 持久化）
export const trayStore = reactive({
  foodTray: JSON.parse(localStorage.getItem('foodTray') || '[]'),
  currentMode: localStorage.getItem('currentMode') || 'daily',
  save() {
    localStorage.setItem('foodTray', JSON.stringify(this.foodTray));
    localStorage.setItem('currentMode', this.currentMode);
  }
});

// AI 对话域（仅内存）
export const chatStore = reactive({
  messages: [],
  sending: false,
  persona: localStorage.getItem('persona') || '',  // canteen_aunt/senior_brother/senior_sister (v2.2 改)
});

// 识菜域（仅内存）
export const recognizeStore = reactive({
  preview: null,
  taskId: null,
  progress: 0,
  statusText: '',
  result: null,
  error: '',
});

// 用户偏好域（持久化 + 同步 user_habits）
export const prefStore = reactive({
  allergens: JSON.parse(localStorage.getItem('allergens') || '[]'),
  mealReminders: JSON.parse(localStorage.getItem('mealReminders') || '[]'),
  healthProfile: JSON.parse(localStorage.getItem('health_profile') || '{}'),
  save() { /* localStorage 写回 + 调 api.savePreferences 同步 user_habits */ }
});

// 社交域（仅内存，token 持久化）
export const socialStore = reactive({
  anonymousToken: localStorage.getItem('anon_token') || '',
  leaderboard: null,
  pinfanList: [],
});

// API 缓存域
export const cacheStore = reactive({
  menu: { data: null, expireAt: 0 },
  weeklyReport: { data: null, expireAt: 0 },
});

// B 端 admin 域（admin.html 独立使用）
export const adminStore = reactive({
  token: localStorage.getItem('admin_token') || '',
  stats: null,
  dishHeat: [],
  menuDraft: null,
});
```

### 4.3 user_habits 同步策略（V2 关键）

`user_habits` 是后端维护的用户长期记忆载体，字段示意：

```
user_habits = {
  allergens: string[],
  health_profile: { height, weight, goal, bmi },
  recent_moods: [{ mood, note, time }],  // 最近 30 条
  recent_nutrition_trends: [{ date, kcal, protein }],  // 最近 30 天
  mentioned_facts: [{ fact, time }],  // 对话中抽取的事实，如"胃不舒服""在减脂"
  persona: 'canteen_aunt' | 'senior_brother' | 'senior_sister'  // v2.2 改
}
```

**同步策略**：

| 数据 | 写入时机 | 前端做什么 |
|---|---|---|
| `allergens` | 用户改设置页 | 调 `POST /api/preferences` |
| `health_profile` | 用户改健康档案 | 调 `POST /api/health/profile`（v2.2 改路径） |
| `recent_moods` | 用户提交情绪日记 | 调 `POST /api/mood`（后端写） |
| `recent_nutrition_trends` | 每日 23:00 后端定时任务 | 前端不写，AI 对话时后端自取 |
| `mentioned_facts` | AI 对话过程中后端抽取 | 前端不写，AI 对话时后端自取 |
| `persona` | 用户切换人设 | 调 `POST /api/preferences`（v2.2 字段 persona） |

**关键约束**：前端不存 `user_habits` 明文，不传给 AI 接口，由后端基于 token 自取。前端只持久化 `allergens` / `healthProfile` / `persona` 用于本地拦截（如忌口弹窗）和离线兜底。

### 4.4 持久化策略表

| 数据 | 存储位置 | 期限 | 说明 |
|---|---|---|---|
| `foodTray` / `currentMode` | localStorage | 永久 | 复用现有 key |
| `allergens` / `health_profile` / `persona` | localStorage | 永久 | 新增，本地兜底 |
| `anon_token` / `admin_token` | localStorage | 永久 | 身份 |
| `weekly_history_YYYYMMDD` | localStorage | 30 天 | 每日一条，超 30 条触发清理 |
| `dismissed_rec_YYYYMMDD` | localStorage | 当日 | 推荐关闭记录 |
| `chatMessages` | 仅内存 | - | 关闭页面即清，避免隐私 |
| 识菜临时数据 | 仅内存 | - | 确认后即清 |
| 菜单 / 周报 API 结果 | cacheStore | 5 分钟 | TTL 过期重新请求 |
| `user_habits` 明文 | **不存前端** | - | 后端维护 |

### 4.5 兼容现有代码

迁移策略：现有 `foodTray` / `currentMode` ref 改为从 `trayStore` 引用，所有 `saveState()` 调用改为 `trayStore.save()`。其余 ref 暂保留在 setup 内，不强制一次性迁移。

---

## 5. API 调用层

### 5.1 新增文件 `js/api.js`

封装统一 fetch 调用，所有后端调用必走该层。

### 5.2 设计要点

```javascript
// js/api.js  (示意，非完整实现)
const API_BASE = window.API_BASE || 'http://localhost:8000/api';

// 统一响应格式 {code, message, data}
async function request(path, options = {}) {
  const url = API_BASE + path;
  const headers = { 'Accept': 'application/json', ...(options.headers || {}) };

  // token 预留（user / admin 区分）
  const token = options.admin
    ? localStorage.getItem('admin_token')
    : localStorage.getItem('anon_token');
  if (token) headers['Authorization'] = 'Bearer ' + token;

  // FormData 不强制 Content-Type，让浏览器自动带 boundary
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status);
  const json = await res.json();
  if (json.code !== 0) throw new ApiError(json.message || 'unknown error', json.code);
  return json.data;
}

class ApiError extends Error {
  constructor(message, code) { super(message); this.code = code; }
}

// 业务方法
export const api = {
  // P0-1 识菜（异步轮询，v2.2 关键封装）
  submitRecognize(file, userId) {
    const fd = new FormData();
    fd.append('file', file);                       // v2.2 字段名 file
    if (userId) fd.append('user_id', userId);      // v2.2 snake_case
    return request('/recognize-dish', { method: 'POST', body: fd });
  },
  pollRecognize(taskId) {
    return request('/recognize/result/' + taskId);
  },
  cancelRecognize(taskId) {
    return request('/recognize/cancel/' + taskId, { method: 'POST' });
  },
  // 轮询包装器：v2.2 1.5s 间隔 / 20 次 / 30s 硬约束
  async recognizeWithPolling(file, { onProgress, onStatus, userId } = {}) {
    const { task_id } = await this.submitRecognize(file, userId);
    for (let i = 0; i < 20; i++) {
      await sleep(1500);
      const r = await this.pollRecognize(task_id);
      onProgress && onProgress(r.progress || Math.min(95, (i + 1) * 5));
      onStatus && onStatus(r.status);
      if (r.status === 'done') return r.dish;       // v2.2 字段名 dish
      if (r.status === 'failed') throw new ApiError(r.error || '识别失败');
    }
    throw new ApiError('识别超时');
  },

  // P0-2 AI 对话（SSE 流式，单独处理）
  chatStream(payload, { onDelta, onMemoryHint, onDone, onError }) {
    // 使用 fetch + ReadableStream 解析 SSE
    // 多事件类型：delta / memory_hint / [DONE]
    // 降级 stream=false 模式
  },

  // P1-3 多模态：语音解析
  parseTextMeal(text, mode) {
    return request('/parse-text-meal', { method: 'POST', body: JSON.stringify({ text, mode }) });
  },
  // P1-3 多模态：外卖截图（同识菜异步轮询）
  submitRecognizeReceipt(file) { /* ... */ },

  // P1 推荐补菜
  getRecommend(mode, trayIds) {
    const qs = new URLSearchParams({ mode, tray: trayIds.join(',') });
    return request('/recommend?' + qs.toString());
  },

  // P1 周报（v2.2 改 GET，后端从 PostgreSQL 聚合，前端不传 7 天 body）
  getWeeklyReport(userId, week) {
    const qs = new URLSearchParams({ user_id: userId, week });
    return request('/weekly-report?' + qs.toString());
  },

  // P1 偏好 / 健康档案
  savePreferences(prefs) {
    return request('/preferences', { method: 'POST', body: JSON.stringify(prefs) });
  },
  saveHealthProfile(profile) {                          // v2.2 改路径
    return request('/health/profile', { method: 'POST', body: JSON.stringify(profile) });
  },
  getHealthProfile(userId) {
    return request('/health/profile?user_id=' + encodeURIComponent(userId));
  },

  // P2 菜单 / 榜单 / 拼饭 / 评价 / 情绪
  getMenu(canteen, date) {
    const qs = new URLSearchParams({ canteen, date });
    return request('/menu?' + qs.toString());
  },
  getLeaderboard(mode, limit) {
    const qs = new URLSearchParams({ mode, limit });
    return request('/leaderboard?' + qs.toString());
  },
  joinLeaderboard(payload) { /* POST /leaderboard/join */ },
  getPinfan(date, meal) { /* GET /pinfan?date=&meal= */ },
  createPinfan(payload) { /* POST /pinfan */ },
  joinPinfan(id) { /* POST /pinfan/{id}/join */ },
  getDishReviews(dishId) { /* GET /dishes/{id}/reviews */ },
  postDishReview(dishId, payload) { /* POST /dishes/{id}/reviews */ },
  postMood(payload) { /* POST /mood */ },

  // P3 运动（v2.2 改路径 /sport/records）
  postSportRecord(payload) {
    return request('/sport/records', { method: 'POST', body: JSON.stringify(payload) });
  },
  getSportRecords(userId, date) {
    const qs = new URLSearchParams({ user_id: userId, date });
    return request('/sport/records?' + qs.toString());
  },

  // P1 分享卡片（v2.2 改 POST）
  postShareCard(payload) {
    return request('/share-card', { method: 'POST', body: JSON.stringify(payload) });
  },

  // P1 多模态
  parseTextMeal(text, mode, userId) {
    return request('/voice-to-tray', { method: 'POST', body: JSON.stringify({ text, mode, user_id: userId }) });
  },

  // B 端 admin
  adminLogin(password) { /* POST /admin/login, admin: true */ },
  adminGetOverview() { /* GET /admin/overview, admin: true */ },
  adminGetDishHeat(range) { /* GET /admin/dish-heat?range= */ },
  adminGetUnsold(days) { /* GET /admin/unsold?days= */ },
  adminGetNutritionStats(date) { /* GET /admin/nutrition-stats?date= */ },
  adminGetCanteenStats(date) { /* GET /admin/canteen-stats?date= */ },
  adminPostMenu(menu) { /* POST /admin/menu */ },
  adminGetReviews() { /* GET /admin/reviews */ },
  adminReplyReview(id, reply) { /* POST /admin/reviews/{id}/reply */ },
  adminHideReview(id) { /* DELETE /admin/reviews/{id} */ },
};

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
```

### 5.3 统一错误处理策略

| 错误类型 | 用户可见反馈 | 数据影响 |
|---|---|---|
| 网络断开 | toast "网络好像不太顺畅～" | 保留本地状态，不阻塞 UI |
| HTTP 5xx | toast "服务打盹了，稍后再试" | 同上 |
| HTTP 4xx | toast "请求出错了：{message}" | 同上 |
| 识菜失败 / 超时 | 弹窗内显示错误 + 重试按钮 | 不关闭弹窗 |
| AI 对话失败 | 替换占位消息为"AI 暂时没空，等下再问吧～" | 保留用户问题可重发 |
| 业务 code !== 0 | toast 显示 message | 不写入 store |

### 5.4 Loading 状态统一管理

每个 API 调用配套一个 loading ref，由调用方持有（不在 api.js 全局管理，避免过度设计）。

### 5.5 双 AI 平台 key 不进前端

通义千问 VL API key + 阿里百练 API key 都不进前端代码、不进 localStorage。前端只调自己的 FastAPI 接口，由后端持有 key 转发。

---

## 6. 组件拆分建议

### 6.1 现状

`index.html` 内联字符串模板，无组件复用。V2 加十余功能后模板膨胀到无法维护。

### 6.2 拆分原则

**不强制重构**，优先拆"会被多处复用"或"逻辑复杂到影响可读性"的块。优先级：

| 优先级 | 组件 | 拆分理由 | 拆分方式 |
|---|---|---|---|
| 高 | `AddFoodModal` | 五 tab（搜索/自定义/拍照/语音/截图）+ 识菜异步轮询 + 语音流程，逻辑最重 | 独立 `js/components/add-food-modal.js` |
| 高 | `AiChatPanel` | SSE 流式 + 人设条 + 记忆气泡 + 打字机 | 独立 `js/components/ai-chat-panel.js` |
| 高 | `PersonaPicker` | 首次进入强制选择 + 设置页切换 | 独立 `js/components/persona-picker.js` |
| 中 | `NutritionRing` | 复用于周报页 / 分享卡片 | 可暂不拆，复用静态版本 |
| 中 | `RecommendCard` | 独立功能模块 | 独立 `js/components/recommend-card.js` |
| 中 | `WeeklyReportPage` | ECharts + 数据复杂 | 独立 `js/components/weekly-report-page.js` |
| 中 | `SocialModule` | 三 tab（榜单/拼饭/评价）| 独立 `js/components/social-module.js` |
| 中 | `ShareCard` | html2canvas + 卡片预览 | 独立 `js/components/share-card.js` |
| 低 | `MealCard` / `FoodTag` | 已有 3 个餐次复用，循环已够用 | 不拆 |

### 6.3 Vue3 CDN 模式下的组件实现

不使用 SFC，使用 `app.component()` 注册 + 字符串模板或 `template: '#xxx-tpl'`（写在 index.html 末尾的 `<script type="text/x-template">`）。

推荐：每个组件一个 JS 文件，导出对象字面量挂到 `window`，主入口 `main.js` 顺序加载后 `app.component('AddFoodModal', window.AddFoodModal)`。

```javascript
// js/components/add-food-modal.js  (示意)
window.AddFoodModal = {
  props: ['show'],
  emits: ['close', 'add'],
  setup(props, { emit }) {
    // ... 五 tab 状态 + 识菜异步轮询 + 语音流程 ...
    return { /* ... */ };
  },
  template: `
    <div v-if="show" class="modal-overlay" @click.self="emit('close')">
      <!-- ... -->
    </div>
  `
};

// js/main.js
const app = Vue.createApp({ /* root setup */ });
app.component('AddFoodModal', window.AddFoodModal);
app.component('AiChatPanel', window.AiChatPanel);
app.component('PersonaPicker', window.PersonaPicker);
app.mount('#app');
```

### 6.4 渐进迁移

- 第一阶段（P0）：拆 `AddFoodModal` / `AiChatPanel` / `PersonaPicker` 三个高优先级组件。
- 第二阶段（P1）：新功能（周报、菜单、社交）以独立组件 + 路由形式开发。
- 第三阶段（P3）：B 端后台在 `js/admin/` 下独立组件体系。
- 不重写已有功能代码（matcher / generateAiText / 营养环保持不动）。

---

## 7. 路由方案

### 7.1 选项对比

| 方案 | 复杂度 | 适合度 | 决策 |
|---|---|---|---|
| A. 单页 + 全 modal | 低 | P0 完全够，P1 后弹窗嵌套会乱 | P0 采用 |
| B. Vue Router CDN（hash 模式） | 中 | 多页面切换顺滑，URL 可分享 | P1 起采用 |
| C. 手写 hash 路由 | 低 | 不引第三方，但需自写切换动画 | 备选 |
| D. B 端后台独立 admin.html | 低 | 桌面端布局，与 C 端解耦 | P3 采用 |

### 7.2 决策

- **P0 阶段**：方案 A。两个 P0 功能（拍照加 tab、AI 改气泡）+ 人设选择 modal，都不需要新页面。
- **P1 阶段起**：方案 B。引入 Vue Router CDN（`https://unpkg.com/vue-router@4`），hash 模式。路由表：

```
/                    首页（菜盘 + 营养 + AI 对话 + 餐次卡 + 推荐卡）
/menu                今日菜单
/social             校园社交（榜单/拼饭/评价）
/weekly-report      周报
/settings            偏好 / 忌口 / 餐次提醒 / 健康档案 / 人设切换
/mood               情绪日记（也可作 modal 不开路由）
```

- **B 端后台**：方案 D。独立 `admin.html`，桌面端布局，与 C 端解耦，避免 C 端加载不必要的 ECharts / admin 逻辑。

### 7.3 路由切换动画

使用 Vue `<transition>` 包裹 `<router-view>`，切换时套用现有 `fade-in-up` 动画，保持视觉一致性。

### 7.4 不采用 history 模式

CDN 静态托管无服务端配合，history 模式刷新会 404。坚持 hash 模式。

---

## 8. 与后端接口契约对齐

### 8.1 统一响应格式

所有非 SSE 接口返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": { /* 业务字段 */ }
}
```

约定：

- `code === 0` 表示成功，非 0 表示业务错误。
- HTTP 状态码仍按 REST 规范（200/4xx/5xx），HTTP 错误也走 `code !== 0` 路径。
- `message` 永远面向用户可读，前端可直接 toast 显示。
- `data` 字段缺失时返回 `{}`，不返回 `null`。

### 8.2 字段映射到现有 addFood() 入参

现有 `addFood(food)` 接受字段：

```javascript
{
  id: string,
  name: string,
  category: '主食'|'肉类'|'蔬菜'|'蛋奶'|'汤品'|'水果',
  unit: string,
  kcal: number, protein: number, carb: number, fat: number
}
```

后端 `recognize-dish` / `recommend` / `menu` / `parse-text-meal` 等接口返回的 `data.dish` 字段必须严格对齐上述结构（字段名 + 类型 + 分类枚举值）。前端拿到后直接喂给 `addFood()`，不做字段转换。

`id` 由后端生成，按来源加前缀：

| 前缀 | 来源 |
|---|---|
| `f001` | 预置 FOODS_DATA |
| `custom_*` | 用户手动自定义 |
| `r001` | 拍照识菜 |
| `v001` | 语音解析 |
| `s001` | 外卖截图 |
| `m001` | 食堂菜单 |
| `rec_*` | 推荐补菜 |

前端 `addFood()` 内部会追加 `tray_id` 和 `is_custom` 字段（v2.2 改 snake_case，与后端 `TrayItem` 一致，省去转换层；V1 旧字段 `trayId`/`isCustom` 在迁移时一次性重命名）。

### 8.3 识图异步轮询契约（V2 关键变化）

V1 设计为同步 `POST /api/recognize-dish` 直接返回结果。V2 改异步轮询：

```
POST /api/recognize-dish
  → 立即返回 { task_id, status: 'pending' }
GET  /api/recognize/result/{task_id}
  → 轮询，返回 { status: 'pending'|'done'|'failed', progress?, dish?, error? }
POST /api/recognize/cancel/{task_id}  (可选)
```

轮询参数：前端 1.5s 间隔，最多 20 次（30s 超时）；进度条前端模拟（0→80% 前 3s 线性，80% 后等待真实结果）。

### 8.4 SSE 流式对话契约（V2 多事件类型）

```
POST /api/chat
Content-Type: application/json
Accept: text/event-stream

请求体（v2.2 合并 user_id + persona + messages + context，全 snake_case）:
{
  user_id: 'u_demo',
  persona: 'canteen_aunt' | 'senior_brother' | 'senior_sister',
  messages: [{role: 'user'|'assistant', content}, ...],
  context: {
    food_tray: [{name, category, kcal}, ...],
    mode: 'daily'|'fitness'|'weight_loss',
    nutrition: {kcal, protein, carb, fat},
    mode_target: {kcal, protein, carb, fat}
  }
  // user_habits 后端基于 user_id 自取，前端不传
}

SSE 事件流（v2.2 多事件类型，event: 前缀）:
event: delta
data: {"delta":"今","done":false}

event: delta
data: {"delta":"天","done":false}

event: memory_hint
data: {"hint":"你上周说胃不舒服"}

event: heartbeat
data: {"type":"heartbeat"}

event: done
data: {"delta":"","done":true}

降级: POST /api/chat?stream=false → 一次性返回 { code:0, data: { text: string, memory_hint?: string } }
```

### 8.5 user_habits 字段契约（V2 关键）

后端维护的 `user_habits` 表结构：

```
user_habits {
  user_id (token 关联),
  allergens: string[],
  health_profile: { height_cm, weight_kg, activity_level, daily_kcal_target, bmi, bmr, updated_at },
  recent_moods: [{ mood, note, time }],  // 最近 30 条
  recent_nutrition_trends: [{ date, kcal, protein }],  // 最近 30 天
  mentioned_facts: [{ fact, time }],  // 对话抽取的事实
  persona: 'canteen_aunt' | 'senior_brother' | 'senior_sister',
  updated_at: timestamp
}
```

前端不直接读写 `user_habits`，通过以下接口间接同步：

| 接口 | 写入字段 |
|---|---|
| `POST /api/preferences` | `allergens` / `persona` |
| `GET/POST /api/health/profile` | `health_profile` |
| `POST /api/mood` | `recent_moods` |
| AI 对话过程（后端抽取） | `mentioned_facts` |
| 后端定时任务（每日） | `recent_nutrition_trends` |

### 8.6 接口契约清单

| 接口 | 方法 | 用途 | 关键字段 |
|---|---|---|---|
| `/api/recognize-dish` | POST multipart | 提交识菜任务 | `data: {task_id, status}` |
| `/api/recognize/result/{task_id}` | GET | 轮询识菜结果 | `data: {status, dish?, error?}` |
| `/api/recognize/cancel/{task_id}` | POST | 取消任务（可选） | - |
| `/api/recognize-receipt` | POST multipart | 外卖截图识菜 | 同上 |
| `/api/voice-to-tray` | POST | 语音转菜盘 | `data: {tray: [Dish]}`（兼容别名 `/api/parse-text-meal`）|
| `/api/chat` | POST + SSE | AI 对话 | 流式 `delta` / `memory_hint` / `heartbeat` / `done` |
| `/api/recommend` | GET | 推荐补菜 | `data: {gaps, suggestions:[{...dish, reason}]}` |
| `/api/weekly-report` | GET | 周报总结 | `data: {daily, avg_kcal, hit_days, trend, ai_summary}` |
| `/api/preferences` | POST | 偏好 | 请求 `{user_id, allergens, daily_kcal_target, persona}` |
| `/api/health/profile` | GET / POST | 健康档案 | `data: HealthProfile`（含 `bmi`/`bmr`/`daily_kcal_target`）|
| `/api/sport/records` | GET / POST | 运动记录 | `data: SportRecord`（含 `kcal_burned`/`kcal_quota`）|
| `/api/menu` | GET | 今日菜单 | `data: CanteenMenu`（`MenuItem` 含 `is_recommended`）|
| `/api/leaderboard` | GET | 排行榜 | `data: [LeaderboardEntry]`（含 `anonymous_name`/`hit_days`）|
| `/api/leaderboard/join` | POST | 上传搭配 | `data: {rank}` |
| `/api/pinfan` | GET / POST | 拼饭列表 / 发起 | - |
| `/api/pinfan/{id}/join` | POST | 加入拼饭 | - |
| `/api/dishes/{id}/reviews` | GET / POST | 菜品评价 | - |
| `/api/mood` | POST | 情绪日记 | `data: MoodLog + suggestion?`（`ai_comfort`）|
| `/api/share-card` | POST | 分享卡片 | `data: ShareCard` |
| `/api/admin/*` | - | B 端后台 | admin token（详见 §3.15.7，10 个端点）|

### 8.7 联调 mock 建议

后端开发期间，前端 `js/api.js` 顶部加 `const USE_MOCK = true;` 开关，mock 数据写在 `js/api.mock.js`，方便并行开发。联调切回 `false`。

---

## 9. AI 搭子人设 + 记忆 UI 设计

### 9.1 三个人设

| id | 名称 | 头像 | slogan | 口吻示例 |
|---|---|---|---|---|
| `canteen_aunt` | 食堂阿姨 | 👩‍🍳 | "多打两勺，孩子饿瘦了" | "哎呀今天怎么没吃主食，阿姨给你多盛点米饭" |
| `senior_brother` | 学长 | 🧑‍🎓 | "练完得补蛋白，懂？" | "兄弟这餐蛋白差点意思，加个鸡腿" |
| `senior_sister` | 学姐 | 👩‍🎓 | "女孩子要好好吃饭" | "今天蔬菜不够哦，来份沙拉好不好" |

### 9.2 首次进入人设选择（强制）

应用首次启动 / `userPersona` 为空时，弹出全屏 modal：

```html
<div class="persona-picker-overlay">
  <div class="persona-picker-card">
    <h2 class="font-display">选一位 AI 搭子陪你吃饭</h2>
    <p class="handwritten">可以随时在设置里换</p>
    <div class="persona-options">
      <div class="persona-option" @click="pick('canteen_aunt')">
        <span class="persona-emoji">👩‍🍳</span>
        <p class="persona-name">食堂阿姨</p>
        <p class="persona-slogan">多打两勺，孩子饿瘦了</p>
      </div>
      <div class="persona-option" @click="pick('senior_brother')">
        <span class="persona-emoji">🧑‍🎓</span>
        <p class="persona-name">学长</p>
        <p class="persona-slogan">练完得补蛋白，懂？</p>
      </div>
      <div class="persona-option" @click="pick('senior_sister')">
        <span class="persona-emoji">👩‍🎓</span>
        <p class="persona-name">学姐</p>
        <p class="persona-slogan">女孩子要好好吃饭</p>
      </div>
    </div>
  </div>
</div>
```

视觉沿用治愈系：米纸底 + 虚线边框 + `Ma Shan Zheng` 标题 + 暖橙选中态。`persona-option` 三栏横排，hover / tap 时虚线边框变实线 + 暖橙描边。

选择后写入 `localStorage.persona` + `POST /api/preferences` 同步到 `user_habits.persona`，AI 欢迎语按人设口吻生成。

### 9.3 记忆提示气泡样式

```html
<div class="memory-hint">
  <span class="memory-icon">🧠</span>
  <span>{{ msg.memoryHint }}</span>
</div>
```

```css
/* 沿用治愈系色板 */
.memory-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(59, 130, 246, 0.1);  /* --color-blue 10% */
  border: 2px dashed #93C5FD;          /* 浅蓝虚线 */
  border-radius: var(--radius-md);
  padding: 4px 10px;
  font-size: 12px;
  color: var(--color-blue);
  font-family: 'LXGW WenKai', 'Ma Shan Zheng', sans-serif;
  margin-bottom: 4px;
}
```

记忆提示气泡置于 assistant 主气泡上方，浅蓝调区别于暖黄主气泡，不喧宾夺主。出现频率由后端控制（每 N 次对话最多 1 次），避免打扰。

### 9.4 设置页切换人设

设置页"AI 搭子"分区：

```html
<div class="settings-section">
  <p class="settings-section-title">AI 搭子</p>
  <div class="persona-switcher">
    <div v-for="p in personas" :key="p.id"
         class="persona-option"
         :class="{ active: userPersona === p.id }"
         @click="switchPersona(p.id)">
      <span class="persona-emoji">{{ p.emoji }}</span>
      <p class="persona-name">{{ p.name }}</p>
    </div>
  </div>
</div>
```

切换后写入 `localStorage` + `POST /api/preferences`，下一句 AI 回复立即换口吻，无需重启。

### 9.5 记忆来源与触发

记忆内容来自 `user_habits.mentioned_facts` + `recent_moods` + `recent_nutrition_trends` + `allergens`。后端在 AI 对话时判断当前对话上下文是否需要"提起"某条记忆：

- 用户当前菜盘含过敏原 → 触发记忆"你说过对花生过敏"
- 用户当前情绪日记显示低落 → 触发"今天心情不太好"
- 用户长期缺蛋白 → 触发"最近蛋白一直不够"

前端只渲染后端返回的 `memory_hint` 事件，不做主动判断。

---

## 10. 治愈系 UI 一致性规范

新组件必须遵守以下规范，避免破坏视觉统一。**B 端后台可破例桌面布局，但色板与字体仍需沿用。**

### 10.1 字体使用规范

| 场景 | 字体 family | CSS class |
|---|---|---|
| 大标题（页头、卡片标题） | `Ma Shan Zheng` | `.font-display` |
| AI 对话、温馨文案、人设口吻 | `Ma Shan Zheng` + `霞鹜文楷` fallback | `.handwritten` |
| 正文、按钮文字 | `Noto Sans SC` | 默认 |
| 数字（kcal、营养值） | `Fraunces` + tabular-nums | `.font-number` |

### 10.2 颜色使用规范

| 用途 | 颜色 | CSS 变量 |
|---|---|---|
| 主操作 / 主品牌 | 暖橙 | `--color-orange` `#F97316` |
| 达标 / 成功 | 抹茶绿 | `--color-green` `#84CC16` |
| 提示 / 信息 / 记忆气泡 | 天蓝 | `--color-blue` |
| 警告 / 超标 / 忌口 | 红 | `--color-red` |
| 背景 | 米纸 | `--color-bg` `#FEF9F0` |
| 卡片底 | 白 | `--color-card` |
| 虚线边框 | 浅米 | `#E8D5B7`（建议提为 `--color-dashed`） |

### 10.3 形状规范

- 圆角统一走 `--radius-sm/md/lg/xl/2xl`，禁止硬编码圆角值。
- 虚线边框统一 `2px dashed #E8D5B7`（记忆气泡可用浅蓝 `#93C5FD` 区分）。
- 卡片阴影统一走 `--shadow-sm/md/lg`，主按钮用 `--shadow-orange`。

### 10.4 间距规范

- 全部走 `--spacing-xs/sm/md/lg/xl`，禁止硬编码 px。
- 弹窗内 padding 沿用现有 `20px`。

### 10.5 动画规范

- 入场动画复用 `.fade-in-up`，配合 `animation-delay` 错峰 0.05s 一档。
- 微交互（hover、tap）用 `transition: all 0.2s ease`。
- 重要变化（达标、添加成功）用一次性 keyframe（celebrate / tagPop），不要常驻循环。
- 必须保留 `@media (prefers-reduced-motion: reduce)` 兜底。

### 10.6 移动端优先（C 端）

- 设计宽度基准 375px，禁止写死大于 375 的容器。
- 触控热区 ≥ 44×44px。
- 输入框 `font-size: 14px+`，避免 iOS 缩放。
- 长列表必须有 `max-height` + `overflow-y: auto`，避免撑破 phone-frame。

### 10.7 文案口吻

- 第一人称 + 人设化："我帮你搭好三餐"（阿姨口吻）、"练完得补蛋白"（学长口吻）。
- 用 emoji 但不滥用：标题级用 emoji，按钮级不放 emoji（除现有"＋ 添加食堂菜品"沿用）。
- 不出现"系统"、"失败"等冰冷词，改为"打盹了"、"网络不太顺畅"。

### 10.8 B 端后台例外

B 端后台可破例：

- 桌面端三栏布局，最大宽度 1440px。
- 不使用 phone-frame 外壳。
- 但字体 / 色板 / 圆角 / 虚线边框仍沿用治愈系，保持品牌一致。
- 数据可视化用 ECharts，主色用 `--color-orange` / `--color-green`。

---

## 11. B 端管理后台设计

### 11.1 独立页面

- 入口：`admin.html`，与 `index.html` 解耦。
- C 端 `index.html` 底部加小字灰色"食堂管理员入口"链接。
- 加载 `js/admin/` 目录下脚本，与 C 端组件体系完全独立。

### 11.2 桌面端布局

三栏布局（详见 §3.15.3）：左侧栏导航 + 右侧主内容区 + 顶部信息条。最大宽度 1440px，居中显示。

### 11.3 功能模块

| 模块 | 功能 | 数据源 |
|---|---|---|
| 概览 | 今日识别次数 / 在线用户 / 平均营养分 / 实时识别流 | `/api/admin/overview` |
| 菜品热度 | TOP 10 柱状图 + 列表（识别次数 / 加入菜盘次数 / 评分） | `/api/admin/dish-heat` |
| 滞销菜 | 7 天内 < 阈值订单的菜品（提示替换 / 改良） | `/api/admin/unsold` |
| 营养统计 | 学生整体营养均值 / 缺失项分布（饼图） | `/api/admin/nutrition-stats` |
| 菜单下发 | 早午晚菜单编辑 + 一键下发（Nacos） | `/api/admin/menu` |
| 评价管理 | 查看菜品评价 + 回复 / 隐藏不当评价 | `/api/admin/reviews` |
| 设置 | 管理员口令 / 食堂信息 / 营养阈值 | - |

### 11.4 Nacos 菜单下发联动

- 管理员在"菜单下发"页编辑今日菜单 → `POST /api/admin/menu`。
- 后端写入 Nacos 配置中心（data-id: `canteen_menu_YYYY-MM-DD`）。
- C 端 `GET /api/menu` 实时拉取 Nacos 最新配置，秒级生效。

### 11.5 鉴权

- 简单口令登录（`POST /api/admin/login`），admin token 存 localStorage。
- 不做完整账号体系（量级 <1 万，单人 / 少数管理员）。
- admin 接口走单独的 admin token，与 C 端 anonymous token 区分。

---

## 12. 性能优化

### 12.1 图片压缩 before upload（P0-1 必须）

识菜图片常达 2~5MB，直接上传会拖慢请求 + 占带宽。前端压缩：

```javascript
async function compressImage(file, maxSize = 800, quality = 0.8) {
  // 1. 用 createImageBitmap 或 URL.createObjectURL 加载
  // 2. canvas 按 maxSize 等比缩放
  // 3. canvas.toBlob('image/jpeg', quality)
  // 4. 返回 Blob
}
```

目标：输出 JPEG < 200KB，长边 ≤ 800px，质量足以让 VL 识别。

### 12.2 防抖（沿用现有模式）

- AI 文本更新：现有 300ms 防抖保留。
- 推荐请求：菜盘变化后 debounce 3 秒。
- 搜索：现有 `filteredFoods` 是 computed，无需额外防抖。
- 输入对话：发送按钮防连击（`chatSending` flag）。
- 拼饭列表刷新：5 秒轮询（或 SSE，后端有余力时升级）。

### 12.3 懒加载

- 周报页 ECharts：仅在用户进入 `/weekly-report` 时动态 `<script>` 加载 CDN。
- 菜单页图片：用 `loading="lazy"` 属性。
- 榜单头像：占位 emoji + Intersection Observer 懒加载真实头像。
- B 端后台 ECharts：仅 admin 页加载。

### 12.4 Intersection Observer 应用场景

- 周报页图表：进入视口才 `chart.init()`。
- 餐次卡：进入视口才触发 fade-in-up（替代当前全量 delay 触发）。
- 推荐卡片：滚到菜盘可见时才请求。
- B 端图表区：进入视口才渲染。

### 12.5 并发优化

- 识菜完成 → 加菜 + 触发推荐请求 + 更新 AI 文案，三者并发，不串行 await。
- 周报页进入时并行拉取：周报数据 + 历史趋势数据。
- 菜单页进入时并行拉取：早午晚三时段数据（按当前时段优先）。

### 12.6 缓存

- 菜单数据缓存 5 分钟（同日同餐次不变）。
- 推荐结果缓存 1 分钟（菜盘变化即失效）。
- B 端概览数据缓存 1 分钟。
- 静态菜品库 `FOODS_DATA` 改为常量（已经是 const），不变。

### 12.7 PWA Service Worker（P3）

- 缓存 index.html / style.css / main.js / constants.js / FOODS_DATA。
- AI 调用走 network-first，失败回退缓存。
- 离线时显示"离线模式，仅可查看菜盘 + 本地菜品库"。

### 12.8 不做的事

- 不做虚拟列表（菜品数 < 100 不需要）。
- 不做骨架屏（loading 用现有 `.loading-ring` 即可）。
- 不做图片 WebP 转换（兼容性问题，压缩 JPEG 已够）。

---

## 13. 前端目录结构调整

### 13.1 目标结构

```
food-healing-demo/
├── index.html                 # C 端入口（375×812 phone-frame）
├── admin.html                 # B 端入口（桌面端，P3）
├── manifest.json              # PWA（P3）
├── css/
│   ├── style.css              # 现有治愈系主样式（不动）
│   ├── components.css         # 新增组件样式（识菜、对话、推荐、人设、社交等）
│   ├── pages.css              # 路由页面样式（周报、菜单、榜单、设置）
│   └── admin.css              # B 端后台样式
├── js/
│   ├── main.js                # C 端入口（createApp + 注册组件 + mount）
│   ├── admin.js               # B 端入口
│   ├── store.js               # 轻量 store（reactive，C/B 共用）
│   ├── api.js                 # API 调用层（C/B 共用）
│   ├── api.mock.js            # 联调期 mock 数据（可选）
│   ├── constants.js           # FOODS_DATA / CATEGORIES / MODES / ICONS / PERSONAS 等常量
│   ├── utils.js               # calcNutrition / matcher / generateAiText / compressImage / sleep 等
│   ├── components/
│   │   ├── add-food-modal.js  # 添加菜品弹窗（五 tab）
│   │   ├── ai-chat-panel.js   # AI 对话面板（人设 + 记忆气泡）
│   │   ├── persona-picker.js  # 人设选择（首次 + 切换）
│   │   ├── recommend-card.js  # 推荐补菜卡
│   │   ├── nutrition-ring.js  # 营养环（可选拆分）
│   │   ├── meal-card.js       # 餐次卡（可选拆分）
│   │   ├── weekly-report-page.js  # 周报页（含 ECharts）
│   │   ├── menu-page.js       # 今日菜单页
│   │   ├── social-module.js   # 校园社交（榜单/拼饭/评价）
│   │   ├── share-card.js      # 分享卡片生成
│   │   ├── mood-modal.js      # 情绪日记
│   │   └── settings-page.js   # 偏好 / 忌口 / 餐次提醒 / 健康档案 / 人设切换
│   └── admin/
│       ├── overview.js        # 概览
│       ├── dish-heat.js       # 菜品热度
│       ├── unsold.js          # 滞销菜
│       ├── nutrition-stats.js # 营养统计
│       ├── menu-editor.js     # 菜单下发（Nacos）
│       ├── review-mgr.js      # 评价管理
│       └── login.js           # 管理员登录
└── docs/
    └── FRONTEND_DESIGN.md    # 本文档
```

### 13.2 加载顺序

`index.html` 底部按依赖顺序加载：

```html
<!-- 1. 第三方 -->
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<!-- Vue Router 按需加载（P1 阶段引入） -->
<!-- <script src="https://unpkg.com/vue-router@4"></script> -->

<!-- 2. 自有逻辑（顺序敏感） -->
<script src="js/constants.js"></script>
<script src="js/utils.js"></script>
<script src="js/store.js"></script>
<script src="js/api.js"></script>

<!-- 3. 组件（依赖 store + api） -->
<script src="js/components/persona-picker.js"></script>
<script src="js/components/add-food-modal.js"></script>
<script src="js/components/ai-chat-panel.js"></script>
<script src="js/components/recommend-card.js"></script>
<!-- ... 其他组件 ... -->

<!-- 4. 入口（最后加载，注册所有组件并 mount） -->
<script src="js/main.js"></script>
```

`admin.html` 加载顺序类似，但加载 `js/admin/` 下脚本，不加载 C 端组件。

### 13.3 迁移步骤

1. 先把 `FOODS_DATA / CATEGORIES / ICONS / MODES / STRUCTURES / CATEGORY_META / MODE_COLORS / PERSONAS` 抽到 `constants.js`。
2. 把 `calcNutrition / matcher / generateAiText / getBarColor / compressImage / sleep` 抽到 `utils.js`。
3. 新建 `store.js` / `api.js`。
4. 新功能直接以组件形式写在新文件，不再往 `main.js` 塞。
5. 现有 `index.html` 内联模板可暂不拆，等 P0 完成后再拆 `AddFoodModal` / `AiChatPanel` / `PersonaPicker`。
6. P3 阶段新建 `admin.html` + `js/admin/`。

---

## 14. 与后端联调注意事项

### 14.1 本地开发环境

- 前端：`http-server` 起在 `http://localhost:5500`。
- 后端：FastAPI 起在 `http://localhost:8000`。
- `js/api.js` 顶部 `API_BASE` 配为 `'http://localhost:8000/api'`，可通过 `window.API_BASE` 覆盖方便切环境。

### 14.2 CORS 配置

后端 FastAPI 必须配置 CORS：

```python
# 后端示意（非前端代码）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

注意：

- `allow_origins` 必须包含前端实际访问的 host（包括 IP 形式，真机调试时手机访问开发机 IP）。
- SSE 流式响应必须确认 nginx / 中间件不缓冲响应（`X-Accel-Buffering: no` 头）。
- 识菜 multipart 上传需调大 `max_upload_size`（建议 10MB）。
- 异步轮询接口（`GET /api/recognize/result/{task_id}`）每次请求耗时 < 50ms，避免轮询本身拖慢。

### 14.3 跨域图片

- `html2canvas` 生成分享卡片时，若图片来自后端域名（菜谱缩略图），后端必须返回 `Access-Control-Allow-Origin` 头，或前端用同域代理。
- 简化方案：分享卡片内只放 emoji + 文字 + 营养环 SVG，不嵌入外部图片。

### 14.4 双 AI 平台 key 不进前端

- 通义千问 VL API key + 阿里百练 API key 都不进前端代码、不进 localStorage。
- 前端只调自己的 FastAPI 接口（`/api/recognize-dish` / `/api/chat` 等），由后端持有 key 转发到对应平台。
- 部署时 key 通过环境变量注入后端，不写进配置文件仓库。

### 14.5 SSE 流式响应注意事项

- 后端响应头必须 `Content-Type: text/event-stream` + `Cache-Control: no-cache` + `Connection: keep-alive`。
- nginx / 反向代理必须关闭缓冲（`proxy_buffering off;`）。
- 每个 SSE 事件以 `data: ` 开头，以 `\n\n` 结尾。
- `[DONE]` 作为流结束标记。
- 后端要实现心跳（每 15 秒发一个 `data: {"type":"heartbeat"}`），避免代理超时断连。

### 14.6 联调清单

- [ ] 后端接口 base url 在前端 `js/api.js` 配置正确。
- [ ] CORS 在后端放开前端域名（含真机 IP）。
- [ ] SSE 流式响应不被中间件缓冲，有心跳保活。
- [ ] multipart 上传大小限制 ≥ 10MB。
- [ ] 接口响应统一 `{code, message, data}` 格式。
- [ ] `data.dish` 字段名与类型与前端 `addFood()` 入参对齐。
- [ ] 分类枚举值严格匹配 `['主食','肉类','蔬菜','蛋奶','汤品','水果']`（含中文）。
- [ ] 识图异步轮询：`POST /api/recognize-dish` 立即返回 `task_id`，`GET /result/{task_id}` 轮询。
- [ ] AI 对话 SSE 多事件类型：`delta` / `memory_hint` / `[DONE]`。
- [ ] `user_habits` 后端维护，前端不传明文，由后端基于 token 自取。
- [ ] 双 AI 平台 key 不进前端，由后端持有。
- [ ] 4xx / 5xx 错误返回 JSON 而非 HTML 错误页。
- [ ] 联调期前端 `USE_MOCK` 开关可独立切换每个接口。
- [ ] 部署环境下 `window.API_BASE` 通过运行期配置注入。

### 14.7 移动端真机调试

- 前端跑在开发机 `http://<开发机IP>:5500`，手机连同一 WiFi 访问。
- `js/api.js` 的 `API_BASE` 不能写 `localhost`，必须写开发机 IP（手机访问 localhost 会指向手机自己）。
- iOS Safari 调试：手机开启 Web 检查器，Mac Safari 开发者菜单连入。
- 摄像头 API 需 `https` 才能调用（`capture="environment"` 在 http 下不生效，本地用 127.0.0.1 例外）。
- 语音 `webkit SpeechRecognition` 在 iOS Safari 部分版本不支持，需做特性检测。

---

## 15. 里程碑与风险降级

### 15.1 P0 阶段（初赛核心，1~2 周）

1. 拆 `constants.js` / `utils.js`（半天）
2. 新建 `js/api.js` + `js/store.js`（1 天）
3. 拆 `PersonaPicker` 组件 + 首次进入人设选择（1 天）
4. 改造 `AddFoodModal` 加拍照 tab + 异步轮询（2 天，含图片压缩）
5. 后端联调 `POST /api/recognize-dish` 异步轮询
6. 改造 AI 气泡为 `AiChatPanel`，对接 SSE + 人设口吻 + 记忆气泡（2 天）
7. 后端联调 `POST /api/chat` SSE
8. 联调 + 视觉走查（1 天）

### 15.2 P1 阶段（增强，1 周）

- 多模态输入（语音 / 外卖截图）
- 推荐补菜 / 周报 / 偏好 / 分享卡片 / 健康档案
- 引入 Vue Router hash 路由
- 拆分组件文件

### 15.3 P2 阶段（校园特色，1 周）

- 菜单页 / 榜单 / 拼饭 / 评价 / 餐次提醒 / 情绪日记
- 视需要再拆组件

### 15.4 P3 阶段（进阶，复赛）

- PWA / 运动数据
- B 端管理后台（admin.html + Nacos 菜单下发）

### 15.5 风险与降级

| 风险 | 概率 | 影响 | 降级方案 |
|---|---|---|---|
| 通义千问 VL 识别食堂菜品准确率不足 | 中 | 识菜体验差 | 前端 confidence < 0.6 时提示用户核对，等于把识别降级为"半自动填表" |
| 识图异步轮询超时（> 30s） | 中 | 用户等待焦虑 | 30s 超时后提示"AI 有点忙，请稍后重试" + 重试按钮 |
| SSE 在某些代理下不通 | 低 | AI 对话不可用 | 降级为非流式 `POST /api/chat?stream=false` |
| 后端响应慢（> 5s） | 中 | 体验差 | loading 态 + 取消按钮 + 超时降级到本地文案 |
| 图片压缩后体积仍过大 | 低 | 上传失败 | 二次压缩到 quality 0.6，仍失败提示"换张图试试" |
| 手机端浏览器不支持 Notification | 高 | P2 餐次提醒不可用 | 降级为页面内 toast 提示 |
| 手机端不支持 SpeechRecognition | 高 | P1 语音输入不可用 | 语音 tab 显示"当前浏览器不支持，请改用搜索" |
| html2canvas 在治愈系虚线边框下渲染异常 | 中 | 分享卡片丑 | 降级为"复制文案"按钮 |
| localStorage 超 5MB 配额 | 低 | 周报历史写不进 | 自动清理 30 天前数据 |
| AI 搭子记忆提示频率过高打扰用户 | 中 | 体验差 | 后端控制每 N 次对话最多 1 次记忆提示，前端可关闭开关 |
| B 端后台 Nacos 配置延迟 | 低 | 菜单不生效 | 后端 fallback 兜底配置 + 前端刷新重试 |
| 社交功能匿名 token 丢失 | 低 | 榜单数据错乱 | token 持久化 + 后端允许重新生成 |

---

## 16. 评审检查清单

评审时请重点确认以下决策：

- [ ] 不引入构建工具、CDN 模式 OK
- [ ] 不引 Pinia / Vuex，用 reactive 自建 store OK
- [ ] P0 不开新路由，P1 起引入 Vue Router hash 模式，B 端后台独立 admin.html OK
- [ ] 识菜改异步轮询（POST 提交 → GET 轮询），前端模拟进度条 + 30s 超时 OK
- [ ] 识菜结果直接复用 `addFood()`，字段对齐后端契约 OK
- [ ] AI 对话用 fetch + ReadableStream 解析 SSE，非 EventSource（支持 POST）OK
- [ ] SSE 多事件类型：`delta` / `memory_hint` / `[DONE]` OK
- [ ] AI 搭子三人设（阿姨 / 学长 / 学姐），首次强制选 + 设置页切换 OK
- [ ] 记忆气泡浅蓝色 + 🧠 图标，频率后端控制 OK
- [ ] `user_habits` 后端维护，前端不存明文，只持久化 `allergens / healthProfile / persona` 兜底 OK
- [ ] 双 AI 平台 key 不进前端，后端持有 OK
- [ ] 渐进增强：后端不通时降级到本地 `generateAiText()` OK
- [ ] 治愈系视觉规范（字体 / 颜色 / 圆角 / 虚线 / 动画）新组件必须遵守
- [ ] B 端后台破例桌面布局，但色板字体沿用治愈系 OK
- [ ] 菜单下发走 Nacos 配置中心，C 端实时拉取 OK
- [ ] 性能：识菜图片必须前端压缩，AI 文本必须 debounce，AI 调用并发不串行 OK
- [ ] 文件拆分：`constants / utils / store / api / components/* / admin/*` 顺序加载 OK
- [ ] 联调：CORS / SSE 不缓冲 + 心跳 / multipart 限制 / 异步轮询 / 错误返回 JSON OK

---

文档结束。如对决策有异议，请在评审会议上标记，本文档将随实施迭代更新版本号。
