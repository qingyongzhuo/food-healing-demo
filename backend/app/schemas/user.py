"""用户中心模块 Pydantic 校验模型。

4 类入参/出参模型：
- ProfileUpdateRequest：基础资料修改（昵称、头像、手机号）
- BodyUpdateRequest：身体数据调整（身高、体重、性别、年龄）
- TargetUpdateRequest：营养目标修改（每日热量、三大营养素、目标类型）
- UserProfileResponse：用户完整信息返回

字段命名与前端 frontend-v2/src/lib/api.js 对齐（snake_case）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ===== 1. 基础资料修改入参 =====
class ProfileUpdateRequest(BaseModel):
    """基础资料修改入参。

    昵称、头像 URL、手机号均可选（部分更新），但至少传一个字段。
    主题 theme 也归入此模型（个人中心设置）。
    """

    nickname: str | None = Field(default=None, max_length=64, description="昵称")
    avatar_url: str | None = Field(
        default=None, max_length=512, description="头像 URL（相对路径）"
    )
    phone: str | None = Field(
        default=None, max_length=20, description="手机号（仅格式校验，不做归属地校验）"
    )
    theme: Literal["light", "dark"] | None = Field(
        default=None, description="深浅色主题：light / dark"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """手机号格式校验：允许空、允许 11 位数字（中国大陆）或带 +86 前缀。"""
        if v is None or v == "":
            return None
        cleaned = v.strip().replace(" ", "").replace("-", "")
        if cleaned.startswith("+86"):
            cleaned = cleaned[3:]
        if not cleaned.isdigit() or len(cleaned) != 11:
            raise ValueError("手机号格式不正确（需 11 位数字）")
        return cleaned

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str | None) -> str | None:
        """昵称去空白。"""
        if v is None:
            return None
        v = v.strip()
        return v or None


# ===== 2. 身体数据调整入参 =====
class BodyUpdateRequest(BaseModel):
    """身体数据调整入参。

    身高、体重、性别、年龄均可选（部分更新）。
    """

    height_cm: float | None = Field(
        default=None, gt=0, lt=300, description="身高(cm)，范围 (0, 300)"
    )
    weight_kg: float | None = Field(
        default=None, gt=0, lt=500, description="体重(kg)，范围 (0, 500)"
    )
    gender: Literal["male", "female"] | None = Field(
        default=None, description="性别：male / female"
    )
    age: int | None = Field(
        default=None, ge=1, le=150, description="年龄，范围 [1, 150]"
    )


# ===== 3. 营养目标修改入参 =====
class TargetUpdateRequest(BaseModel):
    """营养目标修改入参。

    每日热量、蛋白、碳水、脂肪目标值，以及目标类型（减脂/增肌/维持）。
    三大营养素单位均为克(g)。
    """

    daily_kcal: int = Field(ge=800, le=5000, description="每日热量目标(kcal)，范围 [800, 5000]")
    protein_g: int = Field(ge=0, le=500, description="每日蛋白质目标(g)")
    carb_g: int = Field(ge=0, le=1000, description="每日碳水目标(g)")
    fat_g: int = Field(ge=0, le=300, description="每日脂肪目标(g)")
    target_type: Literal["fat_loss", "maintain", "muscle_gain"] = Field(
        default="maintain", description="目标类型：fat_loss / maintain / muscle_gain"
    )


# ===== 4. 用户完整信息返回模型 =====
class UserBaseInfo(BaseModel):
    """用户基础信息（来自 user 表，PG）。"""

    user_id: int
    nickname: str = ""
    avatar_url: str = ""
    phone: str = ""
    created_at: str | None = None


class UserBodyTargetInfo(BaseModel):
    """用户身体数据与营养目标（来自 user_body_target 表）。"""

    height_cm: float | None = None
    weight_kg: float | None = None
    gender: str | None = None
    age: int | None = None
    target_type: str = "maintain"
    daily_kcal: int = 2000
    protein_g: int = 60
    carb_g: int = 260
    fat_g: int = 65
    theme: str = "light"


class UserCollectFoodItem(BaseModel):
    """收藏食材列表单项。"""

    food_id: str
    name: str = ""
    category: str = ""
    kcal: int = 0
    protein: float = 0
    carb: float = 0
    fat: float = 0
    collected_at: str | None = None


class UserProfileResponse(BaseModel):
    """用户完整信息返回模型。

    聚合 user_base + body_target + collect_food_ids 三段数据。
    """

    user: UserBaseInfo
    body_target: UserBodyTargetInfo
    collect_food_ids: list[str] = Field(
        default_factory=list, description="收藏食材 ID 列表（仅 ID，详情另查 /user/collect）"
    )
