"""Prompt 模板服务 — 渲染预览与验证。"""

from __future__ import annotations

from typing import Any

from ckyclaw_framework.agent.template import (
    TemplateVariable,
    extract_variables,
    render_template,
    validate_template,
)


def preview_prompt(
    instructions: str,
    variables: dict[str, Any],
    definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """渲染 Prompt 模板并返回预览结果。

    Args:
        instructions: 包含 {{variable}} 的模板文本。
        variables: 变量名→值映射。
        definitions: 可选的变量定义列表（来自 AgentConfig.prompt_variables）。

    Returns:
        {"rendered": str, "warnings": list[str]}
    """
    defs = _parse_definitions(definitions) if definitions else None
    result = render_template(instructions, variables, definitions=defs)
    return {"rendered": result.rendered, "warnings": result.warnings}


def validate_prompt(
    instructions: str,
    definitions: list[dict[str, Any]],
) -> dict[str, Any]:
    """验证 Prompt 模板与变量定义的一致性。

    Args:
        instructions: 包含 {{variable}} 的模板文本。
        definitions: 变量定义列表。

    Returns:
        {"valid": bool, "errors": list[str], "warnings": list[str], "referenced_variables": list[str]}
    """
    defs = _parse_definitions(definitions)
    result = validate_template(instructions, defs)
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "referenced_variables": result.referenced_variables,
    }


def extract_prompt_variables(instructions: str) -> list[str]:
    """提取模板中引用的所有变量名。"""
    return extract_variables(instructions)


def _parse_definitions(raw: list[dict[str, Any]]) -> list[TemplateVariable]:
    """将 JSON 字典列表转换为 TemplateVariable 列表。"""
    result: list[TemplateVariable] = []
    for item in raw:
        result.append(TemplateVariable(
            name=item.get("name", ""),
            type=item.get("type", "string"),
            default=item.get("default", ""),
            description=item.get("description", ""),
            required=item.get("required", False),
            options=item.get("options", []),
        ))
    return result
