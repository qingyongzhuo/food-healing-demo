"""食材库 + 每日饮食记录业务服务层。

Phase 4 新增。提供 5 类业务能力：
1. 食材查询：按分类筛选、模糊搜索，热门搜索结果存 Redis 缓存
2. 自定义食材 CRUD：归属当前登录用户
3. 餐食操作：添加（多选）、修改重量、删除单条
4. 自动计算：根据食材克重换算实际摄入热量与三大营养素
5. 每日汇总更新：新增 / 删除食物后自动刷新当日总营养数据

数据访问约定（与项目其他 service 一致）：
- ORM 模型见 app.models.pg_orm（StandardFood / UserCustomFood / DailyDietRecord / MealItem）
- session 通过 app.database.PgSessionLocal 取
- Redis key 必须带 food_healing: 前缀（settings.REDIS_KEY_PREFIX）

注意：当前阶段 PG 中相关表尚未实际建表，
故所有「直接读写 DB」的代码段以 pass + TODO 注释占位，
待表结构落地后用真实查询替换。Redis 缓存读写 / 营养换算 /
返回结构组装等不依赖 DB 的逻辑已写完整，可直接复用。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import PgSessionLocal, redis_client
from app.exceptions import BizError
from app.models.pg_orm import (
    DailyDietRecord,
    MealItem,
    StandardFood,
    UserCustomFood,
)
from app.models.schemas import ERR_NOT_FOUND
from app.utils.logger import logger


# ===== Redis key 与 TTL =====
FOOD_SEARCH_CACHE_PREFIX = f"{settings.REDIS_KEY_PREFIX}food_search:"
"""食材搜索缓存 key 前缀。完整 key = food_search:{category}:{keyword_normalized}"""
FOOD_SEARCH_TTL = 300  # 5 分钟
"""热门搜索结果缓存 TTL。短 TTL 保证热门词命中同时数据不太陈旧。"""

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
"""4 餐时段枚举，与前端 MEAL_SLOTS 对齐。"""


# ============================================================
# 1. 食材查询
# ============================================================
async def list_foods(
    user_id: int,
    keyword: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """查询食材列表（标准 + 当前用户自定义）。

    策略：
    1. 命中 Redis 缓存（仅缓存带 keyword 的热门搜索）→ 直接返回
    2. 未命中 → 查 DB（standard_food + user_custom_food），结果回写缓存
    3. category 仅作筛选，不缓存（命中率低）

    Returns:
        {standard: [...], custom: [...], total, page, page_size, from_cache}
    """
    keyword_norm = (keyword or "").strip()
    cache_key = _search_cache_key(category, keyword_norm)

    # 1) 尝试命中 Redis 热门搜索缓存（仅带 keyword 时启用）
    use_cache = bool(keyword_norm)
    if use_cache:
        cached = await _get_search_cache(cache_key)
        if cached is not None:
            logger.info("food_search_cache_hit", cache_key=cache_key)
            cached["from_cache"] = True
            return cached

    # 2) 查 DB
    standard_list = await _query_standard_foods(category, keyword_norm, page, page_size)
    custom_list = await _query_custom_foods(user_id, category, keyword_norm)
    total = len(standard_list) + len(custom_list)

    result = {
        "standard": standard_list,
        "custom": custom_list,
        "total": total,
        "page": page,
        "page_size": page_size,
        "from_cache": False,
    }

    # 3) 仅热门搜索（带 keyword）回写缓存，避免无关键词的全量列表占用内存
    if use_cache and total > 0:
        await _set_search_cache(cache_key, result)

    return result


async def _query_standard_foods(
    category: str | None,
    keyword: str,
    page: int,
    page_size: int,
) -> list[dict[str, Any]]:
    """查 standard_food 表（按分类筛选 + 名称模糊搜索 + 分页）。

    TODO(DB): 待 standard_food 表落地后实现真实查询，下面是预期逻辑：
        async with PgSessionLocal() as session:
            stmt = select(StandardFood)
            if category:
                stmt = stmt.where(StandardFood.category == category)
            if keyword:
                stmt = stmt.where(StandardFood.name.ilike(f"%{keyword}%"))
            stmt = stmt.order_by(StandardFood.id).offset((page - 1) * page_size).limit(page_size)
            rows = (await session.execute(stmt)).scalars().all()
            return [_standard_food_to_dict(r) for r in rows]
    """
    # 当前阶段表未落地，返回空列表占位
    pass
    return []


async def _query_custom_foods(
    user_id: int,
    category: str | None,
    keyword: str,
) -> list[dict[str, Any]]:
    """查 user_custom_food 表（仅当前用户，按分类筛选 + 名称模糊搜索）。

    TODO(DB): 待 user_custom_food 表落地后实现真实查询，下面是预期逻辑：
        async with PgSessionLocal() as session:
            stmt = select(UserCustomFood).where(UserCustomFood.user_id == user_id)
            if category:
                stmt = stmt.where(UserCustomFood.category == category)
            if keyword:
                stmt = stmt.where(UserCustomFood.name.ilike(f"%{keyword}%"))
            stmt = stmt.order_by(UserCustomFood.updated_at.desc())
            rows = (await session.execute(stmt)).scalars().all()
            return [_custom_food_to_dict(r) for r in rows]
    """
    pass
    return []


def _standard_food_to_dict(food: StandardFood) -> dict[str, Any]:
    """ORM → dict（与 schemas.StandardFoodItem 字段对齐）。"""
    return {
        "id": food.id,
        "category": food.category,
        "name": food.name,
        "kcal_per_100g": float(food.kcal_per_100g),
        "protein_per_100g": float(food.protein_per_100g),
        "carb_per_100g": float(food.carb_per_100g),
        "fat_per_100g": float(food.fat_per_100g),
        "tag_color": food.tag_color,
    }


def _custom_food_to_dict(food: UserCustomFood) -> dict[str, Any]:
    """ORM → dict（与 schemas.CustomFoodItem 字段对齐）。"""
    return {
        "id": food.id,
        "name": food.name,
        "category": food.category,
        "kcal_per_100g": float(food.kcal_per_100g),
        "protein_per_100g": float(food.protein_per_100g),
        "carb_per_100g": float(food.carb_per_100g),
        "fat_per_100g": float(food.fat_per_100g),
    }


# ============================================================
# 2. 自定义食材 CRUD
# ============================================================
async def create_custom_food(
    user_id: int,
    name: str,
    category: str,
    kcal_per_100g: float,
    protein_per_100g: float,
    carb_per_100g: float,
    fat_per_100g: float,
) -> dict[str, Any]:
    """新增自定义食材，返回新建条目。"""
    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         food = UserCustomFood(
    #             user_id=user_id, name=name, category=category,
    #             kcal_per_100g=kcal_per_100g, protein_per_100g=protein_per_100g,
    #             carb_per_100g=carb_per_100g, fat_per_100g=fat_per_100g,
    #         )
    #         session.add(food)
    #         await session.commit()
    #         await session.refresh(food)
    #         return _custom_food_to_dict(food)
    pass
    return {
        "id": 0,  # 占位，DB 落地后由 autoincrement 填充
        "name": name,
        "category": category,
        "kcal_per_100g": kcal_per_100g,
        "protein_per_100g": protein_per_100g,
        "carb_per_100g": carb_per_100g,
        "fat_per_100g": fat_per_100g,
    }


async def update_custom_food(
    user_id: int,
    custom_food_id: int,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """编辑自定义食材（部分更新）。

    权限：仅允许 owner 修改自己的食材，否则抛 NOT_FOUND（避免泄露存在性）。
    """
    food = await _get_custom_food_owned_by(user_id, custom_food_id)
    if food is None:
        raise BizError(
            code=ERR_NOT_FOUND,
            message="自定义食材不存在或无权修改",
            http_status=404,
        )

    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         for k, v in updates.items():
    #             setattr(food, k, v)
    #         await session.commit()
    #         await session.refresh(food)
    #         return _custom_food_to_dict(food)
    pass
    return {
        "id": custom_food_id,
        "name": updates.get("name", food["name"]),
        "category": updates.get("category", food["category"]),
        "kcal_per_100g": updates.get("kcal_per_100g", food["kcal_per_100g"]),
        "protein_per_100g": updates.get("protein_per_100g", food["protein_per_100g"]),
        "carb_per_100g": updates.get("carb_per_100g", food["carb_per_100g"]),
        "fat_per_100g": updates.get("fat_per_100g", food["fat_per_100g"]),
    }


async def delete_custom_food(user_id: int, custom_food_id: int) -> None:
    """删除自定义食材。

    权限：仅允许 owner 删除自己的食材。
    关联 meal_item 中冗余存储了 food_name / 营养字段，不级联删除历史记录。
    """
    food = await _get_custom_food_owned_by(user_id, custom_food_id)
    if food is None:
        raise BizError(
            code=ERR_NOT_FOUND,
            message="自定义食材不存在或无权删除",
            http_status=404,
        )

    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         await session.delete(food)
    #         await session.commit()
    pass


async def _get_custom_food_owned_by(
    user_id: int, custom_food_id: int
) -> dict[str, Any] | None:
    """查询单个自定义食材并校验归属。无权访问返回 None。"""
    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         stmt = select(UserCustomFood).where(
    #             UserCustomFood.id == custom_food_id,
    #             UserCustomFood.user_id == user_id,
    #         )
    #         food = (await session.execute(stmt)).scalar_one_or_none()
    #         return _custom_food_to_dict(food) if food else None
    pass
    return None


# ============================================================
# 3. 餐食操作（添加 / 修改 / 删除）
# ============================================================
async def add_diet_items(
    user_id: int,
    meal_type: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """向当日某一餐添加食材（支持多选）。

    流程：
    1. 获取 / 创建当日 daily_diet_record（user_id + record_date 唯一）
    2. 逐条解析 food_id / custom_food_id，查对应食材的营养/100g
    3. 按 grams 换算实际摄入，写入 meal_item
    4. 重算当日汇总

    Returns:
        {"added": [...], "summary": {...}} 新增条目列表与最新汇总
    """
    if meal_type not in MEAL_TYPES:
        raise BizError(
            code=10006,
            message=f"meal_type 必须为 {MEAL_TYPES} 之一",
        )

    record = await _ensure_today_record(user_id)

    added_items: list[dict[str, Any]] = []
    for item in items:
        food_id = item.get("food_id")
        custom_food_id = item.get("custom_food_id")
        grams = float(item["grams"])

        # 取食材元信息（标准 / 自定义 二选一）
        food_meta = await _resolve_food_meta(user_id, food_id, custom_food_id)
        if food_meta is None:
            logger.warning(
                "diet_add_food_not_found",
                food_id=food_id,
                custom_food_id=custom_food_id,
            )
            continue

        # 按克重换算实际摄入
        nutrition = _calc_nutrition_by_grams(food_meta, grams)

        new_item = {
            "diet_record_id": record["id"],
            "meal_type": meal_type,
            "food_id": food_id,
            "custom_food_id": custom_food_id,
            "food_name": food_meta["name"],
            "food_category": food_meta["category"],
            "grams": grams,
            **nutrition,
        }
        # TODO(DB): 待表落地后写入 meal_item：
        #     async with PgSessionLocal() as session:
        #         meal_item = MealItem(**new_item)
        #         session.add(meal_item)
        #         await session.commit()
        #         await session.refresh(meal_item)
        #         new_item["id"] = meal_item.id
        pass
        # 占位 id
        new_item["id"] = 0
        added_items.append(new_item)

    # 重算当日汇总
    summary = await _recompute_daily_summary(user_id)

    return {"added": added_items, "summary": summary}


async def update_meal_item_grams(
    user_id: int, item_id: int, grams: float
) -> dict[str, Any]:
    """修改单条餐食条目的克重，重算该条营养 + 当日汇总。

    权限：通过 daily_diet_record.user_id 间接校验归属。
    """
    item = await _get_meal_item_owned_by_user(user_id, item_id)
    if item is None:
        raise BizError(
            code=ERR_NOT_FOUND,
            message="餐食条目不存在或无权修改",
            http_status=404,
        )

    # 取食材元信息用于重算
    food_meta = await _resolve_food_meta(
        user_id, item["food_id"], item["custom_food_id"]
    )
    if food_meta is None:
        # 自定义食材被删等极端情况，用 meal_item 冗余字段兜底
        food_meta = {
            "name": item["food_name"],
            "category": item["food_category"],
            "kcal_per_100g": _safe_div(item["kcal"], item["grams"]) * 100,
            "protein_per_100g": _safe_div(item["protein"], item["grams"]) * 100,
            "carb_per_100g": _safe_div(item["carb"], item["grams"]) * 100,
            "fat_per_100g": _safe_div(item["fat"], item["grams"]) * 100,
        }

    new_nutrition = _calc_nutrition_by_grams(food_meta, grams)

    # TODO(DB): 待表落地后更新 meal_item：
    #     async with PgSessionLocal() as session:
    #         stmt = select(MealItem).where(MealItem.id == item_id)
    #         meal_item = (await session.execute(stmt)).scalar_one()
    #         meal_item.grams = grams
    #         for k, v in new_nutrition.items():
    #             setattr(meal_item, k, v)
    #         await session.commit()
    #         await session.refresh(meal_item)
    #         return _meal_item_to_dict(meal_item)
    pass

    updated = {
        **item,
        "grams": grams,
        **new_nutrition,
    }
    # 重算当日汇总
    summary = await _recompute_daily_summary(user_id)
    return {"item": updated, "summary": summary}


async def delete_meal_item(user_id: int, item_id: int) -> dict[str, Any]:
    """删除单条餐食条目，重算当日汇总。"""
    item = await _get_meal_item_owned_by_user(user_id, item_id)
    if item is None:
        raise BizError(
            code=ERR_NOT_FOUND,
            message="餐食条目不存在或无权删除",
            http_status=404,
        )

    # TODO(DB): 待表落地后实现：
    #     async with PgSessionLocal() as session:
    #         stmt = select(MealItem).where(MealItem.id == item_id)
    #         meal_item = (await session.execute(stmt)).scalar_one()
    #         await session.delete(meal_item)
    #         await session.commit()
    pass

    summary = await _recompute_daily_summary(user_id)
    return {"deleted_id": item_id, "summary": summary}


# ============================================================
# 4. 当日饮食汇总
# ============================================================
async def get_today_diet(user_id: int) -> dict[str, Any]:
    """获取今日全部饮食 + 总营养数据（首页核心接口）。

    Returns:
        {
            record_id: int | None,
            record_date: "YYYY-MM-DD",
            summary: {kcal, protein, carb, fat},
            groups: [{meal_type, items: [...], subtotal_kcal}, ...]
        }
    """
    today = date.today()
    record = await _get_today_record(user_id, today)
    if record is None:
        return {
            "record_id": None,
            "record_date": today.isoformat(),
            "summary": {"kcal": 0, "protein": 0, "carb": 0, "fat": 0},
            "groups": [
                {"meal_type": m, "items": [], "subtotal_kcal": 0}
                for m in MEAL_TYPES
            ],
        }

    items = await _list_meal_items(record["id"])
    groups = _group_items_by_meal(items)
    summary = _aggregate_summary(items)
    return {
        "record_id": record["id"],
        "record_date": today.isoformat(),
        "summary": summary,
        "groups": groups,
    }


# ============================================================
# 内部工具：营养计算
# ============================================================
def _calc_nutrition_by_grams(food_meta: dict[str, Any], grams: float) -> dict[str, float]:
    """按克重换算实际摄入营养。

    food_meta 中字段单位为「每 100g」，grams/100 后相乘。
    保留 2 位小数，避免浮点精度问题。
    """
    ratio = grams / 100.0
    return {
        "kcal": round(float(food_meta["kcal_per_100g"]) * ratio, 2),
        "protein": round(float(food_meta["protein_per_100g"]) * ratio, 2),
        "carb": round(float(food_meta["carb_per_100g"]) * ratio, 2),
        "fat": round(float(food_meta["fat_per_100g"]) * ratio, 2),
    }


def _aggregate_summary(items: list[dict[str, Any]]) -> dict[str, float]:
    """汇总当日总营养（4 餐条目累加）。"""
    summary = {"kcal": 0.0, "protein": 0.0, "carb": 0.0, "fat": 0.0}
    for it in items:
        summary["kcal"] += float(it.get("kcal", 0))
        summary["protein"] += float(it.get("protein", 0))
        summary["carb"] += float(it.get("carb", 0))
        summary["fat"] += float(it.get("fat", 0))
    return {k: round(v, 2) for k, v in summary.items()}


def _group_items_by_meal(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 meal_type 分组，返回 4 餐列表。"""
    groups: dict[str, list[dict[str, Any]]] = {m: [] for m in MEAL_TYPES}
    for it in items:
        m = it.get("meal_type", "snack")
        if m not in groups:
            m = "snack"
        groups[m].append(it)

    result = []
    for m in MEAL_TYPES:
        sub_items = groups[m]
        subtotal = sum(float(i.get("kcal", 0)) for i in sub_items)
        result.append(
            {
                "meal_type": m,
                "items": sub_items,
                "subtotal_kcal": round(subtotal, 2),
            }
        )
    return result


def _safe_div(a: float, b: float) -> float:
    """安全除法，b 为 0 返回 0。"""
    if not b:
        return 0.0
    return float(a) / float(b)


# ============================================================
# 内部工具：当日记录管理
# ============================================================
async def _ensure_today_record(user_id: int) -> dict[str, Any]:
    """获取或创建当日 daily_diet_record。

    TODO(DB): 表落地后实现 upsert：
        async with PgSessionLocal() as session:
            today = date.today()
            stmt = select(DailyDietRecord).where(
                DailyDietRecord.user_id == user_id,
                DailyDietRecord.record_date == today,
            )
            record = (await session.execute(stmt)).scalar_one_or_none()
            if record is None:
                record = DailyDietRecord(user_id=user_id, record_date=today)
                session.add(record)
                await session.commit()
                await session.refresh(record)
            return {"id": record.id, "record_date": record.record_date}
    """
    today = date.today()
    pass
    return {"id": 0, "record_date": today}


async def _get_today_record(
    user_id: int, today: date
) -> dict[str, Any] | None:
    """查当日记录（不创建）。"""
    # TODO(DB): 表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         stmt = select(DailyDietRecord).where(
    #             DailyDietRecord.user_id == user_id,
    #             DailyDietRecord.record_date == today,
    #         )
    #         record = (await session.execute(stmt)).scalar_one_or_none()
    #         return {"id": record.id} if record else None
    pass
    return None


async def _list_meal_items(record_id: int) -> list[dict[str, Any]]:
    """查当日所有 meal_item。"""
    # TODO(DB): 表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         stmt = select(MealItem).where(MealItem.diet_record_id == record_id)
    #         rows = (await session.execute(stmt)).scalars().all()
    #         return [_meal_item_to_dict(r) for r in rows]
    pass
    return []


async def _get_meal_item_owned_by_user(
    user_id: int, item_id: int
) -> dict[str, Any] | None:
    """查 meal_item 并通过 daily_diet_record.user_id 校验归属。

    TODO(DB): 表落地后实现，预期逻辑：
        async with PgSessionLocal() as session:
            stmt = (
                select(MealItem)
                .join(DailyDietRecord, MealItem.diet_record_id == DailyDietRecord.id)
                .where(MealItem.id == item_id, DailyDietRecord.user_id == user_id)
            )
            item = (await session.execute(stmt)).scalar_one_or_none()
            return _meal_item_to_dict(item) if item else None
    """
    pass
    return None


def _meal_item_to_dict(item: MealItem) -> dict[str, Any]:
    """ORM → dict（与 schemas.MealItemInfo 字段对齐）。"""
    return {
        "id": item.id,
        "meal_type": item.meal_type,
        "food_id": item.food_id,
        "custom_food_id": item.custom_food_id,
        "food_name": item.food_name,
        "food_category": item.food_category,
        "grams": float(item.grams),
        "kcal": float(item.kcal),
        "protein": float(item.protein),
        "carb": float(item.carb),
        "fat": float(item.fat),
    }


async def _resolve_food_meta(
    user_id: int,
    food_id: int | None,
    custom_food_id: int | None,
) -> dict[str, Any] | None:
    """根据 food_id / custom_food_id 查对应食材的元信息。

    返回统一字段：{name, category, kcal_per_100g, protein_per_100g,
                  carb_per_100g, fat_per_100g}
    """
    if food_id:
        # TODO(DB): 查 standard_food
        #     async with PgSessionLocal() as session:
        #         stmt = select(StandardFood).where(StandardFood.id == food_id)
        #         food = (await session.execute(stmt)).scalar_one_or_none()
        #         if food is None:
        #             return None
        #         return {
        #             "name": food.name,
        #             "category": food.category,
        #             "kcal_per_100g": float(food.kcal_per_100g),
        #             "protein_per_100g": float(food.protein_per_100g),
        #             "carb_per_100g": float(food.carb_per_100g),
        #             "fat_per_100g": float(food.fat_per_100g),
        #         }
        pass
        return None

    if custom_food_id:
        # TODO(DB): 查 user_custom_food 并校验 user_id 归属
        #     async with PgSessionLocal() as session:
        #         stmt = select(UserCustomFood).where(
        #             UserCustomFood.id == custom_food_id,
        #             UserCustomFood.user_id == user_id,
        #         )
        #         food = (await session.execute(stmt)).scalar_one_or_none()
        #         if food is None:
        #             return None
        #         return {
        #             "name": food.name,
        #             "category": food.category,
        #             "kcal_per_100g": float(food.kcal_per_100g),
        #             "protein_per_100g": float(food.protein_per_100g),
        #             "carb_per_100g": float(food.carb_per_100g),
        #             "fat_per_100g": float(food.fat_per_100g),
        #         }
        pass
        return None

    return None


async def _recompute_daily_summary(user_id: int) -> dict[str, float]:
    """重算当日汇总并写回 daily_diet_record。

    TODO(DB): 表落地后实现，预期逻辑：
        1. 查当日 daily_diet_record（无则返回零值汇总）
        2. 查当日所有 meal_item，累加 kcal/protein/carb/fat
        3. UPDATE daily_diet_record.total_* = 累加值
        4. 返回汇总 dict
    """
    items = await _list_meal_items(0)  # 占位 record_id
    summary = _aggregate_summary(items)
    # TODO(DB): 写回 daily_diet_record.total_*
    pass
    return summary


# ============================================================
# 内部工具：Redis 食材搜索缓存
# ============================================================
def _search_cache_key(category: str | None, keyword: str) -> str:
    """构造搜索缓存 key。

    格式：food_search:{category or 'all'}:{keyword_normalized}
    """
    cat = category or "all"
    return f"{FOOD_SEARCH_CACHE_PREFIX}{cat}:{keyword}"


async def _get_search_cache(cache_key: str) -> dict[str, Any] | None:
    """读 Redis 搜索缓存，失败 graceful 返回 None。"""
    try:
        raw = await redis_client.get(cache_key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("food_search_cache_get_failed", error=str(exc))
        return None


async def _set_search_cache(cache_key: str, data: dict[str, Any]) -> None:
    """写 Redis 搜索缓存，失败 graceful。"""
    try:
        await redis_client.set(
            cache_key,
            json.dumps(data, ensure_ascii=False),
            ex=FOOD_SEARCH_TTL,
        )
    except Exception as exc:
        logger.warning("food_search_cache_set_failed", error=str(exc))
