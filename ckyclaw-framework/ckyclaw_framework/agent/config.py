"""AgentConfig — YAML/dict → Agent 配置解析。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentConfig:
    """从 YAML 或字典加载的 Agent 配置。"""

    name: str
    description: str = ""
    instructions: str = ""
    model: str | None = None
    model_settings: dict[str, Any] | None = None
    tool_groups: list[str] | None = None
    handoffs: list[str] | None = None
