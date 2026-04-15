"""RegexGuardrail 扩展测试 — 覆盖 as_tool_before_fn / case_sensitive / keyword-only 等路径。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.guardrails.regex_guardrail import RegexGuardrail

# ═══════════════════════════════════════════════════════════════════
# case_sensitive 模式
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrailCaseSensitive:

    @pytest.mark.asyncio
    async def test_case_sensitive_no_match(self) -> None:
        """case_sensitive=True 时大小写不匹配不触发。"""
        g = RegexGuardrail(patterns=[r"SECRET"], case_sensitive=True)
        r = await g.check("secret")
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_case_sensitive_exact_match(self) -> None:
        """case_sensitive=True 时精确匹配触发。"""
        g = RegexGuardrail(patterns=[r"SECRET"], case_sensitive=True)
        r = await g.check("my SECRET data")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_case_insensitive_default(self) -> None:
        """默认 case_sensitive=False，大小写不敏感。"""
        g = RegexGuardrail(patterns=[r"SECRET"])
        r = await g.check("secret")
        assert r.tripwire_triggered is True


# ═══════════════════════════════════════════════════════════════════
# keyword-only 模式
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrailKeywords:

    @pytest.mark.asyncio
    async def test_keyword_match(self) -> None:
        """仅使用 keywords 无 patterns。"""
        g = RegexGuardrail(keywords=["password", "密码"])
        r = await g.check("请输入你的密码")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_keyword_no_match(self) -> None:
        g = RegexGuardrail(keywords=["password", "密码"])
        r = await g.check("今天天气很好")
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_keyword_case_insensitive(self) -> None:
        g = RegexGuardrail(keywords=["Password"])
        r = await g.check("your PASSWORD is: xxx")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_keyword_case_sensitive(self) -> None:
        g = RegexGuardrail(keywords=["Password"], case_sensitive=True)
        r = await g.check("your PASSWORD is: xxx")
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_keyword_special_chars_escaped(self) -> None:
        """关键词中的特殊字符应被正确转义。"""
        g = RegexGuardrail(keywords=["$100.00"])
        r = await g.check("price is $100.00")
        assert r.tripwire_triggered is True


# ═══════════════════════════════════════════════════════════════════
# mixed patterns + keywords
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrailMixed:

    @pytest.mark.asyncio
    async def test_pattern_triggers(self) -> None:
        g = RegexGuardrail(patterns=[r"\d{4}-\d{4}-\d{4}-\d{4}"], keywords=["信用卡"])
        r = await g.check("卡号 1234-5678-9012-3456")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_keyword_triggers(self) -> None:
        g = RegexGuardrail(patterns=[r"\d{4}-\d{4}-\d{4}-\d{4}"], keywords=["信用卡"])
        r = await g.check("请不要泄露信用卡信息")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_neither_triggers(self) -> None:
        g = RegexGuardrail(patterns=[r"\d{4}-\d{4}-\d{4}-\d{4}"], keywords=["信用卡"])
        r = await g.check("今天天气很好")
        assert r.tripwire_triggered is False


# ═══════════════════════════════════════════════════════════════════
# as_tool_before_fn (JSON 序列化检测)
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrailToolBeforeFn:

    @pytest.mark.asyncio
    async def test_tool_before_fn_triggered(self) -> None:
        """as_tool_before_fn 将参数 JSON 序列化后检测。"""
        g = RegexGuardrail(patterns=[r"rm\s+-rf"])
        fn = g.as_tool_before_fn()
        # 模拟传入工具参数
        r = await fn(None, "shell_exec", {"command": "rm -rf /"})
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_tool_before_fn_safe(self) -> None:
        g = RegexGuardrail(patterns=[r"rm\s+-rf"])
        fn = g.as_tool_before_fn()
        r = await fn(None, "shell_exec", {"command": "ls -la"})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_tool_before_fn_name(self) -> None:
        """函数名应与 guardrail 名一致。"""
        g = RegexGuardrail(name="my_guard")
        fn = g.as_tool_before_fn()
        assert fn.__name__ == "my_guard"

    @pytest.mark.asyncio
    async def test_tool_before_fn_keyword_in_args(self) -> None:
        """关键词也能在 JSON 序列化的参数中被检测到。"""
        g = RegexGuardrail(keywords=["DROP TABLE"])
        fn = g.as_tool_before_fn()
        r = await fn(None, "db_query", {"sql": "DROP TABLE users"})
        assert r.tripwire_triggered is True


# ═══════════════════════════════════════════════════════════════════
# as_tool_after_fn
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrailToolAfterFn:

    @pytest.mark.asyncio
    async def test_tool_after_fn_triggered(self) -> None:
        g = RegexGuardrail(patterns=[r"\d{3}-\d{2}-\d{4}"])  # SSN 格式
        fn = g.as_tool_after_fn()
        r = await fn(None, "search", "Found: 123-45-6789")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_tool_after_fn_safe(self) -> None:
        g = RegexGuardrail(patterns=[r"\d{3}-\d{2}-\d{4}"])
        fn = g.as_tool_after_fn()
        r = await fn(None, "search", "No sensitive data here")
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_tool_after_fn_name(self) -> None:
        g = RegexGuardrail(name="custom")
        fn = g.as_tool_after_fn()
        assert fn.__name__ == "custom"


# ═══════════════════════════════════════════════════════════════════
# as_input_fn / as_output_fn 补充
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrailAdapterFns:

    @pytest.mark.asyncio
    async def test_input_fn_name(self) -> None:
        g = RegexGuardrail(name="input_guard")
        fn = g.as_input_fn()
        assert fn.__name__ == "input_guard"

    @pytest.mark.asyncio
    async def test_output_fn_name(self) -> None:
        g = RegexGuardrail(name="output_guard")
        fn = g.as_output_fn()
        assert fn.__name__ == "output_guard"

    @pytest.mark.asyncio
    async def test_input_fn_triggered(self) -> None:
        g = RegexGuardrail(keywords=["secret"])
        fn = g.as_input_fn()
        r = await fn(None, "this is a secret message")
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_output_fn_safe(self) -> None:
        g = RegexGuardrail(keywords=["secret"])
        fn = g.as_output_fn()
        r = await fn(None, "this is a normal message")
        assert r.tripwire_triggered is False


# ═══════════════════════════════════════════════════════════════════
# 边界场景
# ═══════════════════════════════════════════════════════════════════


class TestRegexGuardrailEdgeCases:

    def test_invalid_regex(self) -> None:
        """无效正则应抛出 ValueError。"""
        with pytest.raises(ValueError, match="无效"):
            RegexGuardrail(patterns=[r"["])

    @pytest.mark.asyncio
    async def test_empty_patterns_and_keywords(self) -> None:
        """空 patterns 和 keywords，不匹配任何内容。"""
        g = RegexGuardrail()
        r = await g.check("anything")
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_custom_message(self) -> None:
        g = RegexGuardrail(keywords=["bad"], message="自定义拦截消息")
        r = await g.check("this is bad")
        assert r.message == "自定义拦截消息"

    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        g = RegexGuardrail(keywords=["bad"])
        r = await g.check("")
        assert r.tripwire_triggered is False
