"""IM 渠道业务逻辑。"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.im_channel import IMChannel
from app.schemas.im_channel import IMChannelCreate, IMChannelUpdate

logger = logging.getLogger(__name__)


async def list_channels(
    db: AsyncSession,
    *,
    channel_type: str | None = None,
    is_enabled: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[IMChannel], int]:
    """查询 IM 渠道列表。"""
    q = select(IMChannel).where(IMChannel.is_deleted == False)  # noqa: E712

    if org_id is not None:
        q = q.where(IMChannel.org_id == org_id)

    if channel_type is not None:
        q = q.where(IMChannel.channel_type == channel_type)
    if is_enabled is not None:
        q = q.where(IMChannel.is_enabled == is_enabled)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(q.order_by(IMChannel.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def create_channel(db: AsyncSession, data: IMChannelCreate) -> IMChannel:
    """创建 IM 渠道。"""
    channel = IMChannel(
        name=data.name,
        description=data.description,
        channel_type=data.channel_type,
        webhook_url=data.webhook_url,
        webhook_secret=data.webhook_secret,
        app_config=data.app_config,
        agent_id=data.agent_id,
        is_enabled=data.is_enabled,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


async def get_channel(db: AsyncSession, channel_id: uuid.UUID) -> IMChannel | None:
    """获取单个 IM 渠道。"""
    stmt = select(IMChannel).where(
        IMChannel.id == channel_id, IMChannel.is_deleted == False  # noqa: E712
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def update_channel(db: AsyncSession, channel_id: uuid.UUID, data: IMChannelUpdate) -> IMChannel | None:
    """更新 IM 渠道。"""
    channel = await get_channel(db, channel_id)
    if channel is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(channel, field, value)
    await db.commit()
    await db.refresh(channel)
    return channel


async def delete_channel(db: AsyncSession, channel_id: uuid.UUID) -> bool:
    """软删除 IM 渠道。"""
    channel = await get_channel(db, channel_id)
    if channel is None:
        return False
    channel.is_deleted = True
    channel.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return True


def verify_webhook_signature(
    secret: str,
    payload_body: bytes,
    signature: str,
    *,
    algorithm: str = "sha256",
) -> bool:
    """验证 Webhook 签名。

    支持 HMAC-SHA256，适用于企业微信/钉钉/Slack 等。
    """
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        getattr(hashlib, algorithm),
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def route_message(
    db: AsyncSession,
    channel_id: uuid.UUID,
    sender_id: str,
    content: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """路由 IM 消息到绑定的 Agent。

    MVP 阶段：记录消息并返回确认，实际 Agent 调用在后续迭代实现。
    """
    channel = await db.get(IMChannel, channel_id)
    if channel is None:
        return {"status": "error", "message": "IM 渠道不存在"}
    if not channel.is_enabled:
        return {"status": "error", "message": "IM 渠道已禁用"}
    if channel.agent_id is None:
        return {"status": "error", "message": "该渠道未绑定 Agent"}

    logger.info(
        "IM message routed: channel=%s agent=%s sender=%s",
        channel.name,
        channel.agent_id,
        sender_id,
    )

    # MVP: 返回路由确认，实际 Agent 执行将在 Runner 集成后启用
    return {
        "status": "accepted",
        "channel_id": str(channel_id),
        "agent_id": str(channel.agent_id),
        "sender_id": sender_id,
    }
