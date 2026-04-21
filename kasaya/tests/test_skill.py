"""Skill 技能系统 — Framework 层测试。"""

from __future__ import annotations

from datetime import datetime

import pytest

from kasaya.skills.injector import SkillInjector
from kasaya.skills.registry import SkillNotFoundError, SkillRegistry
from kasaya.skills.skill import Skill, SkillCategory

# ── SkillCategory ────────────────────────────────────


class TestSkillCategory:
    def test_values(self) -> None:
        assert SkillCategory.PUBLIC.value == "public"
        assert SkillCategory.CUSTOM.value == "custom"

    def test_is_str_enum(self) -> None:
        assert isinstance(SkillCategory.PUBLIC, str)


# ── Skill dataclass ─────────────────────────────────


class TestSkill:
    def test_defaults(self) -> None:
        s = Skill(name="test-skill", content="hello")
        assert s.name == "test-skill"
        assert s.version == "1.0.0"
        assert s.description == ""
        assert s.content == "hello"
        assert s.category == SkillCategory.CUSTOM
        assert s.tags == []
        assert s.applicable_agents == []
        assert s.author == ""
        assert isinstance(s.created_at, datetime)
        assert isinstance(s.updated_at, datetime)

    def test_custom_values(self) -> None:
        s = Skill(
            name="code-review",
            version="2.0.0",
            description="代码审查技能",
            content="# Review\n...",
            category=SkillCategory.PUBLIC,
            tags=["review", "quality"],
            applicable_agents=["reviewer-agent"],
            author="cky",
        )
        assert s.category == SkillCategory.PUBLIC
        assert s.tags == ["review", "quality"]
        assert s.applicable_agents == ["reviewer-agent"]


# ── SkillRegistry ────────────────────────────────────


class TestSkillRegistry:
    @pytest.fixture
    def registry(self) -> SkillRegistry:
        return SkillRegistry()

    @pytest.fixture
    def sample_skill(self) -> Skill:
        return Skill(name="demo", content="Demo skill content")

    @pytest.mark.asyncio
    async def test_register_and_get(self, registry: SkillRegistry, sample_skill: Skill) -> None:
        await registry.register(sample_skill)
        result = await registry.get("demo")
        assert result.name == "demo"
        assert result.content == "Demo skill content"

    @pytest.mark.asyncio
    async def test_get_not_found(self, registry: SkillRegistry) -> None:
        with pytest.raises(SkillNotFoundError, match="nonexistent"):
            await registry.get("nonexistent")

    @pytest.mark.asyncio
    async def test_register_duplicate_overwrites(self, registry: SkillRegistry) -> None:
        s1 = Skill(name="dup", version="1.0.0", content="v1")
        s2 = Skill(name="dup", version="2.0.0", content="v2")
        await registry.register(s1)
        await registry.register(s2)
        result = await registry.get("dup")
        assert result.version == "2.0.0"
        assert result.content == "v2"

    @pytest.mark.asyncio
    async def test_unregister(self, registry: SkillRegistry, sample_skill: Skill) -> None:
        await registry.register(sample_skill)
        await registry.unregister("demo")
        with pytest.raises(SkillNotFoundError):
            await registry.get("demo")

    @pytest.mark.asyncio
    async def test_unregister_not_found_is_noop(self, registry: SkillRegistry) -> None:
        """对不存在的 Skill 卸载是 no-op，不抛异常。"""
        await registry.unregister("nope")  # should not raise
        skills = await registry.list_skills()
        assert len(skills) == 0

    @pytest.mark.asyncio
    async def test_list_skills(self, registry: SkillRegistry) -> None:
        await registry.register(Skill(name="a", content="a"))
        await registry.register(Skill(name="b", content="b"))
        skills = await registry.list_skills()
        names = {s.name for s in skills}
        assert names == {"a", "b"}

    @pytest.mark.asyncio
    async def test_list_skills_by_category(self, registry: SkillRegistry) -> None:
        await registry.register(Skill(name="pub", content="p", category=SkillCategory.PUBLIC))
        await registry.register(Skill(name="cust", content="c", category=SkillCategory.CUSTOM))
        pub_skills = await registry.list_skills(category=SkillCategory.PUBLIC)
        assert len(pub_skills) == 1
        assert pub_skills[0].name == "pub"

    @pytest.mark.asyncio
    async def test_find_for_agent_all(self, registry: SkillRegistry) -> None:
        """applicable_agents 为空 → 适用所有 Agent。"""
        await registry.register(Skill(name="universal", content="u", applicable_agents=[]))
        result = await registry.find_for_agent("any-agent")
        assert len(result) == 1
        assert result[0].name == "universal"

    @pytest.mark.asyncio
    async def test_find_for_agent_specific(self, registry: SkillRegistry) -> None:
        """只匹配指定 Agent。"""
        await registry.register(Skill(name="specific", content="s", applicable_agents=["agent-a"]))
        assert len(await registry.find_for_agent("agent-a")) == 1
        assert len(await registry.find_for_agent("agent-b")) == 0

    @pytest.mark.asyncio
    async def test_find_for_agent_mixed(self, registry: SkillRegistry) -> None:
        await registry.register(Skill(name="all", content="a", applicable_agents=[]))
        await registry.register(Skill(name="only-x", content="x", applicable_agents=["x"]))
        await registry.register(Skill(name="only-y", content="y", applicable_agents=["y"]))
        result = await registry.find_for_agent("x")
        names = {s.name for s in result}
        assert names == {"all", "only-x"}


# ── SkillInjector ────────────────────────────────────


class TestSkillInjector:
    def test_format_empty(self) -> None:
        injector = SkillInjector()
        assert injector.format_for_injection([]) == ""

    def test_format_single_skill(self) -> None:
        injector = SkillInjector()
        s = Skill(name="demo", version="1.0.0", description="描述", content="内容")
        result = injector.format_for_injection([s])
        assert "## 已启用技能" in result
        assert "### demo (v1.0.0)" in result
        assert "*描述*" in result
        assert "内容" in result

    def test_format_multiple_skills(self) -> None:
        injector = SkillInjector()
        skills = [
            Skill(name="a", version="1.0", description="da", content="ca"),
            Skill(name="b", version="2.0", description="db", content="cb"),
        ]
        result = injector.format_for_injection(skills)
        assert "### a (v1.0)" in result
        assert "### b (v2.0)" in result

    def test_format_respects_token_budget(self) -> None:
        injector = SkillInjector(max_skill_tokens=50)
        skills = [
            Skill(name="big", version="1.0", description="d", content="x" * 2000),
        ]
        result = injector.format_for_injection(skills)
        # 注入文本应远短于原始内容（2000 x）
        assert len(result) < 2000
        # 内容必须被截断
        assert result.count("x") < 2000

    def test_custom_max_tokens(self) -> None:
        injector = SkillInjector(max_skill_tokens=100)
        assert injector._max_skill_tokens == 100


# ── Module exports ────────────────────────────────────


class TestModuleExports:
    def test_skills_package_exports(self) -> None:
        import kasaya.skills as mod
        assert hasattr(mod, "Skill")
        assert hasattr(mod, "SkillCategory")
        assert hasattr(mod, "SkillRegistry")
        assert hasattr(mod, "SkillNotFoundError")
        assert hasattr(mod, "SkillInjector")

    def test_top_level_exports(self) -> None:
        import kasaya
        assert hasattr(kasaya, "Skill")
        assert hasattr(kasaya, "SkillCategory")
        assert hasattr(kasaya, "SkillRegistry")
        assert hasattr(kasaya, "SkillNotFoundError")
        assert hasattr(kasaya, "SkillInjector")
