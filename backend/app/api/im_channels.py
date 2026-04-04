"""IM 渠道管理 API + Webhook 接收端点。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.schemas.im_channel import (
    IMChannelCreate,
    IMChannelListResponse,
    IMChannelResponse,
    IMChannelUpdate,
)
from app.services import im_channel as svc

router = APIRouter(prefix="/api/v1/im-channels", tags=["IM 渠道"])


# ── CRUD ──────────────────────────────────────────


@router.get("", response_model=IMChannelListResponse)
async def list_channels(
    channel_type: str | None = None,
    is_enabled: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> IMChannelListResponse:
    """查询 IM 渠道列表。"""
    items, total = await svc.list_channels(
        db, channel_type=channel_type, is_enabled=is_enabled, limit=limit, offset=offset
    )
    return IMChannelListResponse(
        data=[IMChannelResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=IMChannelResponse, status_code=201)
async def create_channel(
    data: IMChannelCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> IMChannelResponse:
    """创建 IM 渠道。"""
    channel = await svc.create_channel(db, data)
    return IMChannelResponse.model_validate(channel)


@router.get("/{channel_id}", response_model=IMChannelResponse)
async def get_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> IMChannelResponse:
    """获取单个 IM 渠道。"""
    channel = await svc.get_channel(db, channel_id)
    if channel is None:
        raise HTTPException(404, "IM channel not found")
    return IMChannelResponse.model_validate(channel)


@router.put("/{channel_id}", response_model=IMChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    data: IMChannelUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> IMChannelResponse:
    """更新 IM 渠道。"""
    channel = await svc.update_channel(db, channel_id, data)
    if channel is None:
        raise HTTPException(404, "IM channel not found")
    return IMChannelResponse.model_validate(channel)


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> None:
    """删除 IM 渠道。"""
    ok = await svc.delete_channel(db, channel_id)
    if not ok:
        raise HTTPException(404, "IM channel not found")


# ── Webhook 接收 ──────────────────────────────────


@router.post("/{channel_id}/webhook")
async def receive_webhook(
    channel_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """接收 IM 平台 Webhook 回调。

    公开端点，通过签名验证安全性。
    """
    channel = await svc.get_channel(db, channel_id)
    if channel is None:
        raise HTTPException(404, "channel not found")
    if not channel.is_enabled:
        raise HTTPException(403, "channel is disabled")

    body = await request.body()

    # 签名验证（如果配置了 webhook_secret）
    if channel.webhook_secret:
        signature = request.headers.get("X-Signature", "") or request.headers.get("x-hub-signature-256", "")
        if not signature:
            raise HTTPException(401, "missing signature header")
        if not svc.verify_webhook_signature(channel.webhook_secret, body, signature):
            raise HTTPException(401, "invalid signature")

    # 解析消息体
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON payload")

    # 路由到绑定的 Agent
    result = await svc.route_message(
        db,
        channel_id,
        sender_id=payload.get("sender_id", payload.get("user_id", "")),
        content=payload.get("content", payload.get("text", payload.get("message", ""))),
    )
    return result
