"""多租户隔离依赖与配额管理。"""

from __future__ import annotations


import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.organization import Organization
from app.models.user import User


async def get_org_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID | None:
    """从当前用户提取 org_id，用于租户隔离过滤。

    admin 若未绑定组织则返回 None（全局视角）。
    """
    return user.org_id


async def get_org_id_required(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """强制要求用户绑定组织，否则 403。"""
    if user.org_id is None and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NO_ORG", "message": "用户未绑定组织，无法访问租户资源"},
        )
    # admin 无 org_id 时返回特殊的 None（通过 get_org_id 处理）
    if user.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NO_ORG", "message": "用户未绑定组织"},
        )
    return user.org_id


# ---------------------------------------------------------------------------
# 配额定义
# ---------------------------------------------------------------------------

# 默认配额限制（当 Organization.quota 中无对应键时使用）
DEFAULT_QUOTA = {
    "max_agents": 50,
    "max_sessions": 500,
    "max_teams": 20,
    "max_workflows": 30,
    "max_skills": 50,
    "max_tool_groups": 30,
    "max_guardrails": 50,
    "max_mcp_servers": 20,
    "max_memories": 1000,
    "max_im_channels": 10,
    "max_scheduled_tasks": 20,
}

# 配额键到计数表的映射
_QUOTA_TABLE_MAP: dict[str, str] = {
    "max_agents": "agent_configs",
    "max_sessions": "sessions",
    "max_teams": "team_configs",
    "max_workflows": "workflow_definitions",
    "max_skills": "skills",
    "max_tool_groups": "tool_group_configs",
    "max_guardrails": "guardrail_rules",
    "max_mcp_servers": "mcp_servers",
    "max_memories": "memory_entries",
    "max_im_channels": "im_channels",
    "max_scheduled_tasks": "scheduled_tasks",
}


async def check_quota(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    resource_key: str,
) -> None:
    """检查创建资源是否超出组织配额。

    Args:
        db: 数据库会话
        org_id: 组织 ID，为 None 时跳过检查（admin 全局模式）
        resource_key: 配额键名，如 'max_agents'

    Raises:
        HTTPException: 超出配额时返回 429
    """
    if org_id is None:
        return  # admin 全局模式不受配额限制

    if resource_key not in _QUOTA_TABLE_MAP:
        return  # 未定义的配额键不检查

    # 获取组织配额设置
    stmt = select(Organization.quota).where(
        Organization.id == org_id,
        Organization.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    org_quota = result.scalar_one_or_none()
    if org_quota is None:
        return  # 组织不存在时跳过

    limit = org_quota.get(resource_key, DEFAULT_QUOTA.get(resource_key))
    if limit is None or limit <= 0:
        return  # 无限制或未设置

    # 统计当前数量
    table_name = _QUOTA_TABLE_MAP[resource_key]

    # 使用原生 SQL 统计，因为不同表的 soft delete 列不同
    from sqlalchemy import text as sa_text

    count_result = await db.execute(
        sa_text(
            f"SELECT COUNT(*) FROM {table_name} "  # noqa: S608
            f"WHERE org_id = :org_id "
            f"AND (is_deleted = false OR is_deleted IS NULL)"
        ),
        {"org_id": str(org_id)},
    )
    current_count = count_result.scalar_one()

    if current_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "QUOTA_EXCEEDED",
                "message": f"已达配额上限：{resource_key}={limit}，当前已有 {current_count} 个",
                "quota_key": resource_key,
                "limit": limit,
                "current": current_count,
            },
        )
