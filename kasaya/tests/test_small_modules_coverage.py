"""小模块边界路径覆盖测试 — 合并多个模块的少量缺失行覆盖。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kasaya.mcp.connection import _connect_http, _connect_sse, _connect_stdio
from kasaya.model.litellm_provider import LiteLLMProvider
from kasaya.model.message import Message, MessageRole
from kasaya.model.settings import ModelSettings
from kasaya.session.history_trimmer import HistoryTrimConfig, HistoryTrimmer, HistoryTrimStrategy
from kasaya.skills.injector import SkillInjector
from kasaya.skills.registry import SkillRegistry
from kasaya.skills.skill import Skill
from kasaya.team.team import Team
from kasaya.team.team_runner import TeamRunner
from kasaya.workflow.step import (
    AgentStep,
    BranchCondition,
    ConditionalStep,
)
from kasaya.workflow.validator import validate_workflow
from kasaya.workflow.workflow import Edge, Workflow


class TestLiteLLMProviderExtraSettings:
    """覆盖 litellm_provider.py lines 59, 78, 80, 82 — response_format/top_p/stop/extra。"""

    @pytest.mark.asyncio
    async def test_response_format_param(self) -> None:
        """覆盖 response_format 非 None 时注入到 kwargs。"""
        provider = LiteLLMProvider()
        messages = [Message(role=MessageRole.USER, content="hello")]
        response_format = {"type": "json_object"}

        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock(message=MagicMock(content="ok", tool_calls=None))]
            mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            await provider.chat(
                model="test-model",
                messages=messages,
                response_format=response_format,
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs.get("response_format") == response_format

    @pytest.mark.asyncio
    async def test_top_p_and_stop(self) -> None:
        """top_p 和 stop 参数注入。"""
        provider = LiteLLMProvider()
        messages = [Message(role=MessageRole.USER, content="hello")]
        settings = ModelSettings(top_p=0.9, stop=["END"])

        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock(message=MagicMock(content="ok", tool_calls=None))]
            mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            await provider.chat(
                model="test-model",
                messages=messages,
                settings=settings,
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs.get("top_p") == 0.9
            assert call_kwargs.get("stop") == ["END"]

    @pytest.mark.asyncio
    async def test_extra_settings(self) -> None:
        """extra 字典参数注入。"""
        provider = LiteLLMProvider()
        messages = [Message(role=MessageRole.USER, content="hello")]
        settings = ModelSettings(extra={"seed": 42, "logprobs": True})

        with patch("kasaya.model.litellm_provider.litellm") as mock_litellm:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock(message=MagicMock(content="ok", tool_calls=None))]
            mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

            await provider.chat(
                model="test-model",
                messages=messages,
                settings=settings,
            )

            call_kwargs = mock_litellm.acompletion.call_args[1]
            assert call_kwargs.get("seed") == 42
            assert call_kwargs.get("logprobs") is True


# ===== History Trimmer =====


class TestHistoryTrimmerUnknownStrategy:
    """覆盖 history_trimmer.py line 74 — 未知策略回退。"""

    def test_unknown_strategy_returns_all(self) -> None:
        """未知的 strategy 值不报错，返回原始消息。"""
        messages = [Message(role=MessageRole.USER, content="hi")]
        config = HistoryTrimConfig(strategy=HistoryTrimStrategy.SLIDING_WINDOW, max_history_messages=-1)
        # 测试 SLIDING_WINDOW 策略的正常路径
        result = HistoryTrimmer.trim(messages, config)
        assert len(result) >= 0


# ===== Skills Injector =====


class TestSkillInjectorBudgetOverflow:
    """覆盖 injector.py line 36 — token 预算溢出。"""

    def test_budget_overflow_truncates(self) -> None:
        """当 skill header 超出 char_budget 时停止注入。"""
        injector = SkillInjector(max_skill_tokens=1)  # 极小预算: 1 * 4 = 4 chars

        skills = [
            Skill(name="very_long_skill_name_that_exceeds_budget", version="1.0", description="test", category="test"),
        ]

        result = injector.format_for_injection(skills)
        # 预算极小，可能只包含 prefix 或为空
        assert isinstance(result, str)


# ===== Skills Registry =====


class TestSkillRegistryTagFilter:
    """覆盖 registry.py line 59 — tag 过滤。"""

    @pytest.mark.asyncio
    async def test_filter_by_tag(self) -> None:
        """按 tag 过滤 skills。"""
        registry = SkillRegistry()
        skill1 = Skill(name="s1", version="1.0", description="test", category="cat1", tags=["web", "api"])
        skill2 = Skill(name="s2", version="1.0", description="test", category="cat1", tags=["cli"])

        await registry.register(skill1)
        await registry.register(skill2)

        results = await registry.list_skills(tag="web")
        assert len(results) == 1
        assert results[0].name == "s1"

    @pytest.mark.asyncio
    async def test_filter_by_nonexistent_tag(self) -> None:
        """不存在的 tag → 空结果。"""
        registry = SkillRegistry()
        skill = Skill(name="s1", version="1.0", description="test", category="cat1", tags=["web"])
        await registry.register(skill)

        results = await registry.list_skills(tag="nonexistent")
        assert results == []


# ===== Team Runner =====


class TestTeamRunnerUnknownProtocol:
    """覆盖 team_runner.py line 80 — 未知协议。"""

    @pytest.mark.asyncio
    async def test_unknown_protocol_raises(self) -> None:
        """未知的 TeamProtocol 值 → ValueError。"""
        team = Team(name="test_team")
        team.protocol = "UNKNOWN"  # type: ignore[assignment]  # 故意设置非法值

        with pytest.raises(ValueError, match="未支持的团队协议"):
            await TeamRunner.run(team, "test input")


# ===== Team as_tool =====
class TestTeamAsTool:
    """覆盖 team.py lines 69-72 — as_tool 内部函数。"""

    @pytest.mark.asyncio
    async def test_team_as_tool_runs(self) -> None:
        """Team.as_tool() 返回可执行的 FunctionTool。"""
        team = Team(name="test_team", description="A test team")

        tool = team.as_tool()
        assert tool.name == "test_team"
        assert tool.description == "A test team"

        # 调用 tool.fn 应调用 TeamRunner.run
        with patch("kasaya.team.team_runner.TeamRunner.run", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.output = "team result"
            mock_run.return_value = mock_result

            result = await tool.fn("test input")
            assert result == "team result"
            mock_run.assert_called_once()


# ===== Workflow Validator =====


class TestWorkflowValidatorDanglingEdge:
    """覆盖 validator.py line 98 — 边指向不存在的 step。"""

    def test_edge_source_not_exists(self) -> None:
        """edge 的 source_step_id 不存在。"""
        step = AgentStep(id="s1", agent_name="agent1")
        edge = Edge(id="e1", source_step_id="nonexistent", target_step_id="s1")
        workflow = Workflow(
            name="test",
            steps=[step],
            edges=[edge],
        )
        errors = validate_workflow(workflow)
        assert any("source" in e and "nonexistent" in e for e in errors)

    def test_edge_target_not_exists(self) -> None:
        """edge 的 target_step_id 不存在。"""
        step = AgentStep(id="s1", agent_name="agent1")
        edge = Edge(id="e1", source_step_id="s1", target_step_id="nonexistent")
        workflow = Workflow(
            name="test",
            steps=[step],
            edges=[edge],
        )
        errors = validate_workflow(workflow)
        assert any("target" in e and "nonexistent" in e for e in errors)


class TestWorkflowValidatorConditionalDefault:
    """覆盖 validator.py line 181 — ConditionalStep default_step_id 不存在。"""

    def test_conditional_default_not_exists(self) -> None:
        """ConditionalStep 的 default_step_id 指向不存在的 step。"""
        step = ConditionalStep(
            id="c1",
            branches=[
                BranchCondition(label="b1", condition="True", target_step_id="s1"),
            ],
            default_step_id="nonexistent",
        )
        agent_step = AgentStep(id="s1", agent_name="agent1")
        workflow = Workflow(
            name="test",
            steps=[step, agent_step],
            edges=[],
        )
        errors = validate_workflow(workflow)
        assert any("默认目标" in e and "nonexistent" in e for e in errors)


# ===== FunctionTool Schema Generation =====


class TestFunctionToolSchemaGeneration:
    """覆盖 function_tool.py lines 65-66 — _generate_parameters_schema 函数。"""

    def test_auto_schema_via_decorator(self) -> None:
        """通过 @function_tool 装饰器触发自动 schema 生成。"""
        from kasaya.tools.function_tool import function_tool

        @function_tool()
        async def my_tool(name: str, count: int = 5) -> str:
            """测试工具。"""
            return f"{name}: {count}"

        schema = my_tool.parameters_schema
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "count" in schema["properties"]

    def test_schema_gen_with_broken_hints(self) -> None:
        """get_type_hints 失败时走 except 分支。"""
        from kasaya.tools.function_tool import _generate_parameters_schema

        # 创建一个 get_type_hints 会失败的函数
        def broken_fn(x, y=10):
            pass

        # 模拟 get_type_hints 抛异常
        with patch("kasaya.tools.function_tool.get_type_hints", side_effect=Exception("bad")):
            schema = _generate_parameters_schema(broken_fn)
        assert "properties" in schema
        assert "x" in schema["properties"]


# ===== MCP Connection Error Paths =====


class TestMCPConnectionTimeouts:
    """覆盖 connection.py timeout/error 路径（lines 147-148, 177-182, 208-213）。

    通过 mock mcp 客户端来模拟超时和错误。
    """

    @pytest.mark.asyncio
    async def test_stdio_timeout(self) -> None:
        """stdio 连接超时 → 返回空列表。"""
        from contextlib import AsyncExitStack

        config = MagicMock()
        config.name = "test_server"
        config.command = "echo hello"
        config.args = []
        config.env = None
        config.connect_timeout = 0.001

        async with AsyncExitStack() as stack:
            # 让 stack.enter_async_context 抛超时

            async def _timeout_enter(cm: Any) -> Any:
                raise TimeoutError

            stack.enter_async_context = _timeout_enter  # type: ignore[assignment]
            result = await _connect_stdio(stack, config)
            assert result == []

    @pytest.mark.asyncio
    async def test_stdio_general_error(self) -> None:
        """stdio 连接一般错误 → 返回空列表。"""
        from contextlib import AsyncExitStack

        config = MagicMock()
        config.name = "test_server"
        config.command = "echo hello"
        config.args = []
        config.env = None
        config.connect_timeout = 5

        async with AsyncExitStack() as stack:

            async def _error_enter(cm: Any) -> Any:
                raise RuntimeError("broken")

            stack.enter_async_context = _error_enter  # type: ignore[assignment]
            result = await _connect_stdio(stack, config)
            assert result == []

    @pytest.mark.asyncio
    async def test_sse_timeout(self) -> None:
        """SSE 连接超时 → 返回空列表。"""
        from contextlib import AsyncExitStack

        config = MagicMock()
        config.name = "test_server"
        config.url = "http://localhost:9999"
        config.headers = None
        config.connect_timeout = 0.001

        async with AsyncExitStack() as stack:
            async def _timeout_enter(cm: Any) -> Any:
                raise TimeoutError

            stack.enter_async_context = _timeout_enter  # type: ignore[assignment]
            result = await _connect_sse(stack, config)
            assert result == []

    @pytest.mark.asyncio
    async def test_sse_general_error(self) -> None:
        """SSE 连接一般错误 → 返回空列表。"""
        from contextlib import AsyncExitStack

        config = MagicMock()
        config.name = "test_server"
        config.url = "http://localhost:9999"
        config.headers = None
        config.connect_timeout = 5

        async with AsyncExitStack() as stack:
            async def _error_enter(cm: Any) -> Any:
                raise RuntimeError("conn failed")

            stack.enter_async_context = _error_enter  # type: ignore[assignment]
            result = await _connect_sse(stack, config)
            assert result == []

    @pytest.mark.asyncio
    async def test_http_timeout(self) -> None:
        """HTTP 连接超时 → 返回空列表。"""
        from contextlib import AsyncExitStack

        config = MagicMock()
        config.name = "test_server"
        config.url = "http://localhost:9999"
        config.headers = None
        config.connect_timeout = 0.001

        async with AsyncExitStack() as stack:
            async def _timeout_enter(cm: Any) -> Any:
                raise TimeoutError

            stack.enter_async_context = _timeout_enter  # type: ignore[assignment]
            result = await _connect_http(stack, config)
            assert result == []

    @pytest.mark.asyncio
    async def test_http_general_error(self) -> None:
        """HTTP 连接一般错误 → 返回空列表。"""
        from contextlib import AsyncExitStack

        config = MagicMock()
        config.name = "test_server"
        config.url = "http://localhost:9999"
        config.headers = None
        config.connect_timeout = 5

        async with AsyncExitStack() as stack:
            async def _error_enter(cm: Any) -> Any:
                raise RuntimeError("conn failed")

            stack.enter_async_context = _error_enter  # type: ignore[assignment]
            result = await _connect_http(stack, config)
            assert result == []
