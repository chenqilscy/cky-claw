"""监督面板业务逻辑层。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.exceptions import ConflictError, NotFoundError
from app.models.session import SessionRecord
from app.models.token_usage import TokenUsageLog
from app.schemas.supervision import (
    SessionStatus,
    SupervisionActionResponse,
    SupervisionSessionDetail,
    SupervisionSessionItem,
    SupervisionSessionListResponse,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def list_active_sessions(
    db: AsyncSession,
    *,
    agent_name: str | None = None,
    status: str | None = None,
) -> SupervisionSessionListResponse:
    """获取活跃会话列表，附带 Token 统计。

    默认返回 active + paused 状态的会话。可通过 status 参数筛选。
    """
    # 子查询：按 session_id 聚合 token 统计
    token_sub = (
        select(
            TokenUsageLog.session_id,
            func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("token_used"),
            func.count().label("call_count"),
        )
        .group_by(TokenUsageLog.session_id)
        .subquery()
    )

    stmt = (
        select(
            SessionRecord,
            func.coalesce(token_sub.c.token_used, 0).label("token_used"),
            func.coalesce(token_sub.c.call_count, 0).label("call_count"),
        )
        .outerjoin(token_sub, SessionRecord.id == token_sub.c.session_id)
    )

    if status:
        stmt = stmt.where(SessionRecord.status == status)
    else:
        # 默认只返回活跃（active + paused）
        stmt = stmt.where(
            SessionRecord.status.in_([SessionStatus.active.value, SessionStatus.paused.value])
        )

    if agent_name:
        stmt = stmt.where(SessionRecord.agent_name == agent_name)

    stmt = stmt.order_by(SessionRecord.updated_at.desc())

    result = await db.execute(stmt)
    rows = result.all()

    items = [
        SupervisionSessionItem(
            session_id=row[0].id,
            agent_name=row[0].agent_name,
            status=row[0].status,
            title=row[0].title,
            token_used=int(row[1]),
            call_count=int(row[2]),
            created_at=row[0].created_at,
            updated_at=row[0].updated_at,
        )
        for row in rows
    ]

    return SupervisionSessionListResponse(data=items, total=len(items))


async def get_session_detail(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> SupervisionSessionDetail:
    """获取会话详情（含消息历史和 Token 统计）。"""
    # 查询会话
    stmt = select(SessionRecord).where(SessionRecord.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise NotFoundError(f"Session '{session_id}' 不存在")

    # Token 统计
    token_stmt = select(
        func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("token_used"),
        func.count().label("call_count"),
    ).where(TokenUsageLog.session_id == session_id)
    token_row = (await db.execute(token_stmt)).one()

    return SupervisionSessionDetail(
        session_id=session.id,
        agent_name=session.agent_name,
        status=session.status,
        title=session.title,
        token_used=int(token_row[0]),
        call_count=int(token_row[1]),
        created_at=session.created_at,
        updated_at=session.updated_at,
        metadata=session.metadata_,
        messages=[],  # 消息由 Framework SessionBackend 管理，此处留空
    )


async def pause_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    reason: str = "",
) -> SupervisionActionResponse:
    """暂停会话。"""
    session = await _get_and_validate_session(db, session_id, expected_status=SessionStatus.active.value)
    session.status = SessionStatus.paused.value
    await db.commit()
    await db.refresh(session)
    return SupervisionActionResponse(
        session_id=session.id,
        status=session.status,
        message=f"会话已暂停{f'：{reason}' if reason else ''}",
    )


async def resume_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    injected_instructions: str = "",
) -> SupervisionActionResponse:
    """恢复会话。"""
    session = await _get_and_validate_session(db, session_id, expected_status=SessionStatus.paused.value)
    session.status = SessionStatus.active.value
    await db.commit()
    await db.refresh(session)
    return SupervisionActionResponse(
        session_id=session.id,
        status=session.status,
        message="会话已恢复",
    )


async def _get_and_validate_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    expected_status: str,
) -> SessionRecord:
    """获取会话并校验状态。"""
    stmt = select(SessionRecord).where(SessionRecord.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise NotFoundError(f"Session '{session_id}' 不存在")
    if session.status != expected_status:
        raise ConflictError(
            f"会话当前状态为 '{session.status}'，无法执行此操作（需要 '{expected_status}'）"
        )
    return session
