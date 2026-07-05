"""应用常量。

集中管理 AI prompt 模板、队列名、路由键等常量。
阶段 6 新增：识菜相关 prompt + MQ 队列/路由键。
阶段 5 新增：消息通知类型与已读状态、消息推送路由键。
"""

from __future__ import annotations


# ===== 消息通知（Phase 5）=====
MSG_TYPE_REMIND = "remind"
"""饮食提醒：定时推送（如该吃饭了、喝水提醒）。"""

MSG_TYPE_AI = "ai"
"""AI 推送：营养师助手主动建议（如今天碳水偏高）。"""

MSG_TYPES = (MSG_TYPE_REMIND, MSG_TYPE_AI)
"""消息类型枚举元组，校验时用 `in` 判断。"""

MSG_READ_UNREAD = 0
"""未读。"""

MSG_READ_READ = 1
"""已读。"""

# RabbitMQ 消息推送路由键（Phase 5）
ROUTING_KEY_PUSH_MSG = "task.push.msg"
"""消息推送任务路由键。生产者发到此 key，消费者监听写入 system_message 表。"""

QUEUE_NAME_PUSH_MSG = "task.push.msg.queue"
"""消息推送消费者队列名。与路由键同名便于排查。"""

# 死信交换机与队列（Phase 8 容错增强）
DLX_EXCHANGE = "food_healing_dlx"
"""死信交换机名。主队列消息 nack 且 requeue=False 时进入此交换机。"""

DLX_QUEUE_PUSH_MSG = "task.push.msg.dlq"
"""消息推送死信队列名。存放消费失败的消息，便于人工排查或重投。"""

# 消息重试参数（Phase 8）
MQ_MAX_RETRIES = 3
"""单条消息最大重试次数（写入 header x-retry 跟踪）。"""
MQ_RETRY_BASE_DELAY = 5
"""重试基础延迟（秒），实际延迟 = base * 2^retry_count。"""


# ===== AI Prompt 模板 =====

# 菜品识别系统 prompt（Qwen-VL）
# 输出 JSON 格式：dishes 数组，每项含 name/category/unit/kcal/protein/carb/fat/confidence
RECOGNIZE_DISH_SYSTEM_PROMPT = """你是一个食堂菜品识别助手。根据用户上传的图片识别菜品，返回 JSON。

要求：
1. 识别图片中的菜品名称（中文）
2. 估算每份的营养成分（kcal、蛋白质g、碳水g、脂肪g）
3. 估算分量（克）
4. 给出置信度 0-1
5. 分类必须从以下枚举中选择：主食 / 肉类 / 蔬菜 / 蛋奶 / 汤品 / 水果 / 其他

严格按以下 JSON 格式返回，不要包含其他文字、不要包裹 markdown 代码块：
{
  "dishes": [
    {
      "name": "菜品名",
      "category": "主食|肉类|蔬菜|蛋奶|汤品|水果|其他",
      "unit": "份(克数g)",
      "kcal": 数字,
      "protein": 数字,
      "carb": 数字,
      "fat": 数字,
      "confidence": 0.0-1.0
    }
  ]
}"""

# 菜品识别用户 prompt
RECOGNIZE_DISH_USER_PROMPT = "请识别这张图片中的菜品，返回 JSON。"


# ===== RabbitMQ 队列与路由键（阶段 6 新增）=====

# 识菜任务队列名
AI_RECOGNIZE_QUEUE = "ai_recognize_queue"
# 识菜任务路由键
AI_RECOGNIZE_ROUTING_KEY = "task.ai.recognize"


# ===== Redis Key 前缀（阶段 6 camera 任务状态）=====
# 完整 key: food_healing:camera_task:{task_id}
CAMERA_TASK_KEY_PREFIX = "food_healing:camera_task:"
# 任务状态保留时间（10 分钟，与 recognize 一致）
CAMERA_TASK_TTL = 600


# ===== MongoDB 集合名（阶段 6 新增）=====
CAMERA_RECOGNIZE_LOG_COLLECTION = "camera_recognize_log"

# AI 对话历史集合（每日一文档，chat_list 累加）
AI_CHAT_HISTORY_COLLECTION = "ai_chat_history"
# AI 每日营养简报集合（每日一文档，存完整长报告）
AI_DAILY_REPORT_COLLECTION = "ai_daily_report"


# ===== AI 营养师 prompt 模板（Phase 3 新增）=====

# 营养师系统提示词：定义 AI 角色与回答风格
NUTRITIONIST_SYSTEM_PROMPT = """你是「食愈」App 的专属营养师助手，温柔专业、贴近校园生活。

你的职责：
1. 根据用户当日的三餐 + 零食记录，给出贴合实际的营养建议
2. 指出当日热量、蛋白、碳水、脂肪的摄入偏差（偏高/偏低/合理）
3. 推荐适合校园食堂场景的改善方案，避免空泛理论
4. 语气亲切简短，每次回答控制在 200 字以内，可用少量 emoji

约束：
- 不要编造用户未记录的食物
- 不要推荐昂贵或难以购买的食材
- 不要重复用户已经说过的内容
- 如用户当日无饮食记录，引导用户先记录再咨询"""


# 每日 AI 总结模板：用于生成当日营养简报
AI_DAILY_SUMMARY_PROMPT = """请基于以下用户当日饮食数据，生成一份完整的「每日营养简报」。

【用户信息】
- 用户 ID：{user_id}
- 报告日期：{report_date}
- 营养目标：热量 {target_calorie} kcal / 蛋白 {target_protein}g / 碳水 {target_carb}g / 脂肪 {target_fat}g

【当日实际摄入】
- 总热量：{total_calorie} kcal
- 蛋白质：{total_protein}g
- 碳水化合物：{total_carb}g
- 脂肪：{total_fat}g

【当日餐次明细】
{meal_details}

请按以下结构返回 Markdown 文本（不要包裹代码块）：

## 今日营养总览
（一句话点评当日整体饮食）

## 营养偏差分析
- 热量：对比目标，给出偏差百分比与影响
- 蛋白 / 碳水 / 脂肪：分别点评

## 改善建议
（3 条可执行的明日改善建议，结合校园食堂场景）

## 推荐食谱
（基于今日不足推荐 1-2 个明日的具体菜品搭配）"""


# ===== RabbitMQ 每日 AI 简报队列（Phase 3 新增）=====

# 每日 AI 简报任务队列名
AI_DAILY_SUMMARY_QUEUE = "ai_daily_summary_queue"
# 每日 AI 简报任务路由键
AI_DAILY_SUMMARY_ROUTING_KEY = "task.ai.daily"

