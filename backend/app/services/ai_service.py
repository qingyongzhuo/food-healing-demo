"""AI 对话与每日简报业务服务层。

Phase 3 新增。提供 5 类业务能力：
1. chat_with_assistant：发送咨询问题，携带当日饮食上下文 + 历史对话
2. get_chat_history_by_date：查询单日完整聊天记录
3. list_chat_history：分页查询历史每日对话摘要
4. get_daily_summary：获取单日 AI 简报
5. list_daily_reports：分页查询历史每日 AI 报告
6. generate_daily_summary：触发为用户生成当日营养简报（MQ 消费者调用）
7. trigger_daily_summary_task：异步触发简报生成任务（投递 MQ 或 fallback）

数据访问：
- PG：daily_diet_record + meal_item + standard_food + user_custom_food + user_body_target
- Mongo：ai_chat_history + ai_daily_report（Mongo 未启用时 graceful 降级）
- AI：utils.bailian_client.chat_with_diet_context / chat_text
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select

from app.constants import (
    AI_CHAT_HISTORY_COLLECTION,
    AI_DAILY_REPORT_COLLECTION,
    AI_DAILY_SUMMARY_PROMPT,
)
from app.database import PgSessionLocal, mongo_db
from app.exceptions import BizError
from app.models.pg_orm import (
    DailyDietRecord,
    MealItem,
    StandardFood,
    UserBodyTarget,
    UserCustomFood,
)
from app.models.schemas import ERR_BAILIAN_CHAT, ERR_PARAM_FORMAT
from app.tasks.ai_task import publish_daily_summary_task
from app.utils.bailian_client import chat_with_diet_context, chat_text
from app.utils.logger import logger


# ============================================================
# 1. 发送咨询问题
# ============================================================
async def chat_with_assistant(
    user_id: int,
    content: str,
    query_date: str | None = None,
) -> dict[str, Any]:
    """发送咨询问题，AI 携带当日饮食上下文回答。

    流程：
    1. 解析 query_date（默认当天）
    2. 拉取用户当日饮食数据，拼接上下文字符串
    3. 拉取当日已有聊天记录作为历史
    4. 调百炼 chat_with_diet_context 生成回答
    5. 将 user + assistant 两条消息 append 到 Mongo ai_chat_history

    Args:
        user_id: 当前用户 ID
        content: 用户提问内容
        query_date: 查询日期 YYYY-MM-DD，None 则当天

    Returns:
        {"reply": str, "query_date": str, "saved": bool}
    """
    content = (content or "").strip()
    if not content:
        raise BizError(code=ERR_PARAM_FORMAT, message="提问内容不能为空")
    if len(content) > 500:
        raise BizError(code=ERR_PARAM_FORMAT, message="提问内容不能超过 500 字")

    record_date = query_date or date.today().isoformat()

    # 1. 拉取当日饮食数据 + 拼接上下文
    diet_context = await _build_diet_context(user_id, record_date)

    # 2. 拉取当日已有聊天记录（作为历史，最多取最近 10 条避免 token 超限）
    history_messages = await _load_chat_history(user_id, record_date, limit=10)

    # 3. 调百炼生成回答
    try:
        reply = await chat_with_diet_context(
            user_question=content,
            diet_context=diet_context,
            history_messages=history_messages,
            scene="chat",
        )
    except Exception as exc:
        logger.error("ai_chat_failed", user_id=user_id, error=str(exc))
        raise BizError(
            code=ERR_BAILIAN_CHAT,
            message="AI 服务暂时不可用，请稍后再试",
            http_status=503,
        ) from exc

    if not reply:
        raise BizError(
            code=ERR_BAILIAN_CHAT,
            message="AI 未返回有效回答，请重试",
            http_status=503,
        )

    # 4. 保存对话到 Mongo
    saved = await _append_chat_history(
        user_id=user_id,
        record_date=record_date,
        user_content=content,
        assistant_content=reply,
    )

    logger.info(
        "ai_chat_ok",
        user_id=user_id,
        record_date=record_date,
        question_chars=len(content),
        reply_chars=len(reply),
        saved=saved,
    )

    return {
        "reply": reply,
        "query_date": record_date,
        "saved": saved,
    }


# ============================================================
# 2. 查询单日完整聊天记录
# ============================================================
async def get_chat_history_by_date(
    user_id: int,
    record_date: str | None = None,
) -> dict[str, Any]:
    """查询单日完整聊天记录。

    Args:
        user_id: 当前用户 ID
        record_date: 日期 YYYY-MM-DD，None 则当天

    Returns:
        {
            "user_id": int,
            "record_date": str,
            "chat_list": [{role, content, created_at}],
            "daily_summary": str | None
        }
    """
    record_date = record_date or date.today().isoformat()

    if mongo_db is None:
        return {
            "user_id": user_id,
            "record_date": record_date,
            "chat_list": [],
            "daily_summary": None,
        }

    doc = await mongo_db[AI_CHAT_HISTORY_COLLECTION].find_one(
        {"user_id": user_id, "record_date": record_date},
        projection={"_id": 0},
    )

    if doc is None:
        return {
            "user_id": user_id,
            "record_date": record_date,
            "chat_list": [],
            "daily_summary": None,
        }

    return {
        "user_id": user_id,
        "record_date": record_date,
        "chat_list": doc.get("chat_list", []),
        "daily_summary": doc.get("daily_summary"),
    }


# ============================================================
# 3. 分页查询历史每日对话摘要
# ============================================================
async def list_chat_history(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询历史每日对话摘要（一日一条）。

    按日期倒序，每项含：日期、消息条数、最后一条消息预览、当日简报摘要。

    Args:
        user_id: 当前用户 ID
        page: 页码（从 1 起）
        page_size: 每页条数 [1, 100]

    Returns:
        {items, total, page, page_size}
    """
    if mongo_db is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    skip = (page - 1) * page_size
    coll = mongo_db[AI_CHAT_HISTORY_COLLECTION]

    # 总日数
    total = await coll.count_documents({"user_id": user_id})

    # 分页查询（按日期倒序）
    cursor = (
        coll.find({"user_id": user_id}, projection={"_id": 0})
        .sort("record_date", -1)
        .skip(skip)
        .limit(page_size)
    )

    items: list[dict[str, Any]] = []
    async for doc in cursor:
        chat_list = doc.get("chat_list", [])
        last_content = ""
        if chat_list:
            last_msg = chat_list[-1]
            last_content = (last_msg.get("content") or "")[:100]

        items.append({
            "record_date": doc.get("record_date", ""),
            "message_count": len(chat_list),
            "daily_summary": doc.get("daily_summary"),
            "last_content": last_content or None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# 4. 获取单日 AI 简报
# ============================================================
async def get_daily_summary(
    user_id: int,
    report_date: str | None = None,
) -> dict[str, Any]:
    """获取单日 AI 营养简报。

    Args:
        user_id: 当前用户 ID
        report_date: 报告日期 YYYY-MM-DD，None 则当天

    Returns:
        {found, user_id, report_date, full_content, create_at}
    """
    report_date = report_date or date.today().isoformat()

    if mongo_db is None:
        return {
            "found": False,
            "user_id": user_id,
            "report_date": report_date,
            "full_content": None,
            "create_at": None,
        }

    doc = await mongo_db[AI_DAILY_REPORT_COLLECTION].find_one(
        {"user_id": user_id, "report_date": report_date},
        projection={"_id": 0},
    )

    if doc is None:
        return {
            "found": False,
            "user_id": user_id,
            "report_date": report_date,
            "full_content": None,
            "create_at": None,
        }

    create_at = doc.get("create_at")
    return {
        "found": True,
        "user_id": user_id,
        "report_date": report_date,
        "full_content": doc.get("full_content", ""),
        "create_at": create_at if isinstance(create_at, str) else (
            create_at.isoformat() if create_at else None
        ),
    }


# ============================================================
# 5. 分页查询历史每日 AI 报告
# ============================================================
async def list_daily_reports(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询历史每日 AI 报告（按日期倒序）。

    Args:
        user_id: 当前用户 ID
        page: 页码（从 1 起）
        page_size: 每页条数 [1, 100]

    Returns:
        {items, total, page, page_size}
    """
    if mongo_db is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    skip = (page - 1) * page_size
    coll = mongo_db[AI_DAILY_REPORT_COLLECTION]

    total = await coll.count_documents({"user_id": user_id})

    cursor = (
        coll.find({"user_id": user_id}, projection={"_id": 0})
        .sort("report_date", -1)
        .skip(skip)
        .limit(page_size)
    )

    items: list[dict[str, Any]] = []
    async for doc in cursor:
        create_at = doc.get("create_at")
        items.append({
            "report_date": doc.get("report_date", ""),
            "full_content": doc.get("full_content", ""),
            "create_at": create_at if isinstance(create_at, str) else (
                create_at.isoformat() if create_at else None
            ),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# 6. 生成单日 AI 简报（MQ 消费者调用）
# ============================================================
async def generate_daily_summary(user_id: int, report_date: str) -> str:
    """为用户生成单日 AI 营养简报（MQ 消费者调用）。

    流程：
    1. 拉取用户当日饮食数据（diet_record + meal_items）
    2. 拉取用户营养目标
    3. 用 AI_DAILY_SUMMARY_PROMPT 模板拼接 prompt
    4. 调百炼 chat_text 生成 Markdown 简报
    5. 写入 Mongo ai_daily_report 集合（upsert）
    6. 同时把简报摘要写回 ai_chat_history.daily_summary

    Args:
        user_id: 用户 ID
        report_date: 报告日期 YYYY-MM-DD

    Returns:
        生成的简报文本（Markdown）。无饮食数据时返回空字符串。
    """
    # 1. 拉取当日饮食数据
    diet_data = await _load_diet_data(user_id, report_date)

    # 无饮食数据则不生成简报
    if diet_data["record"] is None:
        logger.info(
            "daily_summary_skip_no_data",
            user_id=user_id,
            report_date=report_date,
        )
        return ""

    # 2. 拉取营养目标
    target = await _load_user_target(user_id)

    # 3. 拼接 prompt
    record = diet_data["record"]
    meal_details = _format_meal_details(diet_data["meal_items"])
    prompt = AI_DAILY_SUMMARY_PROMPT.format(
        user_id=user_id,
        report_date=report_date,
        target_calorie=target.get("daily_calorie", 2000),
        target_protein=target.get("target_protein", 60),
        target_carb=target.get("target_carb", 250),
        target_fat=target.get("target_fat", 65),
        total_calorie=record.get("total_calorie", 0),
        total_protein=record.get("total_protein", 0),
        total_carb=record.get("total_carb", 0),
        total_fat=record.get("total_fat", 0),
        meal_details=meal_details,
    )

    # 4. 调百炼生成简报
    try:
        # 用 report 场景（max 模型，30s 超时，更适合长文本生成）
        # 覆盖 max_tokens=1500：route 默认 300 太小，4 段 Markdown 会被截断
        full_content = await chat_text(
            scene="report",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1500,
        )
    except Exception as exc:
        logger.error(
            "daily_summary_ai_failed",
            user_id=user_id,
            report_date=report_date,
            error=str(exc),
        )
        raise

    if not full_content:
        logger.warning(
            "daily_summary_ai_empty",
            user_id=user_id,
            report_date=report_date,
        )
        return ""

    # 5. 写入 Mongo ai_daily_report（upsert：同 user_id + report_date 覆盖）
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    if mongo_db is not None:
        try:
            await mongo_db[AI_DAILY_REPORT_COLLECTION].update_one(
                {"user_id": user_id, "report_date": report_date},
                {
                    "$set": {
                        "user_id": user_id,
                        "report_date": report_date,
                        "full_content": full_content,
                        "create_at": now_iso,
                    }
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(
                "daily_summary_save_failed",
                user_id=user_id,
                report_date=report_date,
                error=str(exc),
            )

        # 6. 把简报摘要（取前 200 字）写回 ai_chat_history.daily_summary
        try:
            summary_short = full_content[:200]
            await mongo_db[AI_CHAT_HISTORY_COLLECTION].update_one(
                {"user_id": user_id, "record_date": report_date},
                {
                    "$set": {"daily_summary": summary_short},
                    "$setOnInsert": {
                        "chat_list": [],
                        "created_at": now_iso,
                    },
                },
                upsert=True,
            )
        except Exception as exc:
            logger.warning(
                "daily_summary_chat_history_sync_failed",
                user_id=user_id,
                report_date=report_date,
                error=str(exc),
            )

    logger.info(
        "daily_summary_generated",
        user_id=user_id,
        report_date=report_date,
        content_chars=len(full_content),
    )
    return full_content


# ============================================================
# 7. 异步触发简报生成任务（投递 MQ 或 fallback 同步执行）
# ============================================================
async def trigger_daily_summary_task(
    user_id: int,
    report_date: str | None = None,
) -> dict[str, Any]:
    """触发为用户生成当日简报任务。

    优先投递 MQ（异步），MQ 未就绪时 fallback 直接调 generate_daily_summary（同步）。

    Args:
        user_id: 用户 ID
        report_date: 报告日期 YYYY-MM-DD，None 则当天

    Returns:
        {"queued": bool, "report_date": str}
        queued=True 表示已投递 MQ；False 表示同步执行或失败
    """
    report_date = report_date or date.today().isoformat()

    # 优先投递 MQ
    queued = await publish_daily_summary_task(user_id, report_date)
    if queued:
        logger.info(
            "daily_summary_queued",
            user_id=user_id,
            report_date=report_date,
        )
        return {"queued": True, "report_date": report_date}

    # MQ 未就绪，fallback 同步执行
    logger.info(
        "daily_summary_fallback_sync",
        user_id=user_id,
        report_date=report_date,
    )
    try:
        await generate_daily_summary(user_id, report_date)
    except Exception as exc:
        logger.error(
            "daily_summary_fallback_failed",
            user_id=user_id,
            report_date=report_date,
            error=str(exc),
        )
        raise BizError(
            code=ERR_BAILIAN_CHAT,
            message="简报生成失败，请稍后再试",
            http_status=503,
        ) from exc

    return {"queued": False, "report_date": report_date}


# ============================================================
# 内部工具
# ============================================================
async def _build_diet_context(user_id: int, record_date: str) -> str:
    """拼接用户当日饮食上下文字符串（供 AI 参考）。

    无饮食数据时返回空字符串（让 AI 引导用户先记录）。
    """
    diet_data = await _load_diet_data(user_id, record_date)
    record = diet_data["record"]
    if record is None:
        return ""

    meal_items = diet_data["meal_items"]
    meal_text = _format_meal_details(meal_items)

    return (
        f"日期：{record_date}\n"
        f"总热量：{record.get('total_calorie', 0)} kcal\n"
        f"蛋白质：{record.get('total_protein', 0)}g / "
        f"碳水：{record.get('total_carb', 0)}g / "
        f"脂肪：{record.get('total_fat', 0)}g\n"
        f"餐次明细：\n{meal_text}"
    )


async def _load_diet_data(user_id: int, record_date: str) -> dict[str, Any]:
    """加载用户当日饮食数据（record + meal_items）。

    Args:
        user_id: 用户 ID
        record_date: 日期 YYYY-MM-DD

    Returns:
        {"record": dict | None, "meal_items": list[dict]}
        record None 表示当日无饮食记录
    """
    try:
        parsed_date = date.fromisoformat(record_date)
    except (ValueError, TypeError):
        raise BizError(
            code=ERR_PARAM_FORMAT,
            message=f"日期格式错误：{record_date}，需 YYYY-MM-DD",
        )

    async with PgSessionLocal() as session:
        # 查当日总记录
        stmt = select(DailyDietRecord).where(
            DailyDietRecord.user_id == user_id,
            DailyDietRecord.record_date == parsed_date,
        )
        record = (await session.execute(stmt)).scalar_one_or_none()

        if record is None:
            return {"record": None, "meal_items": []}

        record_dict = {
            "id": record.id,
            "total_calorie": int(record.total_calorie or 0),
            "total_protein": float(record.total_protein or 0),
            "total_carb": float(record.total_carb or 0),
            "total_fat": float(record.total_fat or 0),
        }

        # 查当日所有餐次明细（按 create_time 排序，餐次顺序在 Python 侧修正）
        meal_stmt = (
            select(MealItem)
            .where(MealItem.diet_record_id == record.id)
            .order_by(MealItem.create_time)
        )
        meal_rows = (await session.execute(meal_stmt)).scalars().all()
        # 餐次按字母排序会得到 breakfast<dinner<lunch<snack（错误），
        # 这里按真实时段排序：breakfast<lunch<dinner<snack
        _meal_order = {"breakfast": 1, "lunch": 2, "dinner": 3, "snack": 4}
        meal_rows.sort(key=lambda m: _meal_order.get(m.meal_type, 5))

        # 批量查关联食物名（避免 N+1）
        food_ids = [m.food_id for m in meal_rows if m.food_id]
        custom_food_ids = [m.custom_food_id for m in meal_rows if m.custom_food_id]

        food_name_map: dict[int, str] = {}
        if food_ids:
            food_result = await session.execute(
                select(StandardFood.id, StandardFood.food_name).where(
                    StandardFood.id.in_(food_ids)
                )
            )
            food_name_map = {row[0]: row[1] for row in food_result.all()}

        custom_food_name_map: dict[int, str] = {}
        if custom_food_ids:
            custom_result = await session.execute(
                select(UserCustomFood.id, UserCustomFood.food_name).where(
                    UserCustomFood.id.in_(custom_food_ids)
                )
            )
            custom_food_name_map = {row[0]: row[1] for row in custom_result.all()}

        meal_items = []
        for m in meal_rows:
            name = (
                food_name_map.get(m.food_id)
                or custom_food_name_map.get(m.custom_food_id)
                or "未知食物"
            )
            meal_items.append({
                "meal_type": m.meal_type,
                "food_name": name,
                "weight": int(m.weight or 0),
                "calorie": int(m.calorie or 0),
                "protein": float(m.protein or 0),
                "carb": float(m.carb or 0),
                "fat": float(m.fat or 0),
            })

    return {"record": record_dict, "meal_items": meal_items}


def _format_meal_details(meal_items: list[dict[str, Any]]) -> str:
    """把餐次明细格式化为 AI 可读的文本。"""
    if not meal_items:
        return "（当日无饮食记录）"

    meal_type_map = {
        "breakfast": "早餐",
        "lunch": "午餐",
        "dinner": "晚餐",
        "snack": "零食",
    }

    lines: list[str] = []
    for item in meal_items:
        meal_label = meal_type_map.get(item.get("meal_type", ""), item.get("meal_type", ""))
        lines.append(
            f"- {meal_label}：{item.get('food_name', '未知')} "
            f"{item.get('weight', 0)}g / {item.get('calorie', 0)}kcal "
            f"(蛋白 {item.get('protein', 0)}g / 碳水 {item.get('carb', 0)}g / "
            f"脂肪 {item.get('fat', 0)}g)"
        )
    return "\n".join(lines)


async def _load_user_target(user_id: int) -> dict[str, Any]:
    """加载用户营养目标（无则返回默认值）。"""
    async with PgSessionLocal() as session:
        stmt = select(UserBodyTarget).where(UserBodyTarget.user_id == user_id)
        target = (await session.execute(stmt)).scalar_one_or_none()

        if target is None:
            return {
                "daily_calorie": 2000,
                "target_protein": 60,
                "target_carb": 250,
                "target_fat": 65,
            }

        return {
            "daily_calorie": int(target.daily_calorie or 2000),
            "target_protein": int(target.target_protein or 60),
            "target_carb": int(target.target_carb or 250),
            "target_fat": int(target.target_fat or 65),
        }


async def _load_chat_history(
    user_id: int,
    record_date: str,
    limit: int = 10,
) -> list[dict[str, str]]:
    """从 Mongo 加载当日已有聊天记录，转为 OpenAI 消息格式。

    Args:
        user_id: 用户 ID
        record_date: 日期 YYYY-MM-DD
        limit: 最多取最近 N 条（避免 token 超限）

    Returns:
        [{"role": "user"|"assistant", "content": "..."}, ...]
    """
    if mongo_db is None:
        return []

    doc = await mongo_db[AI_CHAT_HISTORY_COLLECTION].find_one(
        {"user_id": user_id, "record_date": record_date},
        projection={"chat_list": {"$slice": -limit}},
    )

    if doc is None:
        return []

    chat_list = doc.get("chat_list", [])
    return [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in chat_list
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


async def _append_chat_history(
    user_id: int,
    record_date: str,
    user_content: str,
    assistant_content: str,
) -> bool:
    """把 user + assistant 两条消息 append 到 Mongo ai_chat_history。

    使用 upsert：当日无文档则创建，有则 append。
    返回 False 表示 Mongo 未启用，调用方应记录 saved=False。
    """
    if mongo_db is None:
        return False

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    new_messages = [
        {"role": "user", "content": user_content, "created_at": now_iso},
        {"role": "assistant", "content": assistant_content, "created_at": now_iso},
    ]

    try:
        await mongo_db[AI_CHAT_HISTORY_COLLECTION].update_one(
            {"user_id": user_id, "record_date": record_date},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "record_date": record_date,
                    "created_at": now_iso,
                },
                "$push": {"chat_list": {"$each": new_messages}},
            },
            upsert=True,
        )
        return True
    except Exception as exc:
        logger.error(
            "append_chat_history_failed",
            user_id=user_id,
            record_date=record_date,
            error=str(exc),
        )
        return False
