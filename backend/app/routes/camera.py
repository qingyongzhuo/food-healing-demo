"""拍照识菜路由（阶段 6 新增）。

接口全部需鉴权（中间件已校验，路由内调 get_current_user_id 取 user_id）。

- POST /api/camera/upload   上传菜品图片，下发异步识别任务，返回任务标识
- GET  /api/camera/result   查询图片识别完成后的食材营养清单（?task_id=xxx）
- GET  /api/camera/logs     查询本人所有历史拍照识别记录
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, UploadFile, File

from app.exceptions import BizError, success
from app.models.schemas import BaseResponse, ERR_NOT_FOUND, ERR_PARAM_FORMAT
from app.services import camera_service
from app.utils.auth import get_current_user_id
from app.utils.logger import logger

router = APIRouter(prefix="/camera", tags=["camera"])


@router.post("/upload", response_model=BaseResponse)
async def upload_camera_image(
    request: Request,
    file: UploadFile = File(...),
) -> BaseResponse:
    """上传菜品图片，下发异步识别任务，返回任务标识。

    流程：
    1. 中间件已校验 Token（无 Token 返回 401）
    2. 调 camera_service.submit_camera_task 保存图片 + 发 MQ / fallback
    3. 立即返回 {task_id, image_url, status: "pending"}

    前端拿到 task_id 后轮询 GET /api/camera/result?task_id=xxx 获取结果。
    """
    user_id = get_current_user_id(request)

    if not file.filename:
        raise BizError(code=ERR_PARAM_FORMAT, message="请上传图片文件")

    data = await camera_service.submit_camera_task(file=file, user_id=user_id)
    logger.info(
        "camera_upload_submitted",
        task_id=data["task_id"],
        user_id=user_id,
    )
    return success(data=data, message="识菜任务已提交")


@router.get("/result", response_model=BaseResponse)
async def get_camera_result(
    request: Request,
    task_id: str = Query(..., description="任务标识（POST /camera/upload 返回）"),
) -> BaseResponse:
    """查询图片识别完成后的食材营养清单。

    status: pending / processing / done / failed
    dishes: 识别到的菜品列表（status=done 时有值，含分类标签色 category_color）
    """
    get_current_user_id(request)  # 仅鉴权，不限制跨用户查询（任务 ID 已是 UUID 难猜测）

    if not task_id:
        raise BizError(code=ERR_PARAM_FORMAT, message="task_id 不能为空")

    result = await camera_service.get_task_result(task_id)
    if result is None:
        raise BizError(
            code=ERR_NOT_FOUND,
            message="任务不存在或已过期（10 分钟内有效）",
        )
    return success(data=result)


@router.get("/logs", response_model=BaseResponse)
async def list_camera_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="每页数量"),
    skip: int = Query(default=0, ge=0, description="跳过条数（分页）"),
) -> BaseResponse:
    """查询本人所有历史拍照识别记录（Mongo，按时间倒序）。"""
    user_id = get_current_user_id(request)

    logs = await camera_service.list_user_logs(user_id, limit=limit, skip=skip)
    return success(data={"list": logs, "total": len(logs)})
