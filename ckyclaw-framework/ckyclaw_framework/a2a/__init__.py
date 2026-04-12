"""A2A (Agent-to-Agent) 协议模块。

实现 Google Agent-to-Agent 协议，支持跨平台 Agent 互操作。
包含 AgentCard 发现协议、Task 生命周期管理、A2AClient / A2AServer 以及适配层。
"""

from __future__ import annotations

from ckyclaw_framework.a2a.agent_card import AgentCard, AgentCapability, AgentSkillCard
from ckyclaw_framework.a2a.task import A2ATask, TaskArtifact, TaskState, TaskStatus
from ckyclaw_framework.a2a.client import A2AClient
from ckyclaw_framework.a2a.server import A2AServer
from ckyclaw_framework.a2a.adapter import A2AAdapter

__all__ = [
    "AgentCard",
    "AgentCapability",
    "AgentSkillCard",
    "A2ATask",
    "TaskArtifact",
    "TaskState",
    "TaskStatus",
    "A2AClient",
    "A2AServer",
    "A2AAdapter",
]
