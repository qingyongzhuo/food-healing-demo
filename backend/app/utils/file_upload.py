"""图片上传压缩工具。

阶段 6 新增：camera 模块的图片存储。
- Pillow 压缩到最大边 1024px（保留细节，控制文件大小）
- 保存到本地 uploads/camera/ 目录
- 返回可访问的相对 URL（前端通过 /static/ 拼接）

设计原则：
1. 复用现有 auth_service.upload_avatar 的压缩模式
2. 同步 IO（文件小，事件循环内可接受）
3. 失败抛 BizError，由调用方决定降级
"""

from __future__ import annotations

import io
import os
import time
import uuid

from fastapi import UploadFile

from app.config import settings
from app.exceptions import BizError
from app.models.schemas import ERR_PARAM_FORMAT
from app.utils.logger import logger

# 图片上限 5MB（与 recognize 一致）
MAX_IMAGE_SIZE = 5 * 1024 * 1024
# 允许的图片 MIME 类型
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
# 压缩目标最大边长（px）
TARGET_MAX_SIDE = 1024
# JPEG 压缩质量
JPEG_QUALITY = 85
# 本地存储子目录（相对 uploads/）
CAMERA_UPLOAD_SUBDIR = "camera"


async def save_camera_image(file: UploadFile, user_id: int | str | None) -> dict:
    """保存菜品图片：校验 → Pillow 压缩 → 本地存储 → 返回访问 URL。

    Args:
        file: FastAPI UploadFile 对象。
        user_id: 用户 ID（用于文件名前缀，便于排查）。

    Returns:
        {
            "url": "/static/camera/{filename}",  # 相对路径，前端拼接域名
            "filename": "u1_1234567890_abc123.jpg",
            "size": 12345,  # 压缩后字节数
            "content_type": "image/jpeg",
        }

    Raises:
        BizError: 文件格式/大小/内容不合法。
    """
    if not file.filename:
        raise BizError(code=ERR_PARAM_FORMAT, message="请上传图片文件")
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise BizError(code=ERR_PARAM_FORMAT, message="仅支持 jpg/png/webp 格式")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise BizError(
            code=ERR_PARAM_FORMAT,
            message=f"图片不能超过 {MAX_IMAGE_SIZE // (1024 * 1024)}MB",
        )
    if not image_bytes:
        raise BizError(code=ERR_PARAM_FORMAT, message="图片内容为空")

    # Pillow 压缩
    try:
        from PIL import Image
    except ImportError as exc:
        raise BizError(code=ERR_PARAM_FORMAT, message="图片处理库未安装") from exc

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        # 等比缩放到最大边 1024px（thumbnail 是 in-place 操作）
        img.thumbnail((TARGET_MAX_SIDE, TARGET_MAX_SIDE))
    except Exception as exc:
        logger.warning("camera_image_decode_failed", error=str(exc))
        raise BizError(code=ERR_PARAM_FORMAT, message="图片解析失败") from exc

    # 生成文件名：{user_id}_{ts}_{uuid6}.jpg
    user_prefix = str(user_id) if user_id is not None else "anon"
    filename = f"{user_prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"

    # 存储目录：uploads/camera/
    upload_dir = os.path.join("uploads", CAMERA_UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    # 压缩后写入磁盘
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=JPEG_QUALITY)
    compressed_bytes = buffer.getvalue()
    with open(filepath, "wb") as f:
        f.write(compressed_bytes)

    # 相对 URL（前端通过 /static/camera/xxx.jpg 访问）
    url = f"/static/{CAMERA_UPLOAD_SUBDIR}/{filename}"

    logger.info(
        "camera_image_saved",
        filename=filename,
        original_size=len(image_bytes),
        compressed_size=len(compressed_bytes),
    )

    return {
        "url": url,
        "filename": filename,
        "size": len(compressed_bytes),
        "content_type": "image/jpeg",
    }


async def fetch_image_bytes(url: str) -> bytes:
    """根据相对 URL 读取本地图片字节（供 MQ 消费者调 VL 用）。

    Args:
        url: 相对路径，如 /static/camera/xxx.jpg。

    Returns:
        图片字节。

    Raises:
        FileNotFoundError: 文件不存在。
    """
    # 去掉前导 / 转为相对路径
    relative_path = url.lstrip("/")
    with open(relative_path, "rb") as f:
        return f.read()
