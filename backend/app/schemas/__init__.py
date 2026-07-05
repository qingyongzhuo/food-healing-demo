"""schemas 包：Pydantic 校验模型分层目录。

- user.py：用户中心模块校验模型（Phase 3 新增）
- 后续可按模块拆分：chat.py / recognize.py 等

历史模型仍在 app.models.schemas（错误码常量 + BaseResponse），
新增业务模型优先放本目录。
"""
