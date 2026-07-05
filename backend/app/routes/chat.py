"""AI 对话（SSE 流式）。

- POST /api/chat：SSE 流式对话（默认）
- POST /api/chat?stream=false：一次性返回（降级，SSE 不通时用）

请求体（与 frontend/js/api.js chatStream 对齐）：
  {
    "persona": "canteen_aunt",
    "messages": [{"role": "user", "content": "今天吃啥"}],
    "context": {"user_id": "u123", "mode": "daily"}
  }

SSE 事件协议（与 api.js parseSseChunk 对齐）：
  event: delta
  data: {"delta":"今","done":false}

  event: memory_hint
  data: {"hint":"你上周说胃不舒服"}

  event: done
  data: {"delta":"","done":true}
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.exceptions import BizError, success
from app.models.schemas import ERR_PARAM_MISSING
from app.services.chat_service import chat_non_stream, chat_stream_generator
from app.utils.logger import logger

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(description="user / assistant")
    content: str


class ChatRequest(BaseModel):
    persona: str = Field(default="canteen_aunt", description="人格：canteen_aunt / nutritionist / fitness_coach")
    messages: list[ChatMessage]
    context: dict | None = Field(default=None, description="附加上下文，如 {user_id, mode}")

    def get_user_id(self) -> str:
        if self.context and isinstance(self.context.get("user_id"), str):
            return self.context["user_id"]
        return "anonymous"


@router.post("/chat")
async def chat(
    request: Request,
    req: ChatRequest,
    stream: bool = Query(default=True, description="true=SSE 流式 / false=一次性返回"),
):
    """AI 对话。

    - stream=true（默认）：返回 text/event-stream，逐字推送 delta 事件
    - stream=false：返回统一 {code, message, data}，data={reply, memoryHint}

    user_id 优先取 token（中间件注入 request.state.user_id），缺失则用 context.user_id。
    """
    if not req.messages:
        raise BizError(code=ERR_PARAM_MISSING, message="消息不能为空")

    # 优先用 token 中的 user_id（强制登录后中间件已注入），fallback 到请求体 context
    user_id = getattr(request.state, "user_id", None) or req.get_user_id()
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if stream:
        logger.info("chat_stream_start", user_id=user_id, persona=req.persona)
        return StreamingResponse(
            chat_stream_generator(user_id, req.persona, messages, req.context),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲，确保实时推送
            },
        )

    # 降级：一次性返回（统一响应格式）
    data = await chat_non_stream(user_id, req.persona, messages, req.context)
    return success(data=data, message="ok")
