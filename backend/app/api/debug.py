"""Debug Session REST API — Agent 交互式调试。"""

from __future__ import annotations
import uuid

import contextlib
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.core.deps import get_current_user, get_db, require_permission
from app.schemas.debug import (
    DebugContextResponse,
    DebugSessionCreate,
    DebugSessionListResponse,
    DebugSessionResponse,
)
from app.services import debug as debug_service

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.debug_session import DebugSession
    from app.models.user import User
    from kasaya.debug.controller import DebugEvent

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


@router.get(
    "/sessions",
    response_model=DebugSessionListResponse,
    dependencies=[Depends(require_permission("debug", "read"))],
)
async def list_debug_sessions(
    state: str | None = Query(None, description="按状态筛选"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebugSessionListResponse:
    """获取调试会话列表。"""
    sessions, total = await debug_service.list_debug_sessions(
        db, user_id=user.id, state=state, limit=limit, offset=offset,
    )
    return DebugSessionListResponse(
        items=[DebugSessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.post(
    "/sessions",
    response_model=DebugSessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("debug", "write"))],
)
async def create_debug_session(
    body: DebugSessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebugSessionResponse:
    """创建调试会话。"""
    try:
        session = await debug_service.create_debug_session(
            db,
            agent_id=body.agent_id,
            user_id=user.id,
            input_message=body.input_message,
            mode=body.mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return DebugSessionResponse.model_validate(session)


@router.get(
    "/sessions/{session_id}",
    response_model=DebugSessionResponse,
    dependencies=[Depends(require_permission("debug", "read"))],
)
async def get_debug_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebugSessionResponse:
    """获取调试会话详情。"""
    session = await debug_service.get_debug_session(db, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    return DebugSessionResponse.model_validate(session)


@router.post(
    "/sessions/{session_id}/step",
    response_model=DebugSessionResponse,
    dependencies=[Depends(require_permission("debug", "write"))],
)
async def step_debug_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebugSessionResponse:
    """单步执行 — 执行到下一个检查点后暂停。"""
    session = await debug_service.get_debug_session(db, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    controller = debug_service.get_controller(session_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="调试会话未激活")

    await controller.step()

    # 同步状态到数据库
    updated = await _sync_controller_state(db, session_id, controller)
    if updated is None:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    return DebugSessionResponse.model_validate(updated)


@router.post(
    "/sessions/{session_id}/continue",
    response_model=DebugSessionResponse,
    dependencies=[Depends(require_permission("debug", "write"))],
)
async def continue_debug_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebugSessionResponse:
    """继续执行 — 运行到结束或下一个断点。"""
    session = await debug_service.get_debug_session(db, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    controller = debug_service.get_controller(session_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="调试会话未激活")

    await controller.resume()

    updated = await _sync_controller_state(db, session_id, controller)
    if updated is None:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    return DebugSessionResponse.model_validate(updated)


@router.post(
    "/sessions/{session_id}/stop",
    response_model=DebugSessionResponse,
    dependencies=[Depends(require_permission("debug", "write"))],
)
async def stop_debug_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebugSessionResponse:
    """终止调试会话。"""
    session = await debug_service.get_debug_session(db, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    controller = debug_service.get_controller(session_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="调试会话未激活")

    await controller.stop()
    await debug_service.cleanup_session(session_id)

    session = await debug_service.update_session_state(
        db, session_id, state="failed", finished=True, error="用户终止",
    )
    if session is None:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    return DebugSessionResponse.model_validate(session)


@router.get(
    "/sessions/{session_id}/context",
    response_model=DebugContextResponse,
    dependencies=[Depends(require_permission("debug", "read"))],
)
async def get_debug_context(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DebugContextResponse:
    """获取当前暂停点的上下文详情。"""
    session = await debug_service.get_debug_session(db, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="调试会话不存在")
    controller = debug_service.get_controller(session_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="调试会话未激活")

    ctx = controller.pause_context
    if ctx is None:
        raise HTTPException(status_code=400, detail="调试会话未处于暂停状态")

    return DebugContextResponse(
        turn=ctx.turn,
        agent_name=ctx.agent_name,
        reason=ctx.reason,
        recent_messages=ctx.recent_messages,
        last_llm_response=ctx.last_llm_response,
        last_tool_calls=ctx.last_tool_calls,
        token_usage=ctx.token_usage,
        paused_at=ctx.paused_at,
    )


@router.websocket("/sessions/{session_id}/ws")
async def debug_websocket(
    websocket: WebSocket,
    session_id: uuid.UUID,
) -> None:
    """调试 WebSocket — 双向通信通道。

    服务端推送事件（暂停/工具结果/LLM 流），客户端发送控制指令。
    """
    controller = debug_service.get_controller(session_id)
    if controller is None:
        await websocket.close(code=4004, reason="调试会话未激活")
        return

    await websocket.accept()

    # 注册事件回调
    async def on_event(event: DebugEvent) -> None:
        """将 DebugEvent 推送给 WebSocket 客户端。"""
        with contextlib.suppress(Exception):
            await websocket.send_json({
                "type": event.type.value,
                "data": event.data,
                "timestamp": event.timestamp,
            })

    controller._on_event = on_event

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "step":
                await controller.step()
            elif action == "continue":
                await controller.resume()
            elif action == "stop":
                await controller.stop()
                break
    except WebSocketDisconnect:
        pass
    finally:
        controller._on_event = None


async def _sync_controller_state(
    db: AsyncSession,
    session_id: uuid.UUID,
    controller: object,
) -> DebugSession | None:
    """将 DebugController 的状态同步到数据库。"""
    ctx = getattr(controller, "pause_context", None)
    pause_data = {}
    current_turn = 0
    current_agent = ""
    token_data: dict = {}

    if ctx is not None:
        pause_data = {
            "turn": ctx.turn,
            "agent_name": ctx.agent_name,
            "reason": ctx.reason,
            "paused_at": ctx.paused_at,
        }
        current_turn = ctx.turn
        current_agent = ctx.agent_name
        token_data = ctx.token_usage

    raw_state = getattr(controller, "state", "idle")
    state_str = raw_state.value if hasattr(raw_state, "value") else str(raw_state)

    return await debug_service.update_session_state(
        db,
        session_id,
        state=state_str,
        current_turn=current_turn,
        current_agent_name=current_agent,
        pause_context=pause_data,
        token_usage=token_data,
    )
