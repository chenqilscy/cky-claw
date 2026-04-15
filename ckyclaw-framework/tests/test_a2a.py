"""A2A 协议模块测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.a2a.adapter import A2AAdapter
from ckyclaw_framework.a2a.agent_card import AgentCapability, AgentCard, AgentSkillCard
from ckyclaw_framework.a2a.server import A2AServer
from ckyclaw_framework.a2a.task import A2ATask, TaskArtifact, TaskState, TaskStatus


# ---------------------------------------------------------------------------
# AgentCard 测试
# ---------------------------------------------------------------------------
class TestAgentCard:
    """Agent Card 序列化/反序列化测试。"""

    def test_to_dict_basic(self) -> None:
        card = AgentCard(name="test-agent", description="Test Agent")
        d = card.to_dict()
        assert d["name"] == "test-agent"
        assert d["description"] == "Test Agent"
        assert d["version"] == "1.0.0"
        assert d["capabilities"]["streaming"] is False

    def test_to_dict_with_skills(self) -> None:
        card = AgentCard(
            name="coder",
            skills=[AgentSkillCard(id="review", name="Code Review", tags=["code"])],
        )
        d = card.to_dict()
        assert len(d["skills"]) == 1
        assert d["skills"][0]["id"] == "review"
        assert d["skills"][0]["tags"] == ["code"]

    def test_roundtrip(self) -> None:
        """序列化→反序列化往返一致。"""
        original = AgentCard(
            name="agent1",
            description="描述",
            url="https://example.com/a2a",
            version="2.0.0",
            documentation_url="https://docs.example.com",
            capabilities=AgentCapability(streaming=True, push_notifications=True),
            skills=[
                AgentSkillCard(id="s1", name="Skill1", description="d1", tags=["tag1"], examples=["ex1"]),
            ],
            authentication={"type": "bearer"},
            default_input_modes=["text/plain", "application/json"],
            default_output_modes=["text/plain"],
        )
        d = original.to_dict()
        restored = AgentCard.from_dict(d)
        assert restored.name == original.name
        assert restored.url == original.url
        assert restored.version == original.version
        assert restored.capabilities.streaming is True
        assert restored.capabilities.push_notifications is True
        assert len(restored.skills) == 1
        assert restored.skills[0].id == "s1"
        assert restored.authentication == {"type": "bearer"}

    def test_from_dict_defaults(self) -> None:
        """反序列化时缺失字段使用默认值。"""
        card = AgentCard.from_dict({"name": "minimal"})
        assert card.name == "minimal"
        assert card.description == ""
        assert card.version == "1.0.0"
        assert card.capabilities.streaming is False

    def test_capabilities_default(self) -> None:
        cap = AgentCapability()
        assert cap.streaming is False
        assert cap.push_notifications is False
        assert cap.state_transition_history is False


# ---------------------------------------------------------------------------
# A2ATask 测试
# ---------------------------------------------------------------------------
class TestA2ATask:
    """A2A 任务生命周期测试。"""

    def test_initial_state_submitted(self) -> None:
        task = A2ATask()
        assert task.status == TaskStatus.SUBMITTED
        assert len(task.history) == 1
        assert task.history[0].status == TaskStatus.SUBMITTED

    def test_transition_submitted_to_working(self) -> None:
        task = A2ATask()
        task.transition(TaskStatus.WORKING, "开始处理")
        assert task.status == TaskStatus.WORKING
        assert len(task.history) == 2

    def test_transition_working_to_completed(self) -> None:
        task = A2ATask()
        task.transition(TaskStatus.WORKING)
        task.transition(TaskStatus.COMPLETED, "完成")
        assert task.status == TaskStatus.COMPLETED
        assert task.is_terminal is True

    def test_transition_working_to_failed(self) -> None:
        task = A2ATask()
        task.transition(TaskStatus.WORKING)
        task.transition(TaskStatus.FAILED, "出错了")
        assert task.status == TaskStatus.FAILED
        assert task.is_terminal is True

    def test_transition_submitted_to_canceled(self) -> None:
        task = A2ATask()
        task.transition(TaskStatus.CANCELED, "取消")
        assert task.status == TaskStatus.CANCELED
        assert task.is_terminal is True

    def test_invalid_transition_raises(self) -> None:
        """非法状态变迁抛出 ValueError。"""
        task = A2ATask()
        with pytest.raises(ValueError, match="非法状态变迁"):
            task.transition(TaskStatus.COMPLETED)

    def test_terminal_state_no_transition(self) -> None:
        """终态不可再变迁。"""
        task = A2ATask()
        task.transition(TaskStatus.WORKING)
        task.transition(TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="非法状态变迁"):
            task.transition(TaskStatus.WORKING)

    def test_add_artifact(self) -> None:
        task = A2ATask()
        artifact = TaskArtifact(name="output", parts=[{"type": "text/plain", "text": "result"}])
        task.add_artifact(artifact)
        assert len(task.artifacts) == 1
        assert task.artifacts[0].name == "output"

    def test_to_dict_roundtrip(self) -> None:
        """Task 序列化→反序列化往返。"""
        task = A2ATask(
            input_messages=[{"role": "user", "parts": [{"type": "text/plain", "text": "hello"}]}],
            metadata={"source": "test"},
        )
        task.transition(TaskStatus.WORKING)
        task.add_artifact(TaskArtifact(name="output", parts=[{"type": "text/plain", "text": "world"}]))
        task.transition(TaskStatus.COMPLETED)

        d = task.to_dict()
        restored = A2ATask.from_dict(d)
        assert restored.id == task.id
        assert restored.status == TaskStatus.COMPLETED
        assert len(restored.artifacts) == 1
        assert len(restored.history) == 3  # submitted, working, completed
        assert restored.metadata == {"source": "test"}

    def test_task_state_to_dict(self) -> None:
        state = TaskState(status=TaskStatus.WORKING, message="test")
        d = state.to_dict()
        assert d["status"] == "working"
        assert d["message"] == "test"
        assert "timestamp" in d

    def test_artifact_roundtrip(self) -> None:
        artifact = TaskArtifact(name="a1", parts=[{"type": "text/plain", "text": "data"}], metadata={"k": "v"})
        d = artifact.to_dict()
        restored = TaskArtifact.from_dict(d)
        assert restored.name == "a1"
        assert restored.parts == artifact.parts
        assert restored.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# A2AAdapter 测试
# ---------------------------------------------------------------------------
class TestA2AAdapter:
    """A2A 适配器测试。"""

    def test_agent_to_card(self) -> None:
        """从 Agent 对象生成 Agent Card。"""

        class MockTool:
            name = "search"
            description = "搜索工具"

        class MockAgent:
            name = "my-agent"
            description = "测试 Agent"
            tools = [MockTool()]

        adapter = A2AAdapter()
        card = adapter.agent_to_card(MockAgent(), url="https://example.com/a2a")
        assert card.name == "my-agent"
        assert card.url == "https://example.com/a2a"
        assert len(card.skills) == 1
        assert card.skills[0].id == "search"

    def test_agent_to_card_no_tools(self) -> None:
        """无工具的 Agent 生成空 skills。"""

        class MockAgent:
            name = "simple"
            description = ""
            tools: list[object] = []

        adapter = A2AAdapter()
        card = adapter.agent_to_card(MockAgent())
        assert card.skills == []

    def test_task_to_messages(self) -> None:
        """A2A 消息转换为 Runner 消息格式。"""
        adapter = A2AAdapter()
        task = A2ATask(
            input_messages=[
                {"role": "user", "parts": [{"type": "text/plain", "text": "hello"}]},
                {"role": "user", "parts": [{"type": "text/plain", "text": "line1"}, {"type": "text/plain", "text": "line2"}]},
            ]
        )
        messages = adapter.task_to_messages(task)
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "hello"}
        assert messages[1] == {"role": "user", "content": "line1\nline2"}

    def test_task_to_messages_empty(self) -> None:
        adapter = A2AAdapter()
        task = A2ATask(input_messages=[])
        assert adapter.task_to_messages(task) == []

    def test_apply_result_to_task(self) -> None:
        adapter = A2AAdapter()
        task = A2ATask()
        task.transition(TaskStatus.WORKING)
        adapter.apply_result_to_task(task, result_text="done")
        assert task.status == TaskStatus.COMPLETED
        assert len(task.artifacts) == 1
        assert task.artifacts[0].parts[0]["text"] == "done"

    def test_mark_failed(self) -> None:
        adapter = A2AAdapter()
        task = A2ATask()
        task.transition(TaskStatus.WORKING)
        adapter.mark_failed(task, error="boom")
        assert task.status == TaskStatus.FAILED


# ---------------------------------------------------------------------------
# A2AServer 测试
# ---------------------------------------------------------------------------
class TestA2AServer:
    """A2A Server JSON-RPC 处理测试。"""

    @pytest.fixture()
    def server(self) -> A2AServer:
        card = AgentCard(name="test-server", url="https://example.com/a2a")
        return A2AServer(card=card)

    def test_get_agent_card(self, server: A2AServer) -> None:
        d = server.get_agent_card()
        assert d["name"] == "test-server"
        assert d["url"] == "https://example.com/a2a"

    @pytest.mark.asyncio
    async def test_handle_send_task(self, server: A2AServer) -> None:
        """发送任务并获得完成结果。"""

        async def handler(task: A2ATask) -> str:
            return "处理完毕"

        server.register_handler(handler)
        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": "req-1",
            "params": {
                "id": "task-1",
                "inputMessages": [{"role": "user", "parts": [{"type": "text/plain", "text": "hello"}]}],
            },
        })
        assert resp["result"]["status"] == "completed"
        assert resp["result"]["id"] == "task-1"
        assert len(resp["result"]["artifacts"]) == 1

    @pytest.mark.asyncio
    async def test_handle_send_no_handler(self, server: A2AServer) -> None:
        """未注册处理器时返回错误。"""
        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": "req-1",
            "params": {"id": "t1"},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32603

    @pytest.mark.asyncio
    async def test_handle_send_handler_raises(self, server: A2AServer) -> None:
        """处理器抛异常时 Task 变为 failed。"""

        async def bad_handler(task: A2ATask) -> str:
            raise RuntimeError("boom")

        server.register_handler(bad_handler)
        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": "req-1",
            "params": {"id": "t-err"},
        })
        assert resp["result"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handle_get_task(self, server: A2AServer) -> None:
        """查询已存在的任务。"""

        async def handler(task: A2ATask) -> str:
            return "ok"

        server.register_handler(handler)
        await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": "req-1",
            "params": {"id": "t-get"},
        })

        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "id": "req-2",
            "params": {"id": "t-get"},
        })
        assert resp["result"]["id"] == "t-get"
        assert resp["result"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_handle_get_nonexistent(self, server: A2AServer) -> None:
        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "id": "req-1",
            "params": {"id": "no-such"},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_handle_cancel_task(self, server: A2AServer) -> None:
        """取消正在进行的任务。"""

        async def slow_handler(task: A2ATask) -> str:
            return "中途完成"

        server.register_handler(slow_handler)
        # 先发送一个查询以验证 cancel 场景
        # 由于 send 是同步执行，先发送后查询取消
        await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": "req-1",
            "params": {"id": "t-cancel"},
        })
        # 任务已完成，取消已完成任务应失败
        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/cancel",
            "id": "req-2",
            "params": {"id": "t-cancel"},
        })
        assert "error" in resp  # 已完成不可取消

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, server: A2AServer) -> None:
        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": "req-1",
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_cancel_submitted_task(self, server: A2AServer) -> None:
        """取消尚未开始的（submitted 状态的）任务。"""
        # 直接在 server._tasks 中放一个 submitted 状态的 task
        task = A2ATask(id="t-sub")
        server._tasks["t-sub"] = task
        resp = await server.handle_request({
            "jsonrpc": "2.0",
            "method": "tasks/cancel",
            "id": "req-1",
            "params": {"id": "t-sub"},
        })
        assert resp["result"]["status"] == "canceled"
