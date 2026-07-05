"""AI 对话与每日简报 Pydantic 校验模型。

Phase 3 新增，对应 4 类业务场景：
1. 对话发送请求模型：提问内容 + 查询日期
2. 对话返回模型：AI 回答文本
3. 单条聊天记录结构（Mongo ai_chat_history.chat_list 元素）
4. 每日 AI 简报结构（Mongo ai_daily_report 文档）
5. 历史对话分页查询入参

字段命名与前端 frontend-v2/src/lib/api.js 对齐（snake_case）。
Mongo 集合结构见项目根目录数据库设计文档。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ===== 1. 对话发送请求模型 =====
class AiChatRequest(BaseModel):
    """AI 对话发送请求。

    用户在 AI 营养师聊天页发送一条咨询，后端会：
    1. 拉取 query_date 当日饮食数据作为上下文
    2. 拉取当日已有聊天记录作为历史
    3. 调百炼 chat_with_diet_context 生成回答
    4. 将 user + assistant 两条消息 append 到 Mongo ai_chat_history
    """

    content: str = Field(
        min_length=1,
        max_length=500,
        description="用户提问内容（≤500 字符）",
    )
    query_date: str | None = Field(
        default=None,
        description="查询日期 YYYY-MM-DD，默认当天。用于拉取当日饮食上下文 + 历史对话",
    )


# ===== 2. 对话返回模型 =====
class AiChatReply(BaseModel):
    """AI 对话返回模型。"""

    reply: str = Field(description="AI 回答文本")
    query_date: str = Field(description="本次对话关联的日期 YYYY-MM-DD")
    saved: bool = Field(
        default=True,
        description="对话是否已写入 Mongo ai_chat_history（False 表示 Mongo 未启用）",
    )


# ===== 3. 单条聊天记录结构 =====
class ChatRecordItem(BaseModel):
    """单条聊天记录（Mongo ai_chat_history.chat_list 数组元素）。"""

    role: Literal["user", "assistant"] = Field(
        description="消息角色：user 用户提问 / assistant AI 回答"
    )
    content: str = Field(description="消息内容")
    created_at: str | None = Field(
        default=None,
        description="消息时间 ISO 字符串（用于排序与展示）",
    )


# ===== 4. 当日对话列表返回 =====
class ChatHistoryResponse(BaseModel):
    """单日对话列表返回。"""

    user_id: int
    record_date: str = Field(description="日期 YYYY-MM-DD")
    chat_list: list[ChatRecordItem] = Field(default_factory=list)
    daily_summary: str | None = Field(
        default=None,
        description="当日 AI 自动简报摘要（来自 ai_chat_history.daily_summary）",
    )


# ===== 5. 历史对话分页查询入参 =====
class ChatHistoryQuery(BaseModel):
    """历史对话分页查询入参。"""

    page: int = Field(default=1, ge=1, description="页码，从 1 起")
    page_size: int = Field(
        default=20, ge=1, le=100, description="每页条数 [1, 100]"
    )


# ===== 6. 历史对话分页返回 =====
class ChatHistoryItem(BaseModel):
    """历史对话分页单项（一日一条文档）。"""

    record_date: str = Field(description="日期 YYYY-MM-DD")
    message_count: int = Field(default=0, description="当日消息条数")
    daily_summary: str | None = Field(
        default=None, description="当日简报摘要（无则空）"
    )
    last_content: str | None = Field(
        default=None,
        description="当日最后一条消息内容（预览用，截断 100 字）",
    )


class ChatHistoryListResponse(BaseModel):
    """历史对话分页列表返回。"""

    items: list[ChatHistoryItem] = Field(default_factory=list)
    total: int = Field(default=0, description="总日数（用于分页）")
    page: int = 1
    page_size: int = 20


# ===== 7. 每日 AI 简报结构 =====
class DailySummaryResponse(BaseModel):
    """单日 AI 营养简报返回。

    对应 Mongo ai_daily_report 集合的一个文档。
    如当日尚未生成简报，返回 found=False + content=None。
    """

    found: bool = Field(
        default=False,
        description="当日简报是否已生成。False 表示尚未生成，前端可触发 generate",
    )
    user_id: int
    report_date: str = Field(description="报告日期 YYYY-MM-DD")
    full_content: str | None = Field(
        default=None,
        description="完整 Markdown 简报内容（found=True 时返回）",
    )
    create_at: str | None = Field(
        default=None,
        description="简报生成时间 ISO 字符串",
    )


# ===== 8. 历史 AI 报告分页返回 =====
class DailyReportItem(BaseModel):
    """历史 AI 报告分页单项。"""

    report_date: str = Field(description="报告日期 YYYY-MM-DD")
    full_content: str = Field(description="完整 Markdown 简报内容")
    create_at: str | None = Field(default=None, description="生成时间 ISO 字符串")


class DailyReportHistoryResponse(BaseModel):
    """历史 AI 报告分页列表返回。"""

    items: list[DailyReportItem] = Field(default_factory=list)
    total: int = Field(default=0, description="总条数")
    page: int = 1
    page_size: int = 20
