"""AI 对话与每日简报路由（Phase 3）。

全部接口走中间件鉴权，路由内通过 get_current_user_id(request) 取当前用户。

接口：
- POST /ai/chat            发送咨询问题，携带当日饮食上下文调用百炼
- GET  /ai/chat/list       分页查询指定日期聊天历史
- GET  /ai/daily-summary   获取当天（或指定日期）的 AI 营养简报
- GET  /ai/report/history  查看过往每日完整 AI 饮食报告
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.exceptions import success
from app.models.schemas import BaseResponse
from app.schemas.ai_chat import AiChatRequest
from app.services import ai_service
from app.utils.auth import get_current_user_id

router = APIRouter(prefix="/ai", tags=["ai_chat"])


@router.post("/chat", response_model=BaseResponse)
async def chat_with_assistant(
    request: Request,
    req: AiChatRequest,
) -> BaseResponse:
    """发送咨询问题。

    后端自动：
    1. 拉取 query_date（默认当天）当日饮食数据作为上下文
    2. 拉取当日已有聊天记录作为历史
    3. 调百炼 chat_with_diet_context 生成回答
    4. 将 user + assistant 两条消息写入 Mongo ai_chat_history

    请求体：
        {"content": "我今天蛋白吃少了怎么办", "query_date": "2026-07-04"}

    响应：
        {"reply": "建议晚餐增加鸡胸肉...", "query_date": "2026-07-04", "saved": true}
    """
    user_id = get_current_user_id(request)
    data = await ai_service.chat_with_assistant(
        user_id=user_id,
        content=req.content,
        query_date=req.query_date,
    )
    return success(data=data, message="ok")


@router.get("/chat/list", response_model=BaseResponse)
async def list_chat_history(
    request: Request,
    record_date: str | None = Query(
        default=None,
        description="查询日期 YYYY-MM-DD，默认当天",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BaseResponse:
    """查询聊天历史。

    两种用法：
    1. 传 record_date：返回该日完整 chat_list
    2. 不传 record_date：分页返回历史每日对话摘要（一日一条）

    响应（传 record_date）：
        {
          "user_id": 1, "record_date": "2026-07-04",
          "chat_list": [{"role": "user", "content": "...", "created_at": "..."}],
          "daily_summary": "今日碳水略超标..."
        }

    响应（不传 record_date）：
        {
          "items": [{"record_date": "...", "message_count": 4, "last_content": "..."}],
          "total": 5, "page": 1, "page_size": 20
        }
    """
    user_id = get_current_user_id(request)

    if record_date:
        data = await ai_service.get_chat_history_by_date(
            user_id=user_id,
            record_date=record_date,
        )
    else:
        data = await ai_service.list_chat_history(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

    return success(data=data, message="ok")


@router.get("/daily-summary", response_model=BaseResponse)
async def get_daily_summary(
    request: Request,
    report_date: str | None = Query(
        default=None,
        description="报告日期 YYYY-MM-DD，默认当天",
    ),
) -> BaseResponse:
    """获取当日 AI 营养简报。

    如当日尚未生成简报，返回 found=False + full_content=None。
    前端可在 found=False 时调 POST /ai/trigger 主动触发（如需要）。

    响应：
        {
          "found": true,
          "user_id": 1,
          "report_date": "2026-07-04",
          "full_content": "## 今日营养总览\\n...",
          "create_at": "2026-07-04T12:00:00"
        }
    """
    user_id = get_current_user_id(request)
    data = await ai_service.get_daily_summary(
        user_id=user_id,
        report_date=report_date,
    )
    return success(data=data, message="ok")


@router.get("/report/history", response_model=BaseResponse)
async def list_daily_reports(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BaseResponse:
    """查看过往每日完整 AI 饮食报告（按日期倒序）。

    响应：
        {
          "items": [
            {"report_date": "2026-07-04", "full_content": "...", "create_at": "..."}
          ],
          "total": 5, "page": 1, "page_size": 20
        }
    """
    user_id = get_current_user_id(request)
    data = await ai_service.list_daily_reports(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return success(data=data, message="ok")
