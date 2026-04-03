"""MCP Server 配置管理 API。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.models.user import User
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerListResponse,
    MCPServerResponse,
    MCPServerUpdate,
)
from app.services import mcp_server as mcp_service

router = APIRouter(prefix="/api/v1/mcp/servers", tags=["MCP Servers"])


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create_mcp_server(
    data: MCPServerCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> MCPServerResponse:
    """创建 MCP Server 配置。"""
    record = await mcp_service.create_mcp_server(db, data)
    return MCPServerResponse.model_validate(record)


@router.get("", response_model=MCPServerListResponse)
async def list_mcp_servers(
    transport_type: str | None = Query(default=None, description="传输类型过滤"),
    is_enabled: bool | None = Query(default=None, description="启用状态过滤"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MCPServerListResponse:
    """获取 MCP Server 列表。"""
    items, total = await mcp_service.list_mcp_servers(
        db, transport_type=transport_type, is_enabled=is_enabled, limit=limit, offset=offset,
    )
    return MCPServerListResponse(
        items=[MCPServerResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MCPServerResponse:
    """获取 MCP Server 详情。"""
    record = await mcp_service.get_mcp_server(db, server_id)
    return MCPServerResponse.model_validate(record)


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: uuid.UUID,
    data: MCPServerUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> MCPServerResponse:
    """更新 MCP Server 配置。"""
    record = await mcp_service.update_mcp_server(db, server_id, data)
    return MCPServerResponse.model_validate(record)


@router.delete("/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> None:
    """删除 MCP Server 配置。"""
    await mcp_service.delete_mcp_server(db, server_id)
