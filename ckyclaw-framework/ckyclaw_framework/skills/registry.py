"""SkillRegistry — Skill 注册表，管理已安装 Skill 的增删查改。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.skills.skill import Skill, SkillCategory


class SkillNotFoundError(Exception):
    """Skill 不存在。"""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Skill '{name}' 未注册")


class SkillRegistry:
    """Skill 注册表。

    线程安全的内存注册表，管理已安装 Skill 的生命周期。
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._lock = asyncio.Lock()

    async def register(self, skill: Skill) -> None:
        """注册 Skill（同名则更新）。"""
        async with self._lock:
            skill.updated_at = skill.updated_at  # keep original if new
            self._skills[skill.name] = skill

    async def unregister(self, name: str) -> None:
        """卸载 Skill。"""
        async with self._lock:
            self._skills.pop(name, None)

    async def get(self, name: str) -> Skill:
        """获取 Skill。不存在时抛出 SkillNotFoundError。"""
        async with self._lock:
            skill = self._skills.get(name)
        if skill is None:
            raise SkillNotFoundError(name)
        return skill

    async def list_skills(
        self,
        *,
        category: SkillCategory | None = None,
        tag: str | None = None,
    ) -> list[Skill]:
        """列出已注册 Skill（支持过滤）。"""
        async with self._lock:
            skills = list(self._skills.values())
        if category is not None:
            skills = [s for s in skills if s.category == category]
        if tag is not None:
            skills = [s for s in skills if tag in s.tags]
        return skills

    async def find_for_agent(self, agent_name: str) -> list[Skill]:
        """查找适用于指定 Agent 的 Skill。"""
        async with self._lock:
            return [
                s for s in self._skills.values()
                if not s.applicable_agents or agent_name in s.applicable_agents
            ]
