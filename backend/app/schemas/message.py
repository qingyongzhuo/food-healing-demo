"""消息通知模块 Pydantic 校验模型。

Phase 5 新增，对应 3 类业务场景：
1. 消息返回模型（与 system_message 表字段对齐）
2. 分页查询入参（页码 + 分类筛选）
3. 一键清空请求模型（无 body，保留空模型便于后续扩展）

字段命名与前端 frontend-v2/src/lib/api.js 对齐（snake_case）。
消息类型枚举见 app.constants.MSG_TYPES。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ===== 1. 消息返回模型 =====
class MessageItem(BaseModel):
    """单条消息返回。

    create_time 序列化为 ISO 字符串（service 层转 str），
    is_read 为 0/1（与 system_message 表 SmallInteger 对齐）。
    """

    id: int
    msg_type: str = Field(description="消息类型：remind 饮食提醒 / ai AI 推送")
    title: str
    content: str
    is_read: int = Field(default=0, description="0 未读 / 1 已读")
    create_time: str = Field(description="创建时间，ISO 字符串")


class MessageListResponse(BaseModel):
    """消息分页列表返回。

    包含未读数便于底部 Tab 红点渲染，避免前端再发一次请求。
    """

    items: list[MessageItem] = Field(default_factory=list)
    total: int = Field(default=0, description="符合条件的总条数（用于分页）")
    page: int = 1
    page_size: int = 20
    unread_count: int = Field(
        default=0, description="当前用户未读消息总数（不分类型）"
    )


# ===== 2. 分页查询入参 =====
class MessageListQuery(BaseModel):
    """消息分页查询入参。

    msg_type 为空表示查全部；remind / ai 表示按类型筛选。
    """

    msg_type: Literal["remind", "ai"] | None = Field(
        default=None, description="分类筛选：remind / ai / None(全部)"
    )
    page: int = Field(default=1, ge=1, description="页码，从 1 起")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数 [1, 100]")


# ===== 3. 一键清空请求模型 =====
class MessageClearRequest(BaseModel):
    """一键清空消息请求。

    当前无字段（清空当前用户全部消息），保留空模型便于后续扩展
    （如增加 only_read 只清已读、before_date 按日期清理等）。
    """

    pass


# ===== 4. MQ 推送消息体（生产者 → 消费者内部契约，不暴露给前端）=====
class PushMessagePayload(BaseModel):
    """MQ 推送消息体。

    由生产者（定时任务 / AI 主动推送）构造，发到 task.push.msg 路由键，
    消费者收到后调用 message_service.create_message 写入 system_message 表。
    """

    user_id: int = Field(description="目标用户 ID")
    msg_type: Literal["remind", "ai"] = Field(description="消息类型")
    title: str = Field(min_length=1, max_length=100, description="标题")
    content: str = Field(min_length=1, max_length=2000, description="正文")
