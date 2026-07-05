"""消息通知业务服务层。

Phase 5 新增。提供 5 类业务能力：
1. 分页查询消息列表（支持按 msg_type 筛选，附带未读数）
2. 单条消息标记已读
3. 全部消息标记已读
4. 清空当前用户全部消息
5. 新增消息（供 MQ 消费者调用，写入 system_message 表）

数据访问约定（与项目其他 service 一致）：
- ORM 模型见 app.models.pg_orm.SystemMessage
- session 通过 app.database.PgSessionLocal 取
- 错误码见 app.models.schemas

注意：当前阶段 system_message 表尚未实际建表，
故所有「直接读写 DB」的代码段以 pass + TODO 注释占位，
待表结构落地后用真实查询替换。返回结构组装、参数校验、
权限校验等不依赖 DB 的逻辑已写完整，可直接复用。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update, func, delete

from app.constants import MSG_READ_READ, MSG_READ_UNREAD, MSG_TYPES
from app.database import PgSessionLocal
from app.exceptions import BizError
from app.models.pg_orm import SystemMessage
from app.models.schemas import ERR_NOT_FOUND
from app.utils.logger import logger


# ============================================================
# 1. 分页查询消息列表
# ============================================================
async def list_messages(
    user_id: int,
    msg_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询当前用户的消息列表。

    Args:
        user_id: 当前登录用户 ID
        msg_type: 消息类型筛选，None 表示全部
        page: 页码（从 1 起）
        page_size: 每页条数

    Returns:
        {
            items: [...],
            total: int,
            page, page_size,
            unread_count: int  # 当前用户未读总数（不分类型）
        }
    """
    if msg_type is not None and msg_type not in MSG_TYPES:
        raise BizError(
            code=10006,
            message=f"msg_type 必须为 {MSG_TYPES} 之一或留空",
        )

    # TODO(DB): 待 system_message 表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         # 主查询：当前用户消息，按类型筛选，按 create_time 倒序分页
    #         stmt = select(SystemMessage).where(SystemMessage.user_id == user_id)
    #         if msg_type:
    #             stmt = stmt.where(SystemMessage.msg_type == msg_type)
    #         # 总条数
    #         count_stmt = select(func.count()).select_from(SystemMessage).where(
    #             SystemMessage.user_id == user_id
    #         )
    #         if msg_type:
    #             count_stmt = count_stmt.where(SystemMessage.msg_type == msg_type)
    #         total = (await session.execute(count_stmt)).scalar_one()
    #         # 分页
    #         stmt = stmt.order_by(SystemMessage.create_time.desc()) \
    #             .offset((page - 1) * page_size).limit(page_size)
    #         rows = (await session.execute(stmt)).scalars().all()
    #         items = [_message_to_dict(r) for r in rows]
    #         # 未读数（不分类型）
    #         unread_stmt = select(func.count()).select_from(SystemMessage).where(
    #             SystemMessage.user_id == user_id,
    #             SystemMessage.is_read == MSG_READ_UNREAD,
    #         )
    #         unread_count = (await session.execute(unread_stmt)).scalar_one()
    #         return {
    #             "items": items,
    #             "total": total,
    #             "page": page,
    #             "page_size": page_size,
    #             "unread_count": unread_count,
    #         }
    pass
    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
        "unread_count": 0,
    }


# ============================================================
# 2. 单条消息标记已读
# ============================================================
async def mark_message_read(user_id: int, msg_id: int) -> dict[str, Any]:
    """单条消息标记已读。

    权限：通过 user_id 间接校验归属，找不到/无权访问均抛 NOT_FOUND
    （避免泄露存在性）。

    Returns:
        {"id": msg_id, "is_read": 1}
    """
    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         stmt = select(SystemMessage).where(
    #             SystemMessage.id == msg_id,
    #             SystemMessage.user_id == user_id,
    #         )
    #         msg = (await session.execute(stmt)).scalar_one_or_none()
    #         if msg is None:
    #             raise BizError(
    #                 code=ERR_NOT_FOUND,
    #                 message="消息不存在或无权操作",
    #                 http_status=404,
    #             )
    #         if msg.is_read == MSG_READ_READ:
    #             # 已读幂等，直接返回
    #             return {"id": msg_id, "is_read": MSG_READ_READ}
    #         msg.is_read = MSG_READ_READ
    #         await session.commit()
    #         return {"id": msg_id, "is_read": MSG_READ_READ}
    pass
    return {"id": msg_id, "is_read": MSG_READ_READ}


# ============================================================
# 3. 全部消息标记已读
# ============================================================
async def mark_all_read(user_id: int) -> dict[str, Any]:
    """当前用户全部消息标记已读（仅更新未读的，避免全表锁）。

    Returns:
        {"updated_count": int}  实际更新的条数
    """
    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         stmt = (
    #             update(SystemMessage)
    #             .where(
    #                 SystemMessage.user_id == user_id,
    #                 SystemMessage.is_read == MSG_READ_UNREAD,
    #             )
    #             .values(is_read=MSG_READ_READ)
    #         )
    #         result = await session.execute(stmt)
    #         await session.commit()
    #         updated = result.rowcount or 0
    #         return {"updated_count": updated}
    pass
    return {"updated_count": 0}


# ============================================================
# 4. 清空当前用户全部消息
# ============================================================
async def clear_all_messages(user_id: int) -> dict[str, Any]:
    """清空当前用户全部消息（物理删除）。

    Returns:
        {"deleted_count": int}
    """
    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         stmt = delete(SystemMessage).where(SystemMessage.user_id == user_id)
    #         result = await session.execute(stmt)
    #         await session.commit()
    #         deleted = result.rowcount or 0
    #         logger.info("messages_cleared", user_id=user_id, deleted=deleted)
    #         return {"deleted_count": deleted}
    pass
    return {"deleted_count": 0}


# ============================================================
# 5. 新增消息（供 MQ 消费者调用）
# ============================================================
async def create_message(
    user_id: int,
    msg_type: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    """新增一条系统消息，返回新建条目。

    供 MQ 消费者（tasks/message_task.py）调用，
    收到推送消息后写入 system_message 表。
    也可被定时任务 / AI 主动推送场景直接同步调用。

    Args:
        user_id: 目标用户 ID
        msg_type: 消息类型（remind / ai）
        title: 标题（≤100 字符）
        content: 正文（≤2000 字符）

    Returns:
        新建消息 dict（与 MessageItem 字段对齐）
    """
    if msg_type not in MSG_TYPES:
        raise BizError(
            code=10006,
            message=f"msg_type 必须为 {MSG_TYPES} 之一",
        )

    # TODO(DB): 待表落地后实现，预期逻辑：
    #     async with PgSessionLocal() as session:
    #         msg = SystemMessage(
    #             user_id=user_id,
    #             msg_type=msg_type,
    #             title=title,
    #             content=content,
    #             is_read=MSG_READ_UNREAD,
    #         )
    #         session.add(msg)
    #         await session.commit()
    #         await session.refresh(msg)
    #         logger.info(
    #             "message_created",
    #             msg_id=msg.id,
    #             user_id=user_id,
    #             msg_type=msg_type,
    #         )
    #         return _message_to_dict(msg)
    pass
    return {
        "id": 0,
        "msg_type": msg_type,
        "title": title,
        "content": content,
        "is_read": MSG_READ_UNREAD,
        "create_time": "",
    }


# ============================================================
# 内部工具
# ============================================================
def _message_to_dict(msg: SystemMessage) -> dict[str, Any]:
    """ORM → dict（与 schemas.MessageItem 字段对齐）。

    create_time 序列化为 ISO 字符串，前端 dayjs / Date 可直接解析。
    """
    return {
        "id": msg.id,
        "msg_type": msg.msg_type,
        "title": msg.title,
        "content": msg.content,
        "is_read": int(msg.is_read),
        "create_time": msg.create_time.isoformat() if msg.create_time else "",
    }
