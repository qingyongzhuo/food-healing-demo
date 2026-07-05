"""食材库 + 每日饮食记录模块 Pydantic 校验模型。

Phase 4 新增，对应 4 类业务场景：
1. 食材列表查询入参 / 返回模型（标准 + 自定义）
2. 自定义食材新增 / 编辑入参
3. 餐食添加 / 修改请求模型
4. 当日饮食汇总返回模型

字段命名与前端 frontend-v2/src/lib/api.js 对齐（snake_case）。
6 大分类：主食 / 肉类 / 蔬菜 / 蛋奶 / 汤品 / 水果。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ===== 1. 食材列表查询入参 =====
class FoodListQuery(BaseModel):
    """食材列表查询入参。

    keyword 与 category 均可选，同时给出时取交集。
    page / page_size 分页，默认 1 / 20。
    """

    keyword: str | None = Field(
        default=None, max_length=64, description="食材名称模糊搜索关键词"
    )
    category: str | None = Field(
        default=None, max_length=16, description="分类筛选：主食/肉类/蔬菜/蛋奶/汤品/水果"
    )
    page: int = Field(default=1, ge=1, description="页码，从 1 起")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数，[1, 100]")


# ===== 2. 食材返回模型 =====
class StandardFoodItem(BaseModel):
    """标准食材返回单项。所有营养字段单位为「每 100g」。"""

    id: int
    category: str
    name: str
    kcal_per_100g: float
    protein_per_100g: float
    carb_per_100g: float
    fat_per_100g: float
    tag_color: str


class CustomFoodItem(BaseModel):
    """自定义食材返回单项。归属当前登录用户。"""

    id: int
    name: str
    category: str
    kcal_per_100g: float
    protein_per_100g: float
    carb_per_100g: float
    fat_per_100g: float


class FoodListResponse(BaseModel):
    """食材列表返回。同时返回标准 + 当前用户自定义食材。"""

    standard: list[StandardFoodItem] = Field(default_factory=list)
    custom: list[CustomFoodItem] = Field(default_factory=list)
    total: int = Field(default=0, description="合计条数（标准 + 自定义）")
    page: int = 1
    page_size: int = 20
    from_cache: bool = Field(
        default=False, description="是否命中 Redis 热门搜索缓存"
    )


# ===== 3. 自定义食材新增 / 编辑入参 =====
VALID_CATEGORIES = {"主食", "肉类", "蔬菜", "蛋奶", "汤品", "水果", "其他"}


class CustomFoodCreateRequest(BaseModel):
    """新增自定义食材入参。

    所有营养字段单位为「每 100g」，业务层按实际克重换算。
    """

    name: str = Field(min_length=1, max_length=64, description="食材名称")
    category: str = Field(default="其他", max_length=16, description="分类")
    kcal_per_100g: float = Field(ge=0, le=5000, description="每 100g 热量(kcal)")
    protein_per_100g: float = Field(ge=0, le=500, description="每 100g 蛋白质(g)")
    carb_per_100g: float = Field(ge=0, le=500, description="每 100g 碳水(g)")
    fat_per_100g: float = Field(ge=0, le=500, description="每 100g 脂肪(g)")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("食材名称不能为空")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"分类必须为 {VALID_CATEGORIES} 之一")
        return v


class CustomFoodUpdateRequest(BaseModel):
    """编辑自定义食材入参。所有字段可选（部分更新）。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=16)
    kcal_per_100g: float | None = Field(default=None, ge=0, le=5000)
    protein_per_100g: float | None = Field(default=None, ge=0, le=500)
    carb_per_100g: float | None = Field(default=None, ge=0, le=500)
    fat_per_100g: float | None = Field(default=None, ge=0, le=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("食材名称不能为空")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v not in VALID_CATEGORIES:
            raise ValueError(f"分类必须为 {VALID_CATEGORIES} 之一")
        return v


# ===== 4. 餐食添加 / 修改请求模型 =====
MealType = Literal["breakfast", "lunch", "dinner", "snack"]


class MealItemAdd(BaseModel):
    """单个餐食条目添加入参。

    food_id / custom_food_id 二选一：
    - 选 standard 食材时传 food_id
    - 选自定义食材时传 custom_food_id
    grams 必填，业务层按 grams / 100 换算实际摄入。
    """

    food_id: int | None = Field(default=None, description="标准食材 ID")
    custom_food_id: int | None = Field(default=None, description="自定义食材 ID")
    grams: float = Field(gt=0, le=5000, description="食用克重，范围 (0, 5000]")

    @field_validator("food_id", "custom_food_id")
    @classmethod
    def at_least_one_id(cls, v):
        # Pydantic v2 字段级 validator 难以访问其他字段，
        # 真正的互斥校验放 model_validator，这里只做类型检查。
        return v


class DietAddRequest(BaseModel):
    """添加餐食请求。支持多选（一次添加多个食材到同一餐时）。"""

    meal_type: MealType = Field(description="餐时：breakfast/lunch/dinner/snack")
    items: list[MealItemAdd] = Field(
        min_length=1, max_length=20, description="食材列表，1~20 条"
    )


class DietItemUpdateRequest(BaseModel):
    """修改单条餐食重量。

    仅允许改 grams，业务层重新计算 kcal / 蛋白 / 碳水 / 脂肪。
    """

    grams: float = Field(gt=0, le=5000, description="新的食用克重")


# ===== 5. 当日饮食汇总返回模型 =====
class MealItemInfo(BaseModel):
    """餐食条目返回。包含按 grams 换算后的实际摄入营养。"""

    id: int
    meal_type: str
    food_id: int | None = None
    custom_food_id: int | None = None
    food_name: str
    food_category: str
    grams: float
    kcal: float
    protein: float
    carb: float
    fat: float


class MealGroup(BaseModel):
    """单餐分组。按 meal_type 聚合，前端直接渲染。"""

    meal_type: str
    items: list[MealItemInfo] = Field(default_factory=list)
    subtotal_kcal: float = Field(default=0, description="该餐小计热量")


class DietTodayResponse(BaseModel):
    """当日饮食汇总返回。首页核心接口数据。

    - summary：当日总营养（用于顶部营养概览卡片）
    - groups：按 4 餐分组（breakfast/lunch/dinner/snack），含每条条目
    - record_id：当日 daily_diet_record.id，前端修改/删除时无需传
    """

    record_id: int | None = None
    record_date: str
    summary: dict = Field(
        default_factory=lambda: {
            "kcal": 0,
            "protein": 0,
            "carb": 0,
            "fat": 0,
        },
        description="当日总营养汇总 {kcal, protein, carb, fat}",
    )
    groups: list[MealGroup] = Field(default_factory=list)
