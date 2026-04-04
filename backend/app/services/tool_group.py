"""Tool Group 配置业务逻辑层。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.tool_group import ToolGroupConfig
from app.schemas.tool_group import ToolGroupCreate, ToolGroupUpdate

logger = logging.getLogger(__name__)


async def list_tool_groups(
    db: AsyncSession,
    *,
    is_enabled: bool | None = None,
    org_id: uuid.UUID | None = None,
) -> tuple[list[ToolGroupConfig], int]:
    """获取工具组列表。"""
    base = select(ToolGroupConfig).where(ToolGroupConfig.is_deleted == False)  # noqa: E712
    if org_id is not None:
        base = base.where(ToolGroupConfig.org_id == org_id)
    if is_enabled is not None:
        base = base.where(ToolGroupConfig.is_enabled == is_enabled)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(ToolGroupConfig.created_at.desc())
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_tool_group_by_name(db: AsyncSession, name: str) -> ToolGroupConfig:
    """按 name 获取工具组，不存在则 404。"""
    stmt = select(ToolGroupConfig).where(
        ToolGroupConfig.name == name, ToolGroupConfig.is_deleted == False  # noqa: E712
    )
    tg = (await db.execute(stmt)).scalar_one_or_none()
    if tg is None:
        raise NotFoundError(f"工具组 '{name}' 不存在")
    return tg


async def create_tool_group(db: AsyncSession, data: ToolGroupCreate) -> ToolGroupConfig:
    """创建工具组配置。名称冲突返回 409。"""
    exists_stmt = select(ToolGroupConfig.id).where(ToolGroupConfig.name == data.name)
    existing = (await db.execute(exists_stmt)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"工具组名称 '{data.name}' 已存在")

    tg = ToolGroupConfig(
        name=data.name,
        description=data.description,
        tools=[t.model_dump() for t in data.tools],
        source="custom",
    )
    db.add(tg)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"工具组名称 '{data.name}' 已存在")

    await db.commit()
    await db.refresh(tg)
    return tg


async def update_tool_group(
    db: AsyncSession, name: str, data: ToolGroupUpdate
) -> ToolGroupConfig:
    """更新工具组配置（PATCH 语义）。"""
    tg = await get_tool_group_by_name(db, name)

    if data.description is not None:
        tg.description = data.description
    if data.tools is not None:
        tg.tools = [t.model_dump() for t in data.tools]
    if data.is_enabled is not None:
        tg.is_enabled = data.is_enabled

    tg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tg)
    return tg


async def delete_tool_group(db: AsyncSession, name: str) -> None:
    """软删除工具组配置。"""
    tg = await get_tool_group_by_name(db, name)
    tg.is_deleted = True
    tg.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ---------------------------------------------------------------------------
# Hosted Tool Group Seed（启动时同步内置工具组到数据库）
# ---------------------------------------------------------------------------

# 内置工具组定义
_HOSTED_TOOL_GROUPS: list[dict[str, object]] = [
    {
        "name": "web-search",
        "description": "网络搜索与页面抓取",
        "tools": [
            {"name": "web_search", "description": "搜索互联网并返回相关结果摘要。"},
            {"name": "fetch_webpage", "description": "抓取指定 URL 的网页内容并返回纯文本。"},
        ],
    },
    {
        "name": "code-executor",
        "description": "代码执行（Python/Shell 沙箱）",
        "tools": [
            {"name": "execute_python", "description": "在沙箱中执行 Python 代码并返回输出。"},
            {"name": "execute_shell", "description": "在沙箱中执行 Shell 命令并返回输出。"},
        ],
    },
    {
        "name": "file-ops",
        "description": "文件读写与目录操作",
        "tools": [
            {"name": "file_read", "description": "读取文件内容。路径限制在工作目录内。"},
            {"name": "file_write", "description": "写入内容到文件。路径限制在工作目录内。"},
            {"name": "file_list", "description": "列出目录内容。路径限制在工作目录内。"},
        ],
    },
    {
        "name": "http",
        "description": "HTTP 请求工具",
        "tools": [
            {"name": "http_request", "description": "发送 HTTP 请求并返回响应。"},
        ],
    },
    {
        "name": "database",
        "description": "只读 SQL 查询",
        "tools": [
            {"name": "database_query", "description": "执行只读 SQL 查询并返回结果。"},
        ],
    },
]


async def seed_hosted_tool_groups(db: AsyncSession) -> int:
    """同步内置工具组到数据库。已存在的跳过，不覆盖用户修改。

    Returns:
        新创建的工具组数量。
    """
    created = 0
    for group_def in _HOSTED_TOOL_GROUPS:
        name = str(group_def["name"])
        stmt = select(ToolGroupConfig.id).where(ToolGroupConfig.name == name)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            continue

        tg = ToolGroupConfig(
            name=name,
            description=str(group_def["description"]),
            tools=group_def["tools"],
            source="hosted",
        )
        db.add(tg)
        created += 1

    if created > 0:
        await db.commit()
        logger.info("已创建 %d 个内置工具组", created)

    return created
