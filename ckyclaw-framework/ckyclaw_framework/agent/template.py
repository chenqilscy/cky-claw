"""Prompt 模板渲染器 — 支持 {{variable}} 语法的安全模板引擎。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 匹配 {{variable_name}} 模式，变量名只允许字母、数字、下划线
_VAR_PATTERN = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")


@dataclass
class TemplateVariable:
    """模板变量定义。"""

    name: str
    """变量名。"""

    type: str = "string"
    """变量类型：string / number / boolean / enum。"""

    default: Any = ""
    """默认值。"""

    description: str = ""
    """变量描述。"""

    required: bool = False
    """是否必填。"""

    options: list[str] = field(default_factory=list)
    """enum 类型的可选值列表。"""


@dataclass
class RenderResult:
    """模板渲染结果。"""

    rendered: str
    """渲染后的文本。"""

    warnings: list[str] = field(default_factory=list)
    """渲染警告列表。"""


@dataclass
class ValidationResult:
    """模板验证结果。"""

    valid: bool
    """是否验证通过。"""

    errors: list[str] = field(default_factory=list)
    """验证错误列表。"""

    warnings: list[str] = field(default_factory=list)
    """验证警告列表。"""

    referenced_variables: list[str] = field(default_factory=list)
    """模板中引用的所有变量名。"""


def _escape_value(value: str) -> str:
    """转义变量值中的 {{ 和 }}，防止递归渲染注入。"""
    return value.replace("{{", "{ {").replace("}}", "} }")


def _coerce_value(value: Any, var_type: str) -> str:
    """将变量值转换为字符串，按类型校验。"""
    if var_type == "number":
        try:
            num = float(value)
            # 整数时不带小数点
            return str(int(num)) if num == int(num) else str(num)
        except (ValueError, TypeError):
            return str(value)
    elif var_type == "boolean":
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value).lower()
    else:
        return str(value)


def extract_variables(template: str) -> list[str]:
    """提取模板中引用的所有变量名（去重保序）。

    Args:
        template: 包含 {{variable}} 占位符的模板文本。

    Returns:
        变量名列表（按首次出现顺序）。
    """
    seen: set[str] = set()
    result: list[str] = []
    for match in _VAR_PATTERN.finditer(template):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def render_template(
    template: str,
    variables: dict[str, Any],
    definitions: list[TemplateVariable] | None = None,
) -> RenderResult:
    """渲染 {{variable}} 模板。

    安全地替换模板中的变量占位符。变量值中的 {{ 和 }} 会被转义，防止递归渲染注入。

    Args:
        template: 包含 {{variable}} 占位符的模板文本。
        variables: 变量名 → 值的映射。
        definitions: 可选的变量定义列表。用于类型转换和默认值填充。

    Returns:
        RenderResult 包含渲染后文本和警告列表。
    """
    warnings: list[str] = []

    # 构建定义索引
    def_map: dict[str, TemplateVariable] = {}
    if definitions:
        for d in definitions:
            def_map[d.name] = d

    # 合并默认值
    merged: dict[str, Any] = {}
    for d in def_map.values():
        if d.default is not None and d.default != "":
            merged[d.name] = d.default
    merged.update(variables)

    def _replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name in merged:
            raw_value = merged[var_name]
            var_def = def_map.get(var_name)
            var_type = var_def.type if var_def else "string"
            coerced = _coerce_value(raw_value, var_type)
            return _escape_value(coerced)
        else:
            warnings.append(f"变量 '{var_name}' 未提供值，替换为空字符串")
            return ""

    rendered = _VAR_PATTERN.sub(_replacer, template)
    return RenderResult(rendered=rendered, warnings=warnings)


def validate_template(
    template: str,
    definitions: list[TemplateVariable],
) -> ValidationResult:
    """验证模板与变量定义的一致性。

    检查模板引用的变量是否在定义列表中，以及必填变量是否有默认值。

    Args:
        template: 包含 {{variable}} 占位符的模板文本。
        definitions: 变量定义列表。

    Returns:
        ValidationResult 包含验证结果。
    """
    errors: list[str] = []
    warnings: list[str] = []

    referenced = extract_variables(template)
    defined_names = {d.name for d in definitions}

    # 模板引用了未定义的变量
    for var in referenced:
        if var not in defined_names:
            warnings.append(f"模板引用变量 '{var}' 未在变量定义列表中")

    # 定义了但模板未引用的变量
    for d in definitions:
        if d.name not in referenced:
            warnings.append(f"变量 '{d.name}' 已定义但模板中未引用")

    # 必填变量检查
    for d in definitions:
        if d.required and (d.default is None or d.default == "") and d.name in referenced:
            warnings.append(f"必填变量 '{d.name}' 无默认值，运行时必须提供")

    # enum 类型检查
    for d in definitions:
        if d.type == "enum" and not d.options:
            errors.append(f"enum 类型变量 '{d.name}' 未定义 options 列表")

    # 变量名格式检查
    for d in definitions:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", d.name):
            errors.append(f"变量名 '{d.name}' 不合法，只允许字母、数字、下划线且不以数字开头")

    valid = len(errors) == 0
    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        referenced_variables=referenced,
    )
