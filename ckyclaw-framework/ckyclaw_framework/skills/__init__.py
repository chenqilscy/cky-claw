"""技能系统 — 领域知识注入包。"""

from ckyclaw_framework.skills.injector import SkillInjector
from ckyclaw_framework.skills.registry import SkillNotFoundError, SkillRegistry
from ckyclaw_framework.skills.skill import Skill, SkillCategory

__all__ = [
    "Skill",
    "SkillCategory",
    "SkillInjector",
    "SkillNotFoundError",
    "SkillRegistry",
]
