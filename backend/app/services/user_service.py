"""用户中心业务服务层（Phase 3）。

功能：
- 查询单用户全部基础信息（user + body_target + collect_food_ids）
- 更新用户基础资料（昵称、头像、手机号、主题）
- 新增/修改用户身体数据与营养目标
- 收藏食材添加、取消收藏、查询收藏列表
- 利用 Redis 缓存当前用户收藏食材 ID 集合

数据库说明：
当前项目正处于 MySQL → PostgreSQL 迁移期。本服务的 ORM 模型已就绪
（app.models.pg_orm.UserBodyTarget / UserCollectFood），但实际 DB 操作
暂时用 pass + 注释占位，等用户完成数据库迁移后填充实现。
路由层接口已完整，前端可先对接契约。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import PgSessionLocal, redis_client
from app.exceptions import BizError
from app.models.schemas import ERR_DB_QUERY, ERR_NOT_FOUND, ERR_PARAM_FORMAT, ERR_USER_EXISTS
from app.utils.logger import logger

# Redis key：收藏食材 ID 集合，TTL 1 天
COLLECT_REDIS_KEY = f"{settings.REDIS_KEY_PREFIX}collect:{{user_id}}"
COLLECT_REDIS_TTL = 86400  # 1 天


def _collect_key(user_id: int) -> str:
    """构造用户收藏集合的 Redis key。"""
    return COLLECT_REDIS_KEY.format(user_id=user_id)


async def get_full_profile(user_id: int) -> dict[str, Any]:
    """查询单用户全部基础信息。

    返回结构：
    {
        "user": { user_id, nickname, avatar_url, phone, created_at },
        "body_target": { height_cm, weight_kg, gender, age, target_type,
                         daily_kcal, protein_g, carb_g, fat_g, theme },
        "collect_food_ids": ["f001", "f002", ...]
    }

    数据来源：
    - user：users 表（PG）
    - body_target：user_body_target 表（PG）
    - collect_food_ids：优先 Redis 缓存，未命中查 user_collect_food 表
    """
    from app.models.pg_orm import User, UserBodyTarget

    async with PgSessionLocal() as session:
        # 1. 查 users 表
        user_row = await session.get(User, user_id)
        if user_row is None:
            raise BizError(code=ERR_NOT_FOUND, message="用户不存在")
        user = {
            "user_id": user_row.id,
            "nickname": user_row.nickname,
            "avatar_url": user_row.avatar_url or "",
            "phone": user_row.phone or "",
            "created_at": user_row.create_time.isoformat() if user_row.create_time else None,
        }

        # 2. 查 user_body_target 表
        stmt = select(UserBodyTarget).where(UserBodyTarget.user_id == user_id)
        target_row = (await session.execute(stmt)).scalar_one_or_none()
        if target_row:
            body_target = {
                "height_cm": float(target_row.height) if target_row.height else None,
                "weight_kg": float(target_row.weight) if target_row.weight else None,
                "gender": target_row.gender,
                "age": None,
                "target_type": target_row.target_type or "maintain",
                "daily_kcal": target_row.daily_calorie or 2000,
                "protein_g": target_row.target_protein or 60,
                "carb_g": target_row.target_carb or 260,
                "fat_g": target_row.target_fat or 65,
                "theme": user_row.theme or "light",
            }
        else:
            body_target = {
                "height_cm": None, "weight_kg": None, "gender": None, "age": None,
                "target_type": "maintain",
                "daily_kcal": 2000, "protein_g": 60, "carb_g": 260, "fat_g": 65,
                "theme": "light",
            }

    # 3. 查收藏 ID 集合
    collect_food_ids: list[str] = []
    try:
        cached = await redis_client.smembers(_collect_key(user_id))
        if cached:
            collect_food_ids = sorted(cached)
    except Exception as exc:
        logger.warning("redis_collect_read_failed", user_id=user_id, error=str(exc))

    return {
        "user": user,
        "body_target": body_target,
        "collect_food_ids": collect_food_ids,
    }


async def update_profile(
    user_id: int,
    nickname: str | None = None,
    avatar_url: str | None = None,
    phone: str | None = None,
    theme: str | None = None,
) -> dict[str, Any]:
    """更新用户基础资料（昵称、头像、手机号、主题）。

    至少传一个字段，部分更新。返回更新后的 user + theme 字段。
    """
    from app.models.pg_orm import User, UserBodyTarget

    if all(v is None for v in (nickname, avatar_url, phone, theme)):
        raise BizError(code=ERR_PARAM_FORMAT, message="至少需要提供一个待更新字段")

    async with PgSessionLocal() as session:
        # 1. 更新 users 表
        user = await session.get(User, user_id)
        if user is None:
            raise BizError(code=ERR_NOT_FOUND, message="用户不存在")

        if nickname is not None and nickname.strip():
            # 查重
            stmt = select(User).where(User.nickname == nickname.strip(), User.id != user_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                raise BizError(code=ERR_USER_EXISTS, message="昵称已被占用")
            user.nickname = nickname.strip()
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if phone is not None:
            user.phone = phone

        # 2. 更新 user_body_target 表的 theme（theme 在 User 表上）
        if theme is not None:
            user.theme = theme

        await session.commit()
        await session.refresh(user)
        logger.info("user_profile_updated", user_id=user_id, nickname=user.nickname)

    return {
        "user": {
            "user_id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url or "",
            "phone": user.phone or "",
        },
        "theme": theme or "light",
    }


async def update_body(
    user_id: int,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    gender: str | None = None,
    age: int | None = None,
) -> dict[str, Any]:
    """新增/修改用户身体数据（身高、体重、性别、年龄）。

    upsert user_body_target 表。返回更新后的 body_target 字段。
    """
    from app.models.pg_orm import UserBodyTarget

    if all(v is None for v in (height_cm, weight_kg, gender, age)):
        raise BizError(code=ERR_PARAM_FORMAT, message="至少需要提供一个待更新字段")

    async with PgSessionLocal() as session:
        stmt = select(UserBodyTarget).where(UserBodyTarget.user_id == user_id)
        target = (await session.execute(stmt)).scalar_one_or_none()
        if target is None:
            target = UserBodyTarget(user_id=user_id)
            session.add(target)

        if height_cm is not None:
            target.height = height_cm
        if weight_kg is not None:
            target.weight = weight_kg
        if gender is not None:
            target.gender = gender
        if age is not None:
            target.age = age

        await session.commit()
        await session.refresh(target)
        logger.info("user_body_updated", user_id=user_id)

    return {
        "height_cm": float(target.height) if target.height else None,
        "weight_kg": float(target.weight) if target.weight else None,
        "gender": target.gender,
        "age": None,
    }


async def update_target(
    user_id: int,
    daily_kcal: int,
    protein_g: int,
    carb_g: int,
    fat_g: int,
    target_type: str = "maintain",
) -> dict[str, Any]:
    """修改每日营养目标（每日热量、三大营养素、目标类型）。

    upsert user_body_target 表。返回更新后的 target 字段。
    """
    from app.models.pg_orm import UserBodyTarget

    async with PgSessionLocal() as session:
        stmt = select(UserBodyTarget).where(UserBodyTarget.user_id == user_id)
        target = (await session.execute(stmt)).scalar_one_or_none()
        if target is None:
            target = UserBodyTarget(user_id=user_id)
            session.add(target)

        target.daily_calorie = daily_kcal
        target.target_protein = protein_g
        target.target_carb = carb_g
        target.target_fat = fat_g
        target.target_type = target_type

        await session.commit()
        await session.refresh(target)
        logger.info("user_target_updated", user_id=user_id, daily_kcal=daily_kcal)

    return {
        "daily_kcal": target.daily_calorie,
        "protein_g": target.target_protein,
        "carb_g": target.target_carb,
        "fat_g": target.target_fat,
        "target_type": target.target_type,
    }


async def list_collect_foods(user_id: int) -> list[dict[str, Any]]:
    """查询用户收藏食材列表（含食物详情）。

    流程：
    1. 从 Redis 取收藏 food_id 集合（未命中则查 DB 回填）
    2. 按 food_id 批量查 dishes 表（迁移后 PG）拿详情
    3. 返回 [{ food_id, name, category, kcal, protein, carb, fat, collected_at }]

    数据来源：
    - food_id 列表：Redis 缓存 / user_collect_food 表（PG）
    - 食物详情：dishes 表（迁移后归属 PG）
    """
    # TODO: 等 PG 迁移完成后实现
    # 1. food_ids = await redis_client.smembers(_collect_key(user_id))
    # 2. if not food_ids:
    #        async with PgSessionLocal() as session:
    #            rows = await session.execute(
    #                select(UserCollectFood.food_id, UserCollectFood.created_at)
    #                .where(UserCollectFood.user_id == user_id)
    #            )
    #            food_ids = [r.food_id for r in rows]
    #        if food_ids:
    #            await redis_client.sadd(_collect_key(user_id), *food_ids)
    #            await redis_client.expire(_collect_key(user_id), COLLECT_REDIS_TTL)
    # 3. 批量查 dishes 表拿详情
    # 以下是占位实现
    try:
        cached = await redis_client.smembers(_collect_key(user_id))
        if cached:
            logger.info("collect_list_cache_hit", user_id=user_id, count=len(cached))
    except Exception as exc:
        logger.warning("redis_collect_read_failed", user_id=user_id, error=str(exc))

    return []


async def toggle_collect_food(user_id: int, food_id: str) -> dict[str, Any]:
    """收藏 / 取消收藏食材（toggle 语义）。

    已收藏 → 取消；未收藏 → 收藏。同步更新 Redis 缓存。

    返回 { collected: bool, food_id: str }。
    """
    if not food_id:
        raise BizError(code=ERR_PARAM_FORMAT, message="food_id 不能为空")

    # TODO: 等 PG 迁移完成后实现
    # 1. async with PgSessionLocal() as session:
    #        existing = await session.execute(
    #            select(UserCollectFood).where(
    #                UserCollectFood.user_id == user_id,
    #                UserCollectFood.food_id == food_id,
    #            )
    #        )
    #        row = existing.scalar_one_or_none()
    #        if row:
    #            await session.delete(row)
    #            collected = False
    #        else:
    #            session.add(UserCollectFood(user_id=user_id, food_id=food_id))
    #            collected = True
    #        await session.commit()
    # 2. 同步 Redis 缓存
    #    if collected:
    #        await redis_client.sadd(_collect_key(user_id), food_id)
    #    else:
    #        await redis_client.srem(_collect_key(user_id), food_id)
    #    await redis_client.expire(_collect_key(user_id), COLLECT_REDIS_TTL)
    # 以下是占位实现：尝试操作 Redis（若 Redis 可用），DB 部分等迁移后补
    collected = False
    try:
        key = _collect_key(user_id)
        is_member = await redis_client.sismember(key, food_id)
        if is_member:
            await redis_client.srem(key, food_id)
            collected = False
        else:
            await redis_client.sadd(key, food_id)
            await redis_client.expire(key, COLLECT_REDIS_TTL)
            collected = True
    except Exception as exc:
        logger.warning("redis_collect_toggle_failed", user_id=user_id, error=str(exc))
        # Redis 不可用时返回默认值（DB 迁移后由 DB 决定真值）
        raise BizError(code=ERR_DB_QUERY, message="收藏操作暂不可用，请稍后重试") from exc

    logger.info("user_collect_toggled", user_id=user_id, food_id=food_id, collected=collected)
    return {"collected": collected, "food_id": food_id}


async def get_collect_ids(user_id: int) -> list[str]:
    """查询用户收藏的 food_id 列表（仅 ID，给其他模块复用）。

    优先 Redis，未命中查 DB 回填。
    """
    try:
        cached = await redis_client.smembers(_collect_key(user_id))
        if cached:
            return sorted(cached)
    except Exception as exc:
        logger.warning("redis_collect_read_failed", user_id=user_id, error=str(exc))

    # TODO: 等 PG 迁移完成后实现
    # async with PgSessionLocal() as session:
    #     rows = await session.execute(
    #         select(UserCollectFood.food_id).where(UserCollectFood.user_id == user_id)
    #     )
    #     food_ids = [r[0] for r in rows]
    # if food_ids:
    #     try:
    #         await redis_client.sadd(_collect_key(user_id), *food_ids)
    #         await redis_client.expire(_collect_key(user_id), COLLECT_REDIS_TTL)
    #     except Exception:
    #         pass
    # return food_ids
    return []
