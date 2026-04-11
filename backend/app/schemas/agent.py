"""Agent 配置请求/响应模型。"""

from __future__ import annotations

from typing import Any

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Agent name 格式：小写字母/数字开头结尾，中间可含连字符，3-64 字符
_AGENT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


class GuardrailsConfig(BaseModel):
    """护栏配置。"""

    input: list[str] = Field(default_factory=list)
    output: list[str] = Field(default_factory=list)
    tool: list[str] = Field(default_factory=list)


class AgentCreate(BaseModel):
    """创建 Agent 请求体。"""

    name: str = Field(..., min_length=3, max_length=64, description="Agent 唯一标识")
    description: str = Field(default="", description="功能描述")
    instructions: str = Field(default="", description="Agent 行为指令")
    model: str | None = Field(default=None, description="LLM 模型标识")
    provider_name: str | None = Field(
        default=None, max_length=64, description="模型厂商名称（对应 ProviderConfig.name）",
    )
    model_settings: dict[str, Any] | None = Field(default=None, description="模型参数")
    tool_groups: list[str] = Field(default_factory=list, description="工具组名称列表")
    handoffs: list[str] = Field(default_factory=list, description="可 Handoff 的目标 Agent")
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig, description="护栏配置")
    approval_mode: str = Field(default="suggest", description="审批模式")
    mcp_servers: list[str] = Field(default_factory=list, description="MCP Server 名称")
    agent_tools: list[str] = Field(default_factory=list, description="作为工具调用的 Agent 名称列表")
    skills: list[str] = Field(default_factory=list, description="已启用 Skill 名称")
    output_type: dict[str, Any] | None = Field(default=None, description="结构化输出 JSON Schema")
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")
    prompt_variables: list[dict[str, Any]] = Field(
        default_factory=list, description="Prompt 模板变量定义列表",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _AGENT_NAME_PATTERN.match(v):
            raise ValueError("名称只能包含小写字母、数字和连字符，且以字母或数字开头结尾，长度 3-64")
        return v

    @field_validator("approval_mode")
    @classmethod
    def validate_approval_mode(cls, v: str) -> str:
        allowed = {"suggest", "auto-edit", "full-auto"}
        if v not in allowed:
            raise ValueError(f"approval_mode 必须是 {allowed} 之一")
        return v


class AgentUpdate(BaseModel):
    """更新 Agent 请求体（PATCH 语义，所有字段可选）。"""

    description: str | None = None
    instructions: str | None = None
    model: str | None = None
    provider_name: str | None = None
    model_settings: dict[str, Any] | None = None
    tool_groups: list[str] | None = None
    handoffs: list[str] | None = None
    guardrails: GuardrailsConfig | None = None
    approval_mode: str | None = None
    mcp_servers: list[str] | None = None
    agent_tools: list[str] | None = None
    skills: list[str] | None = None
    output_type: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    prompt_variables: list[dict[str, Any]] | None = None

    @field_validator("approval_mode")
    @classmethod
    def validate_approval_mode(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"suggest", "auto-edit", "full-auto"}
            if v not in allowed:
                raise ValueError(f"approval_mode 必须是 {allowed} 之一")
        return v


class AgentResponse(BaseModel):
    """Agent 详情响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    description: str
    instructions: str
    model: str | None
    provider_name: str | None
    model_settings: dict[str, Any] | None
    tool_groups: list[str]
    handoffs: list[str]
    guardrails: dict[str, Any]
    approval_mode: str
    mcp_servers: list[str]
    agent_tools: list[str]
    skills: list[str]
    output_type: dict[str, Any] | None
    metadata: dict[str, Any] = Field(alias="metadata_")
    prompt_variables: list[dict[str, Any]]
    org_id: uuid.UUID | None
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    """Agent 列表响应。"""

    data: list[AgentResponse]
    total: int
    limit: int
    offset: int
