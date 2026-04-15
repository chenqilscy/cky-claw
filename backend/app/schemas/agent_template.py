"""AgentTemplate 请求/响应模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class AgentTemplateCreate(BaseModel):
    """创建 Agent 模板请求体。"""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*$", description="模板唯一名称")
    display_name: str = Field(..., min_length=1, max_length=128, description="显示名称")
    description: str = Field("", max_length=5000, description="模板描述")
    category: str = Field("general", max_length=32, description="分类")
    icon: str = Field("RobotOutlined", max_length=64, description="图标名称")
    config: dict[str, Any] = Field(default_factory=dict, description="Agent 配置 JSON")
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")


class AgentTemplateUpdate(BaseModel):
    """更新 Agent 模板请求体。"""

    display_name: str | None = Field(None, min_length=1, max_length=128, description="显示名称")
    description: str | None = Field(None, max_length=5000, description="模板描述")
    category: str | None = Field(None, max_length=32, description="分类")
    icon: str | None = Field(None, max_length=64, description="图标名称")
    config: dict[str, Any] | None = Field(None, description="Agent 配置 JSON")
    metadata: dict[str, Any] | None = Field(None, description="自定义元数据")


class CreateAgentFromTemplate(BaseModel):
    """从模板创建 Agent 请求体。"""

    agent_name: str = Field(..., min_length=1, max_length=64, description="新 Agent 名称")
    overrides: dict[str, Any] = Field(default_factory=dict, description="覆盖模板中的配置项")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class AgentTemplateResponse(BaseModel):
    """Agent 模板响应。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str
    category: str
    icon: str
    config: dict[str, Any]
    is_builtin: bool
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class AgentTemplateListResponse(BaseModel):
    """Agent 模板列表响应。"""

    data: list[AgentTemplateResponse]
    total: int
    limit: int = 20
    offset: int = 0
