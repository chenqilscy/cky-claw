"""Agent 管理 API 路由。"""

from __future__ import annotations

import json
import uuid

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.tenant import check_quota, get_org_id
from app.schemas.agent import AgentCreate, AgentListResponse, AgentResponse, AgentUpdate
from app.services import agent as agent_service

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse, dependencies=[Depends(require_permission("agents", "read"))])
async def list_agents(
    search: str | None = Query(None, description="按名称/描述模糊搜索"),
    limit: int = Query(20, ge=1, le=100, description="分页大小"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AgentListResponse:
    """获取 Agent 列表。"""
    agents, total = await agent_service.list_agents(db, search=search, limit=limit, offset=offset, org_id=org_id)
    return AgentListResponse(
        data=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=AgentResponse, status_code=201, dependencies=[Depends(require_permission("agents", "write"))])
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID | None = Depends(get_org_id),
) -> AgentResponse:
    """创建 Agent。"""
    await check_quota(db, org_id, "max_agents")
    agent = await agent_service.create_agent(db, data)
    return AgentResponse.model_validate(agent)


@router.get("/{name}", response_model=AgentResponse, dependencies=[Depends(require_permission("agents", "read"))])
async def get_agent(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """获取 Agent 详情。"""
    agent = await agent_service.get_agent_by_name(db, name)
    return AgentResponse.model_validate(agent)


@router.put("/{name}", response_model=AgentResponse, dependencies=[Depends(require_permission("agents", "write"))])
async def update_agent(
    name: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """更新 Agent（PATCH 语义）。"""
    agent = await agent_service.update_agent(db, name, data)
    return AgentResponse.model_validate(agent)


@router.delete("/{name}", dependencies=[Depends(require_permission("agents", "delete"))])
async def delete_agent(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """删除 Agent（软删除）。"""
    await agent_service.delete_agent(db, name)
    return {"message": "Agent deleted"}


# ── 导出/导入 ──────────────────────────────────────────

_EXPORT_FIELDS = [
    "name", "description", "instructions", "model", "provider_name",
    "model_settings", "tool_groups", "handoffs", "guardrails",
    "approval_mode", "mcp_servers", "agent_tools", "skills",
    "output_type", "metadata",
]


@router.get("/{name}/export", dependencies=[Depends(require_permission("agents", "read"))])
async def export_agent(
    name: str,
    format: str = Query("yaml", description="导出格式：yaml / json"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """导出 Agent 配置为 YAML 或 JSON。"""
    agent = await agent_service.get_agent_by_name(db, name)
    agent_data = AgentResponse.model_validate(agent)
    export_dict = {k: v for k, v in agent_data.model_dump().items() if k in _EXPORT_FIELDS}

    if format == "json":
        content = json.dumps(export_dict, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{name}.json"'},
        )
    else:
        content = yaml.dump(export_dict, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return Response(
            content=content,
            media_type="application/x-yaml",
            headers={"Content-Disposition": f'attachment; filename="{name}.yaml"'},
        )


@router.post("/import", response_model=AgentResponse, status_code=201, dependencies=[Depends(require_permission("agents", "write"))])
async def import_agent(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """从 YAML/JSON 文件导入创建 Agent。"""
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"文件编码必须为 UTF-8: {exc}") from exc

    filename = file.filename or ""
    try:
        if filename.endswith((".yaml", ".yml")):
            data_dict = yaml.safe_load(text)
        else:
            data_dict = json.loads(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"配置文件解析失败: {exc}") from exc

    if not isinstance(data_dict, dict):
        raise HTTPException(status_code=400, detail="配置文件内容必须为 JSON/YAML 对象")

    try:
        agent_create = AgentCreate(**data_dict)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    agent = await agent_service.create_agent(db, agent_create)
    return AgentResponse.model_validate(agent)
