"""识图异步链路。

- POST /api/recognize-dish：提交识菜任务
- GET /api/recognize/result/{task_id}：轮询识图结果
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.exceptions import BizError, success
from app.models.schemas import BaseResponse, ERR_PARAM_FORMAT, ERR_NOT_FOUND
from app.services.recognize_service import get_task_result, submit_recognize_task
from app.utils.logger import logger

router = APIRouter(tags=["recognize"])

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/recognize-dish", response_model=BaseResponse)
async def recognize_dish(
    request: Request,
    file: UploadFile = File(...),
    user_id: int | None = Form(default=None),
    meal_hint: str = Form(default=""),
) -> BaseResponse:
    """提交识菜任务。

    接收图片，返回 task_id。前端轮询 GET /api/recognize/result/{task_id} 获取结果。
    user_id 优先取 token（中间件注入），fallback 到 FormData。
    """
    # 校验文件类型
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise BizError(
            code=ERR_PARAM_FORMAT,
            message="仅支持 jpg/png/webp 格式",
        )
    if not file.filename:
        raise BizError(
            code=ERR_PARAM_FORMAT,
            message="请上传图片文件",
        )

    # 读取图片内容
    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise BizError(
            code=ERR_PARAM_FORMAT,
            message=f"图片不能超过 {MAX_IMAGE_SIZE // (1024*1024)}MB",
        )

    content_type = file.content_type or "image/jpeg"

    # 优先用 token 中的 user_id（强制登录后中间件已注入）
    effective_user_id = getattr(request.state, "user_id", None) or user_id

    task_id = await submit_recognize_task(
        image_bytes=image_bytes,
        content_type=content_type,
        user_id=effective_user_id or None,
        meal_hint=meal_hint or None,
    )
    logger.info("recognize_dish_submitted", task_id=task_id, user_id=effective_user_id)

    return success(
        data={"task_id": task_id, "status": "pending"},
        message="识菜任务已提交",
    )


@router.get("/recognize/result/{task_id}", response_model=BaseResponse)
async def get_recognize_result(task_id: str) -> BaseResponse:
    """轮询识图结果。

    status: pending|processing|done|failed
    """
    result = await get_task_result(task_id)
    if result is None:
        raise BizError(
            code=ERR_NOT_FOUND,
            message="任务不存在或已过期",
        )

    return success(data=result)
