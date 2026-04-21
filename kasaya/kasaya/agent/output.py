"""结构化输出定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentOutput:
    """Agent 结构化输出容器。"""

    value: Any
    """输出值（可为 Pydantic BaseModel 实例或原始字符串）"""

    output_type: type | None = None
    """输出类型"""
