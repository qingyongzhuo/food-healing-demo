"""PostgreSQL 数据库初始化脚本。

阶段 2 重构：废弃 MySQL，全部表迁到 PG。
创建 8 张表 + 插入标准食材种子数据。

用法: python -m app.scripts.init_db
"""

from __future__ import annotations

import asyncio

from app.database import pg_engine
from app.models.pg_orm import (
    PgBase,
    StandardFood,
)
from app.utils.logger import logger

# 标准食材种子数据（6 条，覆盖 6 大分类）
SEED_FOODS = [
    ("主食", "白米饭", 116, 2.6, 25.9, 0.3, "#E8D9C6"),
    ("肉类", "鸡胸肉", 165, 23.1, 0, 3.6, "#F7C9C9"),
    ("蔬菜", "西兰花", 34, 2.8, 4.5, 0.4, "#B7E4C7"),
    ("水果", "苹果", 52, 0.3, 14, 0.2, "#FFE8D6"),
    ("饮品", "纯牛奶", 60, 3.2, 4.8, 3.2, "#D6E4FF"),
    ("零食", "原味坚果", 600, 20, 10, 52, "#E2E2E8"),
]


async def init_pg() -> None:
    """创建所有 PostgreSQL 表（已存在的跳过）+ 插入种子数据。"""
    async with pg_engine.begin() as conn:
        await conn.run_sync(PgBase.metadata.create_all)
    logger.info("PostgreSQL 8 张表创建完成")

    # 插入标准食材种子数据（如已存在则跳过）
    from sqlalchemy import select

    from app.database import PgSessionLocal

    async with PgSessionLocal() as session:
        existing = (await session.execute(select(StandardFood).limit(1))).scalar_one_or_none()
        if existing is None:
            for category, name, cal, protein, carb, fat, color in SEED_FOODS:
                session.add(
                    StandardFood(
                        category=category,
                        food_name=name,
                        cal_per_100=cal,
                        protein_per_100=protein,
                        carb_per_100=carb,
                        fat_per_100=fat,
                        tag_color=color,
                    )
                )
            await session.commit()
            logger.info("标准食材种子数据已插入", count=len(SEED_FOODS))
        else:
            logger.info("标准食材种子数据已存在，跳过")


async def main() -> None:
    """初始化 PostgreSQL 数据库。"""
    await init_pg()
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    asyncio.run(main())
