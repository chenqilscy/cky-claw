"""Mailbox API 路由 — Agent 间通信。"""

from __future__ import annotations
import uuid

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.core.deps import require_permission
from app.schemas.mailbox import (
    MailboxListResponse,
    MailboxMessageResponse,
    MailboxSendRequest,
)
from app.services import mailbox as mailbox_service

if TYPE_CHECKING:

    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/mailbox", tags=["mailbox"])


@router.post(
    "/send",
    response_model=MailboxMessageResponse,
    status_code=201,
    dependencies=[Depends(require_permission("mailbox", "write"))],
)
async def send_message(
    data: MailboxSendRequest,
    db: AsyncSession = Depends(get_db),
) -> MailboxMessageResponse:
    """发送 Agent 间消息。"""
    record = await mailbox_service.send_message(db, data)
    await db.commit()
    return MailboxMessageResponse.model_validate(record)


@router.get(
    "/receive",
    response_model=MailboxListResponse,
    dependencies=[Depends(require_permission("mailbox", "read"))],
)
async def receive_messages(
    agent_name: str = Query(..., description="接收方 Agent 名称"),
    run_id: str | None = Query(None, description="按 Run ID 过滤"),
    unread_only: bool = Query(True, description="仅未读消息"),
    db: AsyncSession = Depends(get_db),
) -> MailboxListResponse:
    """接收指定 Agent 的消息。"""
    records = await mailbox_service.receive_messages(
        db, agent_name, run_id=run_id, unread_only=unread_only,
    )
    return MailboxListResponse(
        data=[MailboxMessageResponse.model_validate(r) for r in records],
        total=len(records),
    )


@router.post(
    "/{message_id}/read",
    dependencies=[Depends(require_permission("mailbox", "write"))],
)
async def mark_read(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """标记消息为已读。"""
    await mailbox_service.mark_read(db, message_id)
    await db.commit()
    return {"message": "已标记为已读"}


@router.get(
    "/conversation",
    response_model=MailboxListResponse,
    dependencies=[Depends(require_permission("mailbox", "read"))],
)
async def get_conversation(
    run_id: str = Query(..., description="运行 ID"),
    agent_a: str = Query(..., description="Agent A 名称"),
    agent_b: str = Query(..., description="Agent B 名称"),
    db: AsyncSession = Depends(get_db),
) -> MailboxListResponse:
    """获取两个 Agent 之间的对话历史。"""
    records = await mailbox_service.get_conversation(db, run_id, agent_a, agent_b)
    return MailboxListResponse(
        data=[MailboxMessageResponse.model_validate(r) for r in records],
        total=len(records),
    )


@router.delete(
    "/runs/{run_id}",
    dependencies=[Depends(require_permission("mailbox", "delete"))],
)
async def delete_run_messages(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """删除指定 Run 的所有消息。"""
    count = await mailbox_service.delete_run_messages(db, run_id)
    await db.commit()
    return {"deleted": count}
