"""IM 渠道管理 API + Webhook 接收端点。"""

from __future__ import annotations

from typing import Any

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.tenant import check_quota, get_org_id
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
    _: dict[str, Any] = Depends(require_admin),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> IMChannelListResponse:
    """查询 IM 渠道列表。"""
    items, total = await svc.list_channels(
        db, channel_type=channel_type, is_enabled=is_enabled, limit=limit, offset=offset, org_id=org_id
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
    _: dict[str, Any] = Depends(require_admin),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> IMChannelResponse:
    """创建 IM 渠道。"""
    await check_quota(db, org_id, "max_im_channels")
    channel = await svc.create_channel(db, data)
    return IMChannelResponse.model_validate(channel)


@router.get("/{channel_id}", response_model=IMChannelResponse)
async def get_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> IMChannelResponse:
    """获取单个 IM 渠道。"""
    channel = await svc.get_channel(db, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="IM 渠道不存在")
    return IMChannelResponse.model_validate(channel)


@router.put("/{channel_id}", response_model=IMChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    data: IMChannelUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> IMChannelResponse:
    """更新 IM 渠道。"""
    channel = await svc.update_channel(db, channel_id, data)
    if channel is None:
        raise HTTPException(status_code=404, detail="IM 渠道不存在")
    return IMChannelResponse.model_validate(channel)


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: dict[str, Any] = Depends(require_admin),
) -> None:
    """删除 IM 渠道。"""
    ok = await svc.delete_channel(db, channel_id)
    if not ok:
        raise HTTPException(status_code=404, detail="IM 渠道不存在")


# ── Webhook 接收 ──────────────────────────────────


@router.post("/{channel_id}/webhook")
async def receive_webhook(
    channel_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """接收 IM 平台 Webhook 回调。

    公开端点，通过签名验证安全性。
    """
    channel = await svc.get_channel(db, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="IM 渠道不存在")
    if not channel.is_enabled:
        raise HTTPException(status_code=403, detail="IM 渠道已禁用")

    body = await request.body()

    # 签名验证（如果配置了 webhook_secret）
    if channel.webhook_secret:
        signature = request.headers.get("X-Signature", "") or request.headers.get("x-hub-signature-256", "")
        if not signature:
            raise HTTPException(status_code=401, detail="缺少签名头")
        if not svc.verify_webhook_signature(channel.webhook_secret, body, signature):
            raise HTTPException(status_code=401, detail="签名验证失败")

    # 解析消息体
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON 请求体")

    # 路由到绑定的 Agent
    result = await svc.route_message(
        db,
        channel_id,
        sender_id=payload.get("sender_id", payload.get("user_id", "")),
        content=payload.get("content", payload.get("text", payload.get("message", ""))),
    )
    return result
