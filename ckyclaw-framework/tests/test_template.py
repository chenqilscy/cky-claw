"""Prompt 模板渲染器测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.agent.template import (
    RenderResult,
    TemplateVariable,
    ValidationResult,
    extract_variables,
    render_template,
    validate_template,
)


class TestExtractVariables:
    """extract_variables() 测试。"""

    def test_no_variables(self) -> None:
        """无变量的模板返回空列表。"""
        assert extract_variables("Hello world") == []

    def test_single_variable(self) -> None:
        """提取单个变量。"""
        assert extract_variables("Hello {{name}}") == ["name"]

    def test_multiple_variables(self) -> None:
        """提取多个变量。"""
        result = extract_variables("{{greeting}} {{name}}, welcome to {{place}}")
        assert result == ["greeting", "name", "place"]

    def test_duplicate_variables(self) -> None:
        """重复变量去重，保持首次出现顺序。"""
        result = extract_variables("{{a}} {{b}} {{a}} {{c}} {{b}}")
        assert result == ["a", "b", "c"]

    def test_underscore_variable(self) -> None:
        """支持下划线变量名。"""
        assert extract_variables("{{my_var}}") == ["my_var"]

    def test_variable_with_numbers(self) -> None:
        """支持含数字的变量名。"""
        assert extract_variables("{{var1}} {{var_2}}") == ["var1", "var_2"]

    def test_invalid_variable_name_ignored(self) -> None:
        """不合法的变量名（如以数字开头）不被提取。"""
        assert extract_variables("{{1abc}}") == []

    def test_empty_braces_ignored(self) -> None:
        """空双花括号不匹配。"""
        assert extract_variables("{{}}") == []

    def test_nested_braces_ignored(self) -> None:
        """三花括号不匹配内部的双花括号变量。"""
        # {{{var}}} — 外层 {{ 匹配 var，但多余的 } 只是普通字符
        result = extract_variables("{{{var}}}")
        assert result == ["var"]


class TestRenderTemplate:
    """render_template() 测试。"""

    def test_basic_render(self) -> None:
        """基本变量替换。"""
        result = render_template("Hello {{name}}", {"name": "World"})
        assert result.rendered == "Hello World"
        assert result.warnings == []

    def test_multiple_variables(self) -> None:
        """多个变量替换。"""
        result = render_template(
            "{{greeting}} {{name}}!",
            {"greeting": "Hi", "name": "Alice"},
        )
        assert result.rendered == "Hi Alice!"

    def test_missing_variable_empty_string(self) -> None:
        """缺失变量替换为空字符串，并产生警告。"""
        result = render_template("Hello {{name}}", {})
        assert result.rendered == "Hello "
        assert len(result.warnings) == 1
        assert "name" in result.warnings[0]

    def test_default_value_from_definitions(self) -> None:
        """从定义中取默认值。"""
        defs = [TemplateVariable(name="name", default="默认用户")]
        result = render_template("Hello {{name}}", {}, definitions=defs)
        assert result.rendered == "Hello 默认用户"
        assert result.warnings == []

    def test_explicit_value_overrides_default(self) -> None:
        """显式提供的值覆盖默认值。"""
        defs = [TemplateVariable(name="name", default="默认")]
        result = render_template("Hello {{name}}", {"name": "覆盖"}, definitions=defs)
        assert result.rendered == "Hello 覆盖"

    def test_injection_prevention(self) -> None:
        """变量值中的 {{ 被转义，防止递归渲染注入。"""
        result = render_template("Hello {{name}}", {"name": "{{evil}}"})
        assert "{{evil}}" not in result.rendered
        assert "{ {evil} }" in result.rendered

    def test_number_type_coercion(self) -> None:
        """number 类型变量值做数值转换。"""
        defs = [TemplateVariable(name="count", type="number")]
        result = render_template("共 {{count}} 步", {"count": 5}, definitions=defs)
        assert result.rendered == "共 5 步"

    def test_number_float(self) -> None:
        """float 数值保留小数。"""
        defs = [TemplateVariable(name="rate", type="number")]
        result = render_template("Rate: {{rate}}", {"rate": 0.95}, definitions=defs)
        assert result.rendered == "Rate: 0.95"

    def test_boolean_type_coercion(self) -> None:
        """boolean 类型变量值转换为 true/false。"""
        defs = [TemplateVariable(name="strict", type="boolean")]
        result = render_template("Strict: {{strict}}", {"strict": True}, definitions=defs)
        assert result.rendered == "Strict: true"

    def test_no_template_variables(self) -> None:
        """无模板变量的文本原样返回。"""
        result = render_template("Plain text without vars", {"key": "val"})
        assert result.rendered == "Plain text without vars"

    def test_empty_template(self) -> None:
        """空模板返回空字符串。"""
        result = render_template("", {"key": "val"})
        assert result.rendered == ""

    def test_unicode_variable_value(self) -> None:
        """Unicode 字符变量值正常渲染。"""
        result = render_template("你好 {{name}}", {"name": "世界"})
        assert result.rendered == "你好 世界"

    def test_multiline_template(self) -> None:
        """多行模板渲染。"""
        template = "第一行 {{a}}\n第二行 {{b}}\n第三行"
        result = render_template(template, {"a": "值A", "b": "值B"})
        assert result.rendered == "第一行 值A\n第二行 值B\n第三行"

    def test_long_value_within_limit(self) -> None:
        """长变量值（不超限）正常渲染。"""
        long_val = "x" * 5000
        result = render_template("{{content}}", {"content": long_val})
        assert len(result.rendered) == 5000


class TestValidateTemplate:
    """validate_template() 测试。"""

    def test_valid_template(self) -> None:
        """模板和定义完全匹配。"""
        defs = [TemplateVariable(name="name"), TemplateVariable(name="role")]
        result = validate_template("{{name}} is {{role}}", defs)
        assert result.valid is True
        assert result.errors == []
        assert result.referenced_variables == ["name", "role"]

    def test_undefined_variable_warning(self) -> None:
        """模板引用未定义变量产生警告。"""
        defs = [TemplateVariable(name="name")]
        result = validate_template("{{name}} {{unknown}}", defs)
        assert result.valid is True  # 警告不影响 valid
        assert any("unknown" in w for w in result.warnings)

    def test_unused_variable_warning(self) -> None:
        """定义了但模板未引用的变量产生警告。"""
        defs = [TemplateVariable(name="name"), TemplateVariable(name="unused_var")]
        result = validate_template("{{name}}", defs)
        assert any("unused_var" in w for w in result.warnings)

    def test_required_no_default_warning(self) -> None:
        """必填变量无默认值产生警告。"""
        defs = [TemplateVariable(name="key", required=True)]
        result = validate_template("{{key}}", defs)
        assert any("必填" in w for w in result.warnings)

    def test_enum_without_options_error(self) -> None:
        """enum 类型无 options 是错误。"""
        defs = [TemplateVariable(name="mode", type="enum")]
        result = validate_template("{{mode}}", defs)
        assert result.valid is False
        assert any("options" in e for e in result.errors)

    def test_invalid_variable_name_error(self) -> None:
        """非法变量名产生错误。"""
        defs = [TemplateVariable(name="1bad-name")]
        result = validate_template("test", defs)
        assert result.valid is False
        assert any("不合法" in e for e in result.errors)

    def test_empty_template_valid(self) -> None:
        """空模板在无定义时验证通过。"""
        result = validate_template("", [])
        assert result.valid is True

    def test_referenced_variables_list(self) -> None:
        """验证结果包含引用变量列表。"""
        defs = [TemplateVariable(name="a"), TemplateVariable(name="b")]
        result = validate_template("{{a}} {{b}}", defs)
        assert result.referenced_variables == ["a", "b"]


class TestRenderResult:
    """RenderResult 数据类测试。"""

    def test_default_warnings(self) -> None:
        """默认 warnings 为空列表。"""
        r = RenderResult(rendered="test")
        assert r.warnings == []


class TestValidationResult:
    """ValidationResult 数据类测试。"""

    def test_defaults(self) -> None:
        """默认值测试。"""
        r = ValidationResult(valid=True)
        assert r.errors == []
        assert r.warnings == []
        assert r.referenced_variables == []


class TestTemplateVariable:
    """TemplateVariable 数据类测试。"""

    def test_defaults(self) -> None:
        """默认值测试。"""
        v = TemplateVariable(name="test")
        assert v.type == "string"
        assert v.default == ""
        assert v.description == ""
        assert v.required is False
        assert v.options == []

    def test_enum_with_options(self) -> None:
        """enum 类型带 options。"""
        v = TemplateVariable(name="mode", type="enum", options=["fast", "slow"])
        assert v.options == ["fast", "slow"]
