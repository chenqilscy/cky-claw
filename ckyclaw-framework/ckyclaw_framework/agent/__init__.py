"""Agent 定义与加载。"""

from __future__ import annotations

from ckyclaw_framework.agent.agent import Agent, InstructionsType
from ckyclaw_framework.agent.template import (
    RenderResult,
    TemplateVariable,
    ValidationResult,
    extract_variables,
    render_template,
    validate_template,
)

__all__ = [
    "Agent",
    "InstructionsType",
    "RenderResult",
    "TemplateVariable",
    "ValidationResult",
    "extract_variables",
    "render_template",
    "validate_template",
]
