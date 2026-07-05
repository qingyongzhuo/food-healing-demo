"""消息通知路由（Phase 5）。

全部接口走中间件鉴权，路由内通过 get_current_user_id(request) 取当前用户。

接口：
- GET    /message/list             分页获取消息（支持分类筛选 + 未读数）
- PUT    /message/{msg_id}/read    单条标记已读
- PUT    /message/read-all          全部消息标记已读
- DELETE /message/clear             清空当前用户全部消息
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.exceptions import success
from app.models.schemas import BaseResponse
from app.services import message_service
from app.utils.auth import get_current_user_id

router = APIRouter(prefix="/message", tags=["message"])


@router.get("/list", response_model=BaseResponse)
async def list_messages(
    request: Request,
    msg_type: str | None = Query(
        default=None, description="分类筛选：remind / ai / None(全部)"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BaseResponse:
    """分页获取消息列表。

    响应包含 unread_count（当前用户未读总数，不分类型），
    便于底部 Tab 红点渲染，避免前端再发一次请求。

    响应示例：
    {
      "items": [
        {"id": 1, "msg_type": "remind", "title": "午餐提醒",
         "content": "该吃午饭啦", "is_read": 0, "create_time": "2026-07-04T12:00:00"}
      ],
      "total": 15,
      "page": 1,
      "page_size": 20,
      "unread_count": 3
    }
    """
    user_id = get_current_user_id(request)
    data = await message_service.list_messages(
        user_id=user_id,
        msg_type=msg_type,
        page=page,
        page_size=page_size,
    )
    return success(data=data, message="ok")


@router.put("/{msg_id}/read", response_model=BaseResponse)
async def mark_message_read(
    msg_id: int,
    request: Request,
) -> BaseResponse:
    """单条消息标记已读。

    权限：仅 owner 可操作，找不到或无权访问均返回 404。
    幂等：已是已读态时直接返回成功。
    """
    user_id = get_current_user_id(request)
    data = await message_service.mark_message_read(
        user_id=user_id, msg_id=msg_id
    )
    return success(data=data, message="已标记为已读")


@router.put("/read-all", response_model=BaseResponse)
async def mark_all_read(request: Request) -> BaseResponse:
    """全部消息标记已读。

    仅更新未读的，避免全表锁。返回实际更新的条数。
    """
    user_id = get_current_user_id(request)
    data = await message_service.mark_all_read(user_id=user_id)
    return success(data=data, message="全部消息已标记为已读")


@router.delete("/clear", response_model=BaseResponse)
async def clear_messages(request: Request) -> BaseResponse:
    """清空当前用户全部消息（物理删除）。

    谨慎操作：删除后不可恢复。
    """
    user_id = get_current_user_id(request)
    data = await message_service.clear_all_messages(user_id=user_id)
    return success(data=data, message="消息已全部清空")
