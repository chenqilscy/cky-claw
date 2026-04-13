"""Agent 定义与加载。"""

from __future__ import annotations

from ckyclaw_framework.agent.agent import Agent, InstructionsType
from ckyclaw_framework.agent.response_style import (
    RESPONSE_STYLES,
    get_response_style_prompt,
)
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
    "RESPONSE_STYLES",
    "RenderResult",
    "TemplateVariable",
    "ValidationResult",
    "extract_variables",
    "get_response_style_prompt",
    "render_template",
    "validate_template",
]
