"""Debug Session 业务逻辑层。

管理调试会话的 CRUD + 内存中 DebugController 的生命周期。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentConfig
from app.models.debug_session import DebugSession

from ckyclaw_framework.debug.controller import DebugController, DebugMode

logger = logging.getLogger(__name__)

# 内存管理：活跃调试会话的 DebugController 实例
# key = debug_session_id (UUID), value = DebugController
_active_controllers: dict[uuid.UUID, DebugController] = {}

# 最大同时调试会话数
MAX_ACTIVE_SESSIONS = 5


async def list_debug_sessions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    state: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DebugSession], int]:
    """获取调试会话列表。"""
    base = select(DebugSession)
    if user_id is not None:
        base = base.where(DebugSession.user_id == user_id)
    if state is not None:
        base = base.where(DebugSession.state == state)

    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(DebugSession.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def get_debug_session(db: AsyncSession, session_id: uuid.UUID) -> DebugSession | None:
    """获取调试会话详情。"""
    stmt = select(DebugSession).where(DebugSession.id == session_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_debug_session(
    db: AsyncSession,
    *,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    input_message: str,
    mode: str = "step_turn",
) -> DebugSession:
    """创建调试会话 + 初始化内存 DebugController。

    Raises:
        ValueError: 活跃调试会话超过上限。
        ValueError: Agent 不存在。
    """
    # 限流检查
    active_count = len([
        sid for sid, ctrl in _active_controllers.items()
        if ctrl.state.value in ("idle", "running", "paused")
    ])
    if active_count >= MAX_ACTIVE_SESSIONS:
        raise ValueError(f"活跃调试会话已达上限（{MAX_ACTIVE_SESSIONS}）")

    # 验证 Agent 存在
    agent_stmt = select(AgentConfig).where(AgentConfig.id == agent_id)
    agent = (await db.execute(agent_stmt)).scalar_one_or_none()
    if agent is None:
        raise ValueError(f"Agent {agent_id} 不存在")

    mode_enum = DebugMode(mode)

    session = DebugSession(
        agent_id=agent_id,
        agent_name=agent.name,
        user_id=user_id,
        state="idle",
        mode=mode,
        input_message=input_message,
        current_turn=0,
        current_agent_name=agent.name,
        pause_context={},
        token_usage={},
    )
    db.add(session)
    await db.flush()

    # 创建内存 DebugController
    controller = DebugController(mode=mode_enum)
    _active_controllers[session.id] = controller

    await db.commit()
    await db.refresh(session)
    return session


def get_controller(session_id: uuid.UUID) -> DebugController | None:
    """获取内存中的 DebugController 实例。"""
    return _active_controllers.get(session_id)


async def update_session_state(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    state: str | None = None,
    current_turn: int | None = None,
    current_agent_name: str | None = None,
    pause_context: dict[str, Any] | None = None,
    token_usage: dict[str, Any] | None = None,
    result: str | None = None,
    error: str | None = None,
    finished: bool = False,
) -> DebugSession | None:
    """更新调试会话状态。"""
    session = await get_debug_session(db, session_id)
    if session is None:
        return None

    if state is not None:
        session.state = state
    if current_turn is not None:
        session.current_turn = current_turn
    if current_agent_name is not None:
        session.current_agent_name = current_agent_name
    if pause_context is not None:
        session.pause_context = pause_context
    if token_usage is not None:
        session.token_usage = token_usage
    if result is not None:
        session.result = result
    if error is not None:
        session.error = error
    if finished:
        session.finished_at = datetime.now(timezone.utc)

    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def cleanup_session(session_id: uuid.UUID) -> None:
    """清理调试会话的内存资源。"""
    _active_controllers.pop(session_id, None)
