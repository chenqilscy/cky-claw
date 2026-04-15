"""Agent 数据模型单元测试 — AgentConfig / AgentOutput / JsonDict。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ckyclaw_framework.agent.config import AgentConfig
from ckyclaw_framework.agent.output import AgentOutput

if TYPE_CHECKING:
    from ckyclaw_framework._internal.types import JsonDict

# ═══════════════════════════════════════════════════════════════════
# AgentConfig
# ═══════════════════════════════════════════════════════════════════


class TestAgentConfig:
    """AgentConfig 数据类基本测试。"""

    def test_required_field(self) -> None:
        cfg = AgentConfig(name="my_agent")
        assert cfg.name == "my_agent"
        assert cfg.description == ""
        assert cfg.instructions == ""
        assert cfg.model is None
        assert cfg.model_settings is None
        assert cfg.tool_groups is None
        assert cfg.handoffs is None

    def test_all_fields(self) -> None:
        cfg = AgentConfig(
            name="agent1",
            description="desc",
            instructions="do stuff",
            model="gpt-4o",
            model_settings={"temperature": 0.5},
            tool_groups=["search", "calc"],
            handoffs=["agent2"],
        )
        assert cfg.name == "agent1"
        assert cfg.description == "desc"
        assert cfg.instructions == "do stuff"
        assert cfg.model == "gpt-4o"
        assert cfg.model_settings == {"temperature": 0.5}
        assert cfg.tool_groups == ["search", "calc"]
        assert cfg.handoffs == ["agent2"]

    def test_equality(self) -> None:
        a = AgentConfig(name="a", description="d")
        b = AgentConfig(name="a", description="d")
        assert a == b

    def test_inequality(self) -> None:
        a = AgentConfig(name="a")
        b = AgentConfig(name="b")
        assert a != b


# ═══════════════════════════════════════════════════════════════════
# AgentOutput
# ═══════════════════════════════════════════════════════════════════


class TestAgentOutput:
    """AgentOutput 数据类基本测试。"""

    def test_string_value(self) -> None:
        output = AgentOutput(value="hello")
        assert output.value == "hello"
        assert output.output_type is None

    def test_dict_value(self) -> None:
        output = AgentOutput(value={"key": "val"}, output_type=dict)
        assert output.value == {"key": "val"}
        assert output.output_type is dict

    def test_none_value(self) -> None:
        output = AgentOutput(value=None)
        assert output.value is None

    def test_complex_value(self) -> None:
        data = [1, 2, {"nested": True}]
        output = AgentOutput(value=data, output_type=list)
        assert output.value == data


# ═══════════════════════════════════════════════════════════════════
# JsonDict
# ═══════════════════════════════════════════════════════════════════


class TestJsonDict:
    """JsonDict TypeAlias 基本测试。"""

    def test_type_alias(self) -> None:
        """JsonDict 应该是 dict[str, Any] 的别名。"""
        d: JsonDict = {"key": "value", "num": 42, "nested": {"a": [1, 2]}}
        assert isinstance(d, dict)
        assert d["key"] == "value"
        assert d["num"] == 42

    def test_empty_dict(self) -> None:
        d: JsonDict = {}
        assert len(d) == 0
