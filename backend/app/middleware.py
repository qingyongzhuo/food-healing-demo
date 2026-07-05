"""中间件。

按规范 §5.3 顺序挂载：
1. request_id 注入（最先，后续日志可用）
2. 鉴权（JWT 校验，注入 request.state.user_id）
3. CORS
4. 请求日志（记录入参、耗时）
5. 限流（slowapi）
6. 全局异常处理（在 exceptions.register_exception_handlers 中注册）
"""

from __future__ import annotations

import re
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.models.schemas import BaseResponse, ERR_TOKEN_INVALID, ERR_UNAUTHORIZED
from app.utils.auth import _extract_bearer_token, decode_token, validate_session
from app.utils.logger import logger


class RequestIdMiddleware(BaseHTTPMiddleware):
    """注入 request_id 到 request.state 与响应头。"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


class RequestLogMiddleware(BaseHTTPMiddleware):
    """记录请求日志（含 request_id/user_id/latency_ms/status）。"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", "-")
        user_id = getattr(request.state, "user_id", "-")
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request",
                request_id=request_id,
                user_id=user_id,
                method=method,
                path=path,
                status=response.status_code,
                latency_ms=latency_ms,
            )
            return response
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request_error",
                request_id=request_id,
                method=method,
                path=path,
                latency_ms=latency_ms,
                error=str(exc),
            )
            raise


# 鉴权白名单：这些路径不校验 token
# - /api/auth/register|login：注册登录本身
# - /api/health：健康检查
# - /api/admin/*：admin 独立体系，保持现状（占位接口）
# - /docs /openapi.json /redoc /：Swagger 文档与根路径
# - /static/*：头像等静态资源
AUTH_WHITELIST = [
    re.compile(r"^/api/auth/(register|login)$"),
    re.compile(r"^/api/health$"),
    re.compile(r"^/api/recognize-dish$"),
    re.compile(r"^/api/recognize/result/"),
    re.compile(r"^/api/admin/"),
    re.compile(r"^/docs$"),
    re.compile(r"^/redoc$"),
    re.compile(r"^/openapi\.json$"),
    re.compile(r"^/static/"),
    re.compile(r"^/$"),
]


def _is_whitelisted(path: str) -> bool:
    return any(p.match(path) for p in AUTH_WHITELIST)


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 鉴权中间件。

    白名单路径直接放行；其余 /api/* 请求校验 Authorization: Bearer token，
    成功注入 request.state.user_id，失败返回 401。
    OPTIONS 预检请求一律放行（CORS 需要）。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        # OPTIONS 预检 / 白名单 / 非 /api 路径直接放行
        if request.method == "OPTIONS" or _is_whitelisted(path) or not path.startswith("/api"):
            return await call_next(request)

        token = _extract_bearer_token(request)
        if not token:
            return JSONResponse(
                status_code=401,
                content=BaseResponse(
                    code=ERR_UNAUTHORIZED, message="未登录", data=None
                ).model_dump(),
            )
        user_id = decode_token(token)
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content=BaseResponse(
                    code=ERR_TOKEN_INVALID,
                    message="登录已过期，请重新登录",
                    data=None,
                ).model_dump(),
            )
        if not await validate_session(user_id, token):
            return JSONResponse(
                status_code=401,
                content=BaseResponse(
                    code=ERR_TOKEN_INVALID,
                    message="登录已过期，请重新登录",
                    data=None,
                ).model_dump(),
            )
        request.state.user_id = user_id
        return await call_next(request)


def setup_middlewares(app) -> None:  # type: ignore[no-untyped-def]
    """统一挂载所有中间件（顺序重要）。

    Starlette 的 add_middleware 是 LIFO：后挂载的是最外层，最先执行。
    期望执行顺序（外→内）：RequestId → Auth → CORS → RequestLog → 路由
    因此 add 顺序（先 add 变内层）：
      1. RequestLog（最先 add，最里层，最后执行，能读 request_id/user_id）
      2. CORS（中间层）
      3. Auth（中间层，校验 token 注入 user_id）
      4. RequestId（最后 add，最外层，最先执行，注入 request_id）
    """
    # 1. 请求日志（先 add → 变最里层，最后执行）
    app.add_middleware(RequestLogMiddleware)
    # 2. CORS（中间层）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    # 3. 鉴权（中间层，需要 request_id 已注入，所以比 RequestId 更内层）
    app.add_middleware(AuthMiddleware)
    # 4. request_id 注入（最后 add → 变最外层，最先执行）
    app.add_middleware(RequestIdMiddleware)
