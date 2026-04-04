"""Skill — 技能知识注入包核心类型与加载器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SkillCategory(str, Enum):
    """Skill 分类。"""

    PUBLIC = "public"
    """公共/内置 Skill。"""

    CUSTOM = "custom"
    """用户自定义 Skill。"""


@dataclass
class Skill:
    """Skill 定义 — 领域知识注入包。

    Skill 不是可执行的工具函数，而是通过结构化的知识文件
    向 Agent 注入领域知识和操作指令。
    """

    name: str
    """Skill 唯一名称（小写字母、数字、连字符）。"""

    version: str = "1.0.0"
    """语义化版本号。"""

    description: str = ""
    """Skill 功能描述。"""

    content: str = ""
    """SKILL.md 主知识文件内容。"""

    category: SkillCategory = SkillCategory.CUSTOM
    """Skill 分类（public / custom）。"""

    tags: list[str] = field(default_factory=list)
    """标签列表（用于搜索和匹配）。"""

    applicable_agents: list[str] = field(default_factory=list)
    """适用的 Agent 名称列表。空列表表示适用所有 Agent。"""

    author: str = ""
    """作者。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据。"""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """创建时间。"""

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """最后更新时间。"""
