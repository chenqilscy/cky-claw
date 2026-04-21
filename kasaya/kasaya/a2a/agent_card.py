"""Agent Card — A2A 服务发现协议。

Agent Card 遵循 Google A2A 规范，通过 /.well-known/agent.json 端点发布。
描述 Agent 的能力、技能和连接信息，供其他 Agent 或编排器发现并调用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentCapability:
    """Agent 能力声明。"""

    streaming: bool = False
    """是否支持流式响应。"""

    push_notifications: bool = False
    """是否支持推送通知。"""

    state_transition_history: bool = False
    """是否记录状态变迁历史。"""


@dataclass
class AgentSkillCard:
    """Agent 技能描述（在 Agent Card 中声明可执行的技能）。"""

    id: str
    """技能唯一标识。"""

    name: str
    """技能名称。"""

    description: str = ""
    """技能描述。"""

    tags: list[str] = field(default_factory=list)
    """技能标签，用于分类与搜索。"""

    examples: list[str] = field(default_factory=list)
    """示例输入。"""


@dataclass
class AgentCard:
    """Agent Card — 遵循 A2A 发现协议。

    通过 ``/.well-known/agent.json`` 端点发布，描述 Agent 基本信息、
    能力、技能列表和连接方式。

    使用示例::

        card = AgentCard(
            name="code-reviewer",
            description="自动代码审查 Agent",
            url="https://example.com/a2a",
            skills=[AgentSkillCard(id="review", name="Code Review")],
        )
        # 序列化为 dict 后发布到 /.well-known/agent.json
        json_data = card.to_dict()
    """

    name: str
    """Agent 名称。"""

    description: str = ""
    """Agent 描述。"""

    url: str = ""
    """A2A 端点 URL（接收 Task 请求）。"""

    version: str = "1.0.0"
    """Agent Card 版本。"""

    documentation_url: str = ""
    """文档链接。"""

    capabilities: AgentCapability = field(default_factory=AgentCapability)
    """Agent 能力声明。"""

    skills: list[AgentSkillCard] = field(default_factory=list)
    """Agent 可执行的技能列表。"""

    authentication: dict[str, Any] = field(default_factory=dict)
    """认证要求（如 Bearer Token、API Key）。"""

    default_input_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    """默认接受的输入 MIME 类型。"""

    default_output_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    """默认输出 MIME 类型。"""

    def to_dict(self) -> dict[str, Any]:
        """序列化为符合 A2A 规范的字典。"""
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "documentationUrl": self.documentation_url,
            "capabilities": {
                "streaming": self.capabilities.streaming,
                "pushNotifications": self.capabilities.push_notifications,
                "stateTransitionHistory": self.capabilities.state_transition_history,
            },
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "tags": s.tags,
                    "examples": s.examples,
                }
                for s in self.skills
            ],
            "authentication": self.authentication,
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCard:
        """从字典反序列化 Agent Card。"""
        caps_data = data.get("capabilities", {})
        capabilities = AgentCapability(
            streaming=caps_data.get("streaming", False),
            push_notifications=caps_data.get("pushNotifications", False),
            state_transition_history=caps_data.get("stateTransitionHistory", False),
        )
        skills = [
            AgentSkillCard(
                id=s["id"],
                name=s["name"],
                description=s.get("description", ""),
                tags=s.get("tags", []),
                examples=s.get("examples", []),
            )
            for s in data.get("skills", [])
        ]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            url=data.get("url", ""),
            version=data.get("version", "1.0.0"),
            documentation_url=data.get("documentationUrl", ""),
            capabilities=capabilities,
            skills=skills,
            authentication=data.get("authentication", {}),
            default_input_modes=data.get("defaultInputModes", ["text/plain"]),
            default_output_modes=data.get("defaultOutputModes", ["text/plain"]),
        )
