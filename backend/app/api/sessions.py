"""Session 与 Run API 路由。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import check_quota, get_org_id
from app.schemas.session import (
    RunRequest,
    RunResponse,
    SessionCreate,
    SessionListResponse,
    SessionMessageItem,
    SessionMessagesResponse,
    SessionResponse,
)
from app.services import session as session_service

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    dependencies=[Depends(require_permission("sessions", "write"))],
)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> SessionResponse:
    """创建 Session。"""
    await check_quota(db, org_id, "max_sessions")
    session = await session_service.create_session(db, data)
    return SessionResponse.model_validate(session)


@router.get("", response_model=SessionListResponse, dependencies=[Depends(require_permission("sessions", "read"))])
async def list_sessions(
    agent_name: str | None = Query(None, description="按 Agent 筛选"),
    status: str | None = Query(None, description="按状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> SessionListResponse:
    """获取 Session 列表。"""
    sessions, total = await session_service.list_sessions(
        db, agent_name=agent_name, status=status, limit=limit, offset=offset, org_id=org_id
    )
    return SessionListResponse(
        data=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    dependencies=[Depends(require_permission("sessions", "read"))],
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """获取 Session 详情。"""
    session = await session_service.get_session(db, session_id)
    return SessionResponse.model_validate(session)


@router.delete(
    "/{session_id}",
    dependencies=[Depends(require_permission("sessions", "delete"))],
)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除 Session。"""
    await session_service.delete_session(db, session_id)
    return {"message": "Session 已删除"}


@router.post(
    "/{session_id}/run",
    response_model=None,
    dependencies=[Depends(require_permission("sessions", "execute"))],
)
async def run_session(
    session_id: uuid.UUID,
    data: RunRequest,
    db: AsyncSession = Depends(get_db),
) -> RunResponse | StreamingResponse:
    """发起 Run。

    stream=false 返回 JSON 响应。
    stream=true 返回 SSE 事件流。
    """
    if data.config.stream:
        return StreamingResponse(
            session_service.execute_run_stream(db, session_id, data),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        return await session_service.execute_run(db, session_id, data)


@router.get(
    "/{session_id}/messages",
    response_model=SessionMessagesResponse,
    dependencies=[Depends(require_permission("sessions", "read"))],
)
async def get_session_messages(
    session_id: uuid.UUID,
    search: str | None = Query(None, description="按消息内容关键词搜索"),
    db: AsyncSession = Depends(get_db),
) -> SessionMessagesResponse:
    """获取会话的持久化消息历史，支持关键词搜索。"""
    rows = await session_service.get_session_messages(db, session_id, search=search)
    items = [
        SessionMessageItem(
            id=row.id,
            role=row.role,
            content=row.content or "",
            agent_name=row.agent_name,
            tool_call_id=row.tool_call_id,
            tool_calls=row.tool_calls,
            token_usage=row.token_usage,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return SessionMessagesResponse(
        session_id=str(session_id),
        messages=items,
        total=len(items),
    )


@router.post(
    "/runs/{run_id}/cancel",
    dependencies=[Depends(require_permission("sessions", "execute"))],
)
async def cancel_run(
    run_id: str,
) -> dict[str, Any]:
    """取消正在运行的 Run。"""
    cancelled = session_service.cancel_run(run_id)
    if not cancelled:
        return {"cancelled": False, "message": f"Run '{run_id}' 不存在或已结束"}
    return {"cancelled": True, "message": f"Run '{run_id}' 已取消"}


@router.post(
    "/{session_id}/resume-from-checkpoint",
    response_model=RunResponse,
    dependencies=[Depends(require_permission("sessions", "execute"))],
)
async def resume_from_checkpoint(
    session_id: uuid.UUID,
    run_id: str = Query(..., description="原始 Run ID（用于查找 checkpoint）"),
    data: RunRequest = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """从 Checkpoint 恢复执行。"""
    if data is None:
        data = RunRequest(input="")
    return await session_service.resume_from_checkpoint(db, session_id, run_id, data)
