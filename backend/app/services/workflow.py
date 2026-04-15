"""Workflow 工作流业务逻辑层。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.models.workflow import WorkflowDefinition

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.workflow import WorkflowCreate, WorkflowUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_workflow(db: AsyncSession, data: WorkflowCreate) -> WorkflowDefinition:
    """创建工作流定义。"""
    record = WorkflowDefinition(
        name=data.name,
        description=data.description,
        steps=[s.model_dump() for s in data.steps],
        edges=[e.model_dump() for e in data.edges],
        input_schema=data.input_schema,
        output_keys=data.output_keys,
        timeout=data.timeout,
        guardrail_names=data.guardrail_names,
        metadata_=data.metadata,
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"工作流名称 '{data.name}' 已存在") from None
    await db.refresh(record)
    return record


async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> WorkflowDefinition:
    """获取单个工作流。"""
    stmt = select(WorkflowDefinition).where(
        WorkflowDefinition.id == workflow_id, WorkflowDefinition.is_deleted == False  # noqa: E712
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"工作流 '{workflow_id}' 不存在")
    return record


async def get_workflow_by_name(db: AsyncSession, name: str) -> WorkflowDefinition:
    """按名称获取工作流。"""
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.name == name)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise NotFoundError(f"工作流 '{name}' 不存在")
    return record


async def list_workflows(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    org_id: uuid.UUID | None = None,
) -> tuple[list[WorkflowDefinition], int]:
    """获取工作流列表（分页）。"""
    base = select(WorkflowDefinition).where(WorkflowDefinition.is_deleted == False)  # noqa: E712
    if org_id is not None:
        base = base.where(WorkflowDefinition.org_id == org_id)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = (
        base.order_by(WorkflowDefinition.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).scalars().all()
    return list(rows), total


async def update_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, data: WorkflowUpdate
) -> WorkflowDefinition:
    """更新工作流。"""
    record = await get_workflow(db, workflow_id)
    update_data = data.model_dump(exclude_unset=True)
    if "steps" in update_data and update_data["steps"] is not None:
        update_data["steps"] = [s if isinstance(s, dict) else s.model_dump() for s in update_data["steps"]]
    if "edges" in update_data and update_data["edges"] is not None:
        update_data["edges"] = [e if isinstance(e, dict) else e.model_dump() for e in update_data["edges"]]
    for key, value in update_data.items():
        if key == "metadata":
            record.metadata_ = value
        else:
            setattr(record, key, value)
    record.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> None:
    """软删除工作流。"""
    record = await get_workflow(db, workflow_id)
    record.is_deleted = True
    record.deleted_at = datetime.now(UTC)
    await db.commit()


def validate_workflow_definition(steps: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    """验证工作流定义的拓扑结构。

    返回错误列表。空列表表示验证通过。
    """
    errors: list[str] = []

    # 1. 步骤 ID 唯一性
    step_ids = [s.get("id", "") for s in steps]
    seen: set[str] = set()
    for sid in step_ids:
        if not sid:
            errors.append("存在空步骤 ID")
        elif sid in seen:
            errors.append(f"重复步骤 ID: {sid}")
        seen.add(sid)

    # 2. 边引用有效步骤
    for edge in edges:
        src = edge.get("source_step_id", "")
        tgt = edge.get("target_step_id", "")
        if src not in seen:
            errors.append(f"边引用不存在的源步骤: {src}")
        if tgt not in seen:
            errors.append(f"边引用不存在的目标步骤: {tgt}")

    # 3. 环检测（Kahn 算法）
    if not errors:
        in_degree: dict[str, int] = {sid: 0 for sid in seen}
        for edge in edges:
            tgt = edge.get("target_step_id", "")
            if tgt in in_degree:
                in_degree[tgt] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for edge in edges:
                if edge.get("source_step_id") == node:
                    tgt = edge["target_step_id"]
                    in_degree[tgt] -= 1
                    if in_degree[tgt] == 0:
                        queue.append(tgt)

        if visited < len(seen):
            errors.append("工作流存在循环依赖")

    return errors
