"""Workflow — 工作流定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kasaya.workflow.step import Step


@dataclass
class Edge:
    """DAG 边 — 表示步骤间的数据流方向。"""

    id: str
    source_step_id: str
    target_step_id: str


@dataclass
class Workflow:
    """工作流定义。"""

    name: str
    description: str = ""
    steps: list[Step] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_keys: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout: float | None = None
    guardrail_names: list[str] = field(default_factory=list)
