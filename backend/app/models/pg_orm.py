"""PostgreSQL SQLAlchemy ORM 模型。

按阶段 2 全新数据库设计，8 张表：
1. user（用户基础表）
2. user_body_target（身体 & 营养目标）
3. standard_food（系统标准食材库）
4. user_custom_food（用户自定义食材）
5. user_collect_food（用户收藏食材）
6. daily_diet_record（每日饮食总记录）
7. meal_item（单餐食物明细）
8. system_message（系统消息通知）

注意：表名 "user" 是 PG 保留字，SQLAlchemy 会自动加引号。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PgBase(DeclarativeBase):
    """PostgreSQL declarative base。"""
    pass


# ===== 1. user（用户基础表）=====
class User(PgBase):
    """用户基础表。nickname 作为登录账号（唯一必填）。"""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    theme: Mapped[str] = mapped_column(String(10), nullable=False, default="light")
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime)


# ===== 2. user_body_target（身体 & 营养目标）=====
class UserBodyTarget(PgBase):
    """用户身体数据 & 营养目标。target_type: lose/gain/maintain。"""

    __tablename__ = "user_body_target"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    height: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    gender: Mapped[str | None] = mapped_column(String(6))
    target_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="maintain"
    )
    daily_calorie: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    target_protein: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    target_carb: Mapped[int] = mapped_column(Integer, nullable=False, default=250)
    target_fat: Mapped[int] = mapped_column(Integer, nullable=False, default=65)
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ===== 3. standard_food（系统标准食材库）=====
class StandardFood(PgBase):
    """系统标准食材库。category: 主食/肉类/蔬菜/水果/饮品/零食。"""

    __tablename__ = "standard_food"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(12), nullable=False)
    food_name: Mapped[str] = mapped_column(String(50), nullable=False)
    cal_per_100: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_per_100: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    carb_per_100: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    fat_per_100: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    tag_color: Mapped[str] = mapped_column(String(12), nullable=False)
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ===== 4. user_custom_food（用户自定义食材）=====
class UserCustomFood(PgBase):
    """用户自定义食材。"""

    __tablename__ = "user_custom_food"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(12), nullable=False)
    food_name: Mapped[str] = mapped_column(String(50), nullable=False)
    cal_per_100: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_per_100: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    carb_per_100: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    fat_per_100: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    tag_color: Mapped[str] = mapped_column(String(12), nullable=False)
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ===== 5. user_collect_food（用户收藏食材）=====
class UserCollectFood(PgBase):
    """用户收藏食材。food_id / custom_food_id 二选一。"""

    __tablename__ = "user_collect_food"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    food_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("standard_food.id", ondelete="CASCADE")
    )
    custom_food_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("user_custom_food.id", ondelete="CASCADE")
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "food_id", "custom_food_id", name="uq_user_collect"),
    )


# ===== 6. daily_diet_record（每日饮食总记录）=====
class DailyDietRecord(PgBase):
    """每日饮食总记录。每用户每日一条。"""

    __tablename__ = "daily_diet_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    record_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_calorie: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_protein: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=0)
    total_carb: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=0)
    total_fat: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "record_date", name="uq_user_date"),
    )


# ===== 7. meal_item（单餐食物明细）=====
class MealItem(PgBase):
    """单餐食物明细。meal_type: breakfast/lunch/dinner/snack。"""

    __tablename__ = "meal_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    diet_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("daily_diet_record.id", ondelete="CASCADE"), nullable=False
    )
    meal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    food_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("standard_food.id", ondelete="SET NULL")
    )
    custom_food_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("user_custom_food.id", ondelete="SET NULL")
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    calorie: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    protein: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    carb: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    fat: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


# ===== 8. system_message（系统消息通知）=====
class SystemMessage(PgBase):
    """系统消息通知。msg_type: remind饮食提醒 / ai AI推送。"""

    __tablename__ = "system_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    msg_type: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
