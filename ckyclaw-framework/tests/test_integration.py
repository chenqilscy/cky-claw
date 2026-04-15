"""端到端集成测试 — 使用真实 LLM 验证完整链路。

运行方式：
    cd ckyclaw-framework
    uv run python -m pytest tests/test_integration.py -v -m integration

需要 .env.local 配置文件（不提交 Git）：
    ZHIPUAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
    ZHIPUAI_API_KEY=xxx

无 API Key 时自动跳过。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ckyclaw_framework.agent.agent import Agent
from ckyclaw_framework.model.litellm_provider import LiteLLMProvider
from ckyclaw_framework.model.message import MessageRole
from ckyclaw_framework.runner.result import StreamEventType
from ckyclaw_framework.runner.run_config import RunConfig
from ckyclaw_framework.runner.runner import Runner
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.session.session import Session
from ckyclaw_framework.tools.function_tool import function_tool


def _load_env() -> None:
    """从项目根目录的 .env.local 加载环境变量。"""
    env_file = Path(__file__).parent.parent.parent / ".env.local"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env()

# 智谱 AI 通过 LiteLLM OpenAI 兼容模式
_API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
_BASE_URL = os.environ.get("ZHIPUAI_BASE_URL", "")
_HAS_CREDENTIALS = bool(_API_KEY and _BASE_URL)

# 使用 GLM-4-Flash（智谱免费模型，适合测试）
_MODEL = "openai/glm-4-flash"

# 集成测试标记 — 默认不随 pytest 跑，需显式 -m integration
pytestmark = pytest.mark.integration

skip_no_credentials = pytest.mark.skipif(
    not _HAS_CREDENTIALS,
    reason="缺少 ZHIPUAI_API_KEY / ZHIPUAI_BASE_URL，跳过集成测试",
)


def _make_config() -> RunConfig:
    """创建带智谱凭据的 RunConfig。"""
    # LiteLLM OpenAI 兼容模式：通过环境变量设置
    os.environ["OPENAI_API_KEY"] = _API_KEY
    os.environ["OPENAI_API_BASE"] = _BASE_URL
    return RunConfig(model=_MODEL, model_provider=LiteLLMProvider())


# ── 1.5.1 基本对话 ─────────────────────────────────────────────


class TestIntegrationBasicChat:
    @skip_no_credentials
    @pytest.mark.asyncio
    async def test_simple_chat(self) -> None:
        """Agent → 发送消息 → 获得回复。"""
        agent = Agent(
            name="assistant",
            instructions="你是一个有帮助的助手。请用中文简短回答。",
        )
        config = _make_config()

        result = await Runner.run(agent, "你好，请回答1+1等于几？", config=config)

        assert result.output  # 非空
        assert result.last_agent_name == "assistant"
        assert result.turn_count == 1
        assert result.token_usage is not None
        assert result.token_usage.total_tokens > 0
        # LLM 回复应包含 "2"
        assert "2" in result.output
        print(f"\n[集成测试] 基本对话回复: {result.output}")
        print(f"[集成测试] Token 消耗: {result.token_usage}")

    @skip_no_credentials
    @pytest.mark.asyncio
    async def test_streamed_chat(self) -> None:
        """流式对话回复完整。"""
        agent = Agent(
            name="assistant",
            instructions="用中文简短回答。",
        )
        config = _make_config()

        events = []
        chunks: list[str] = []
        async for event in Runner.run_streamed(agent, "中国的首都是哪里？", config=config):
            events.append(event)
            if event.type == StreamEventType.LLM_CHUNK and event.data:
                chunks.append(event.data)

        event_types = [e.type for e in events]
        assert StreamEventType.AGENT_START in event_types
        assert StreamEventType.LLM_CHUNK in event_types
        assert StreamEventType.RUN_COMPLETE in event_types

        full_output = "".join(chunks)
        assert "北京" in full_output
        print(f"\n[集成测试] 流式回复: {full_output}")


# ── 1.5.2 工具调用 ─────────────────────────────────────────────


class TestIntegrationToolCalls:
    @skip_no_credentials
    @pytest.mark.asyncio
    async def test_tool_call_and_response(self) -> None:
        """Agent + 工具调用 → 工具执行 → 回复。"""
        @function_tool()
        def get_weather(city: str) -> str:
            """获取指定城市的天气信息。"""
            return f"{city}今天晴，气温28°C，适合外出。"

        agent = Agent(
            name="weather-bot",
            instructions="你是天气助手。当用户询问天气时，使用 get_weather 工具查询。请用中文回答。",
            tools=[get_weather],
        )
        config = _make_config()

        result = await Runner.run(agent, "北京今天天气怎么样？", config=config)

        assert result.output  # 非空
        # 应该经过了工具调用（至少 2 轮：tool_call + final）
        assert result.turn_count >= 2
        # 回复应包含工具返回的信息
        assert "28" in result.output or "晴" in result.output
        print(f"\n[集成测试] 工具调用回复: {result.output}")
        print(f"[集成测试] 轮次: {result.turn_count}")

        # 验证消息历史包含 tool 角色
        tool_msgs = [m for m in result.messages if m.role == MessageRole.TOOL]
        assert len(tool_msgs) >= 1
        assert "28°C" in tool_msgs[0].content


# ── 1.5.3 多轮对话 + Session ───────────────────────────────────


class TestIntegrationMultiTurnSession:
    @skip_no_credentials
    @pytest.mark.asyncio
    async def test_multi_turn_with_session(self) -> None:
        """多轮对话 + Session 持久化。"""
        backend = InMemorySessionBackend()
        agent = Agent(
            name="assistant",
            instructions="你是一个有帮助的助手。请用中文简短回答。记住用户告诉你的信息。",
        )
        config = _make_config()

        # 第 1 轮：告诉 Agent 信息
        session1 = Session(session_id="integration-s1", backend=backend)
        result1 = await Runner.run(
            agent, "我叫小明，我今年25岁。请记住。",
            session=session1,
            config=config,
        )
        assert result1.output
        print(f"\n[集成测试] 第1轮: {result1.output}")

        # 验证 session 已保存
        stored = await backend.load("integration-s1")
        assert stored is not None
        assert len(stored) >= 2  # user + assistant

        # 第 2 轮：测试 Agent 是否记住了
        session2 = Session(session_id="integration-s1", backend=backend)
        result2 = await Runner.run(
            agent, "我叫什么名字？我多大了？",
            session=session2,
            config=config,
        )
        assert result2.output
        print(f"[集成测试] 第2轮: {result2.output}")

        # Agent 应该能回忆出名字和年龄
        assert "小明" in result2.output or "25" in result2.output

        # 验证 session 现在有 4 条消息
        stored_final = await backend.load("integration-s1")
        assert stored_final is not None
        assert len(stored_final) >= 4  # 2 rounds × (user + assistant)
        print(f"[集成测试] Session 总消息数: {len(stored_final)}")
