"""统一响应 + 异常处理。

- BizError：业务异常，service 层抛出，路由层不处理
- register_exception_handlers：注册全局异常处理器
- success / not_implemented：便捷响应构造
"""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from structlog import get_logger

from app.models.schemas import (
    ERR_INTERNAL,
    ERR_NOT_IMPLEMENTED,
    BaseResponse,
)
from app.utils.logger import logger


class BizError(Exception):
    """业务异常，service 层抛出明确错误码与消息。"""

    def __init__(
        self,
        code: int,
        message: str,
        http_status: int = 400,
        data: Any | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data
        super().__init__(message)


def success(data: Any = None, message: str = "ok") -> BaseResponse:
    """构造成功响应。"""
    return BaseResponse(code=0, message=message, data=data)


def not_implemented() -> NoReturn:
    """占位接口统一响应。

    抛 BizError(HTTP 501, code=ERR_NOT_IMPLEMENTED)，
    由全局 BizError handler 统一序列化为 {code, message, data}。
    HTTP 状态码用 501 Not Implemented，语义比 200 更准确。
    路由调用方仍可写 `return not_implemented()`，因为 raise 会中断 return。
    """
    raise BizError(
        code=ERR_NOT_IMPLEMENTED,
        message="Not Implemented, Phase 1 实现",
        http_status=501,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(BizError)
    async def biz_handler(request: Request, exc: BizError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=BaseResponse(
                code=exc.code, message=exc.message, data=exc.data
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def global_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        logger.exception(
            "Unhandled error",
            request_id=request_id,
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content=BaseResponse(
                code=ERR_INTERNAL, message="internal error", data=None
            ).model_dump(),
        )
