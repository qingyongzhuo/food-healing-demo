"""基础 Pydantic schemas。

统一响应格式 {code, message, data}。
错误码 5 段：1xxxx 业务 / 2xxxx AI / 3xxxx DB / 4xxxx 限流鉴权 / 5xxxx 系统。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """统一响应格式。"""

    code: int = Field(default=0, description="0 成功，非 0 见错误码表")
    message: str = Field(default="ok", description="面向用户可读的提示")
    data: Any | None = Field(default=None, description="业务字段，缺失返回 {} 不返回 null")


class ErrorResponse(BaseModel):
    """错误响应。"""

    code: int
    message: str
    detail: str | None = None


class HealthCheckResponse(BaseModel):
    """健康检查响应。"""

    status: str = Field(description="ok=全通 / degraded=部分不通 / down=整体不可用")
    version: str
    components: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="各组件连通性 {组件名: {status: ok|fail, latency_ms: '...'}}",
    )


# ===== 错误码常量（5 段）=====
# 1xxxx 业务
ERR_PARAM_MISSING = 10001
ERR_PARAM_FORMAT = 10002
ERR_NOT_FOUND = 10003
ERR_CONFLICT = 10004
ERR_BIZ_VALIDATE = 10005
ERR_ENUM_INVALID = 10006
ERR_USER_EXISTS = 10007
ERR_USER_NOT_FOUND = 10008
ERR_PASSWORD_WRONG = 10009

# 2xxxx AI
ERR_VL_CALL = 20001
ERR_VL_PARSE = 20002
ERR_BAILIAN_CHAT = 20003
ERR_BAILIAN_REPORT = 20004
ERR_BAILIAN_MOOD = 20005
ERR_BAILIAN_SUMMARY = 20006

# 3xxxx DB
ERR_MYSQL = 30001
ERR_PG = 30002
ERR_REDIS = 30003
ERR_DB_WRITE = 30004
ERR_DB_QUERY = 30005

# 4xxxx 限流鉴权
ERR_PARAM = 40001
ERR_UNAUTHORIZED = 40101
ERR_FORBIDDEN = 40301
ERR_NOT_FOUND_COMPAT = 40401
ERR_TASK_TIMEOUT = 40801
ERR_VALIDATE_COMPAT = 42201
ERR_RATE_LIMIT = 42901
ERR_AI_RATE_LIMIT = 42902
ERR_TOKEN_INVALID = 40102

# 5xxxx 系统
ERR_INTERNAL = 50000
ERR_VL_CALL_COMPAT = 50001
ERR_VL_PARSE_COMPAT = 50002
ERR_BAILIAN_CALL_COMPAT = 50003
ERR_GATEWAY_TIMEOUT = 50004
ERR_OSS_UPLOAD = 50005
ERR_MQ_DELIVER = 50006

# 占位接口统一错误码
ERR_NOT_IMPLEMENTED = 50100
"""Phase 0 占位接口错误码，Phase 1 实现后移除。"""
