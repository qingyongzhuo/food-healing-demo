"""拍照识菜模块 Pydantic 校验模型（阶段 6 新增）。

2 类核心模型：
- CameraUploadResponse：图片上传响应（任务标识 + 图片 URL）
- RecognizedDish：AI 识别结果单项（食材名/分类/热量/营养/分类标签色）

辅助模型：
- CameraTaskResult：任务结果查询响应
- CameraLogItem：历史识别记录单项
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ===== 分类标签色映射（与前端 FoodTag 配色一致）=====
# key 为菜品分类，value 为 [bg_color, text_color]（仅文档说明用，实际配色前端处理）
CATEGORY_COLOR_MAP = {
    "主食": "#E8D9C6",
    "肉类": "#F7C9C9",
    "蔬菜": "#B7E4C7",
    "蛋奶": "#FFE8D6",
    "汤品": "#D6E4FF",
    "水果": "#FFE8D6",
    "其他": "#E2E2E8",
}


class RecognizedDish(BaseModel):
    """AI 识别结果单项（食材名/分类/热量/营养/分类标签色）。

    字段对齐前端 PhotoRecognition 组件渲染所需数据。
    """

    name: str = Field(description="菜品名称（中文）")
    category: str = Field(default="其他", description="分类：主食/肉类/蔬菜/蛋奶/汤品/水果/其他")
    unit: str = Field(default="份", description="分量描述，如 '份(150g)'")
    kcal: int = Field(default=0, ge=0, description="每份热量(kcal)")
    protein: float = Field(default=0, ge=0, description="蛋白质(g)")
    carb: float = Field(default=0, ge=0, description="碳水(g)")
    fat: float = Field(default=0, ge=0, description="脂肪(g)")
    confidence: float = Field(
        default=0.5, ge=0, le=1, description="AI 置信度 0-1"
    )
    category_color: str | None = Field(
        default=None, description="分类标签色（HEX），由后端按 CATEGORY_COLOR_MAP 填充"
    )


class CameraUploadResponse(BaseModel):
    """图片上传响应模型。"""

    task_id: str = Field(description="异步识别任务标识，用于轮询结果")
    image_url: str = Field(description="图片访问 URL（相对路径，如 /static/camera/xxx.jpg）")
    status: str = Field(default="pending", description="初始任务状态：pending/processing/done/failed")


class CameraTaskResult(BaseModel):
    """任务结果查询响应。"""

    task_id: str
    status: str = Field(description="pending / processing / done / failed")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    dishes: list[RecognizedDish] = Field(
        default_factory=list, description="识别到的菜品列表（status=done 时有值）"
    )
    error: str | None = Field(default=None, description="失败原因（status=failed 时有值）")
    image_url: str | None = Field(default=None, description="原始图片 URL")


class CameraLogItem(BaseModel):
    """历史识别记录单项。"""

    task_id: str
    image_url: str
    dishes: list[RecognizedDish] = Field(default_factory=list)
    created_at: str = Field(description="ISO8601 时间字符串")
    user_id: str | int | None = None
