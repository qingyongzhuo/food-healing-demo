"""检查 PG 各表数据情况，便于初始化后核对。

用法: uv run python -m app.scripts.check_data
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.database import PgSessionLocal
from app.models.pg_orm import (
    DailyDietRecord,
    MealItem,
    StandardFood,
    SystemMessage,
    User,
    UserBodyTarget,
    UserCollectFood,
    UserCustomFood,
)
from app.utils.logger import logger


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _sample(session, model, limit: int = 5):
    rows = (await session.execute(select(model).limit(limit))).scalars().all()
    return rows


async def main() -> None:
    async with PgSessionLocal() as session:
        for name, model in [
            ("user", User),
            ("user_body_target", UserBodyTarget),
            ("standard_food", StandardFood),
            ("user_custom_food", UserCustomFood),
            ("user_collect_food", UserCollectFood),
            ("daily_diet_record", DailyDietRecord),
            ("meal_item", MealItem),
            ("system_message", SystemMessage),
        ]:
            count = await _count(session, model)
            print(f"{name:24s} {count:6d} rows")

        # 显示 standard_food 全部样本（仅 6 条种子）
        print("\n=== standard_food 样本 ===")
        foods = await _sample(session, StandardFood, limit=20)
        for f in foods:
            print(
                f"  id={f.id} cat={f.category} name={f.food_name} "
                f"cal={f.cal_per_100} p={f.protein_per_100} c={f.carb_per_100} f={f.fat_per_100} tag={f.tag_color}"
            )

        print("\n=== user 样本 ===")
        users = await _sample(session, User, limit=5)
        for u in users:
            print(f"  id={u.id} nickname={u.nickname}")


if __name__ == "__main__":
    asyncio.run(main())
