"""A2A Adapter — 协议适配隔离层。

A2AAdapter 将 CkyClaw 内部的 Agent + Runner 执行模型，
适配到 A2A 协议的 Task 请求/响应模型。

当 A2A 协议规范变动时，只需修改此适配器，不影响其余代码。
"""

from __future__ import annotations

from typing import Any

from ckyclaw_framework.a2a.agent_card import AgentCapability, AgentCard, AgentSkillCard
from ckyclaw_framework.a2a.task import A2ATask, TaskArtifact, TaskStatus


class A2AAdapter:
    """A2A 协议适配器 — 在内部 Agent 模型与 A2A 规范之间转换。

    使用示例::

        adapter = A2AAdapter()

        # 从 Agent 生成 Agent Card
        card = adapter.agent_to_card(agent, url="https://example.com/a2a")

        # 将 A2A Task 输入转为 Runner 消息
        messages = adapter.task_to_messages(task)

        # 将 Runner 结果封装回 Task
        adapter.apply_result_to_task(task, result_text="审查结论")
    """

    def agent_to_card(
        self,
        agent: Any,
        *,
        url: str = "",
        version: str = "1.0.0",
        documentation_url: str = "",
    ) -> AgentCard:
        """从 CkyClaw Agent 实例生成 A2A Agent Card。

        Args:
            agent: CkyClaw Agent 实例（duck typing，需有 name/description/tools 属性）。
            url: A2A 端点 URL。
            version: Agent Card 版本。
            documentation_url: 文档链接。

        Returns:
            AgentCard 实例。
        """
        skills: list[AgentSkillCard] = []
        tools = getattr(agent, "tools", []) or []
        for tool in tools:
            tool_name = getattr(tool, "name", str(tool))
            tool_desc = getattr(tool, "description", "")
            skills.append(
                AgentSkillCard(
                    id=tool_name,
                    name=tool_name,
                    description=tool_desc,
                )
            )

        return AgentCard(
            name=getattr(agent, "name", "unknown"),
            description=getattr(agent, "description", ""),
            url=url,
            version=version,
            documentation_url=documentation_url,
            capabilities=AgentCapability(streaming=False),
            skills=skills,
        )

    def task_to_messages(self, task: A2ATask) -> list[dict[str, Any]]:
        """将 A2A Task 的输入消息转换为 CkyClaw Runner 格式。

        A2A 消息格式: ``{"role": "user", "parts": [{"type": "text/plain", "text": "..."}]}``
        Runner 消息格式: ``{"role": "user", "content": "..."}``

        Args:
            task: A2A 任务实例。

        Returns:
            Runner 可接受的消息列表。
        """
        messages: list[dict[str, Any]] = []
        for msg in task.input_messages:
            role = msg.get("role", "user")
            parts = msg.get("parts", [])
            text_parts: list[str] = []
            for part in parts:
                if part.get("type", "").startswith("text/"):
                    text_parts.append(part.get("text", ""))
            content = "\n".join(text_parts) if text_parts else ""
            messages.append({"role": role, "content": content})
        return messages

    def apply_result_to_task(
        self,
        task: A2ATask,
        *,
        result_text: str,
        artifact_name: str = "output",
    ) -> None:
        """将 Runner 执行结果封装回 A2A Task。

        Args:
            task: A2A 任务实例。
            result_text: 运行结果文本。
            artifact_name: 产出物名称。
        """
        task.add_artifact(
            TaskArtifact(
                name=artifact_name,
                parts=[{"type": "text/plain", "text": result_text}],
            )
        )
        task.transition(TaskStatus.COMPLETED, "执行完成")

    def mark_failed(self, task: A2ATask, *, error: str) -> None:
        """将 Task 标记为失败。"""
        task.transition(TaskStatus.FAILED, error)
