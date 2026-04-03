"""MCP Server 配置 CRUD 服务。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_api_key, encrypt_api_key
from app.core.exceptions import NotFoundError, ValidationError
from app.models.mcp_server import MCPServerConfig
from app.schemas.mcp_server import MCPServerCreate, MCPServerUpdate, VALID_TRANSPORT_TYPES

logger = logging.getLogger(__name__)

# auth_config 中需要加密的字段名
_ENCRYPT_FIELDS = {"api_key", "secret", "token", "password", "client_secret", "refresh_token"}


def _encrypt_auth_config(auth: dict | None) -> dict | None:
    """加密 auth_config 中的敏感字段。"""
    if not auth:
        return auth
    encrypted = {}
    for key, value in auth.items():
        if key.lower() in _ENCRYPT_FIELDS and isinstance(value, str) and value and value != "***":
            encrypted[key] = encrypt_api_key(value)
        else:
            encrypted[key] = value
    return encrypted


def _decrypt_auth_config(auth: dict | None) -> dict | None:
    """解密 auth_config 中的敏感字段。"""
    if not auth:
        return auth
    decrypted = {}
    for key, value in auth.items():
        if key.lower() in _ENCRYPT_FIELDS and isinstance(value, str) and value:
            try:
                decrypted[key] = decrypt_api_key(value)
            except Exception:
                decrypted[key] = value  # 解密失败保留原值
        else:
            decrypted[key] = value
    return decrypted


async def create_mcp_server(db: AsyncSession, data: MCPServerCreate) -> MCPServerConfig:
    """创建 MCP Server 配置。"""
    # 检查名称唯一性
    stmt = select(MCPServerConfig).where(MCPServerConfig.name == data.name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ValidationError(f"MCP Server '{data.name}' 已存在")

    record = MCPServerConfig(
        name=data.name,
        description=data.description,
        transport_type=data.transport_type,
        command=data.command,
        url=data.url,
        env=data.env,
        auth_config=_encrypt_auth_config(data.auth_config),
        is_enabled=data.is_enabled,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_mcp_server(db: AsyncSession, server_id: uuid.UUID) -> MCPServerConfig:
    """获取 MCP Server 配置。"""
    stmt = select(MCPServerConfig).where(MCPServerConfig.id == server_id)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"MCP Server '{server_id}' 不存在")
    return record


async def get_mcp_server_by_name(db: AsyncSession, name: str) -> MCPServerConfig | None:
    """按名称获取 MCP Server 配置。"""
    stmt = select(MCPServerConfig).where(MCPServerConfig.name == name)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_mcp_servers(
    db: AsyncSession,
    *,
    transport_type: str | None = None,
    is_enabled: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MCPServerConfig], int]:
    """获取 MCP Server 列表（分页 + 过滤）。"""
    base = select(MCPServerConfig)
    if transport_type:
        base = base.where(MCPServerConfig.transport_type == transport_type)
    if is_enabled is not None:
        base = base.where(MCPServerConfig.is_enabled == is_enabled)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(MCPServerConfig.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def update_mcp_server(
    db: AsyncSession,
    server_id: uuid.UUID,
    data: MCPServerUpdate,
) -> MCPServerConfig:
    """更新 MCP Server 配置（PATCH 语义）。"""
    record = await get_mcp_server(db, server_id)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "auth_config":
            value = _encrypt_auth_config(value)
        if key == "transport_type" and value is not None:
            if value not in VALID_TRANSPORT_TYPES:
                raise ValidationError(f"transport_type 必须是 {VALID_TRANSPORT_TYPES} 之一")
        setattr(record, key, value)

    await db.commit()
    await db.refresh(record)
    return record


async def delete_mcp_server(db: AsyncSession, server_id: uuid.UUID) -> None:
    """删除 MCP Server 配置。"""
    record = await get_mcp_server(db, server_id)
    await db.delete(record)
    await db.commit()


async def get_mcp_servers_by_names(
    db: AsyncSession,
    names: list[str],
) -> list[MCPServerConfig]:
    """根据名称列表批量获取已启用的 MCP Server 配置。"""
    if not names:
        return []
    stmt = select(MCPServerConfig).where(
        MCPServerConfig.name.in_(names),
        MCPServerConfig.is_enabled == True,  # noqa: E712
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def test_mcp_connection(
    db: AsyncSession,
    server_id: uuid.UUID,
) -> dict:
    """测试 MCP Server 连接：连接 → list_tools → 返回工具列表或错误。

    Returns:
        dict with keys: success (bool), tools (list), error (str | None), duration_ms (int)
    """
    import time
    from contextlib import AsyncExitStack

    record = await get_mcp_server(db, server_id)

    # 解密 auth_config 中的敏感字段作为 headers
    headers: dict[str, str] = {}
    decrypted_auth = _decrypt_auth_config(record.auth_config)
    if decrypted_auth:
        for key, value in decrypted_auth.items():
            if isinstance(value, str) and value:
                headers[key] = value

    # 解密 env
    env: dict[str, str] = {}
    if record.env:
        for key, value in record.env.items():
            env[key] = str(value) if value else ""

    start_time = time.monotonic()

    try:
        from ckyclaw_framework.mcp.connection import connect_and_discover
        from ckyclaw_framework.mcp.server import MCPServerConfig as FrameworkMCPConfig

        fw_config = FrameworkMCPConfig(
            name=record.name,
            transport=record.transport_type,
            command=record.command,
            url=record.url,
            env=env,
            headers=headers,
            connect_timeout=15.0,
            tool_call_timeout=15.0,
        )

        async with AsyncExitStack() as stack:
            tools = await connect_and_discover(stack, fw_config)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        tool_infos = []
        for tool in tools:
            tool_infos.append({
                "name": tool.name,
                "description": tool.description,
                "parameters_schema": tool.parameters_schema or {},
            })

        return {
            "success": True,
            "tools": tool_infos,
            "error": None,
            "duration_ms": duration_ms,
        }
    except ImportError:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return {
            "success": False,
            "tools": [],
            "error": "MCP SDK 未安装。请运行: pip install 'ckyclaw-framework[mcp]'",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.exception("MCP Server '%s' 连接测试失败", record.name)
        return {
            "success": False,
            "tools": [],
            "error": str(e),
            "duration_ms": duration_ms,
        }
