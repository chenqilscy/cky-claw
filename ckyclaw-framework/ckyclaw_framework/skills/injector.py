"""SkillInjector — 将 Skill 知识注入 Agent 上下文。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.skills.skill import Skill


class SkillInjector:
    """将 Skill 知识格式化为可注入 System Message 的文本。

    与 Runner 解耦——由上层在调用 Runner 前使用。
    """

    def __init__(self, max_skill_tokens: int = 2000) -> None:
        self._max_skill_tokens = max_skill_tokens

    def format_for_injection(self, skills: list[Skill]) -> str:
        """将 Skill 列表格式化为注入文本。

        Args:
            skills: 已启用的 Skill 列表。

        Returns:
            格式化后的知识注入文本。空列表返回空字符串。
        """
        if not skills:
            return ""

        lines: list[str] = ["## 已启用技能"]
        char_budget = self._max_skill_tokens * 4
        used = len(lines[0])

        for skill in skills:
            header = f"### {skill.name} (v{skill.version})"
            if used + len(header) + 1 > char_budget:
                break

            lines.append(header)
            used += len(header) + 1

            if skill.description:
                desc_line = f"*{skill.description}*"
                if used + len(desc_line) + 1 <= char_budget:
                    lines.append(desc_line)
                    used += len(desc_line) + 1

            if skill.content:
                remaining = char_budget - used
                if remaining > 20:
                    content = skill.content[:remaining]
                    if len(content) < len(skill.content):
                        content = content.rstrip() + "..."
                    lines.append(content)
                    used += len(content) + 1

            lines.append("")  # blank line separator
            used += 1

        return "\n".join(lines).rstrip() if len(lines) > 1 else ""
