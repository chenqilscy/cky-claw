"""SkillFactory 测试 — Agent 自主创建技能的工厂。"""

from __future__ import annotations

import pytest

from kasaya.skills.factory import (
    CodeValidationError,
    InMemorySkillPersistence,
    SkillDefinition,
    SkillFactory,
    SkillFactoryError,
    _validate_code,
)
from kasaya.tools.function_tool import FunctionTool

# ==================== 代码验证测试 ====================


class TestCodeValidation:
    """AST 白名单代码验证。"""

    def test_valid_async_function(self) -> None:
        """正确的 async def 应通过验证。"""
        code = 'async def add(x: int, y: int) -> str:\n    return str(x + y)'
        _validate_code(code)  # 不应抛出

    def test_reject_sync_function(self) -> None:
        """同步函数应被拒绝（要求 async def）。"""
        code = 'def add(x: int, y: int) -> str:\n    return str(x + y)'
        with pytest.raises(CodeValidationError, match="async def"):
            _validate_code(code)

    def test_reject_multiple_functions(self) -> None:
        """多个函数定义应被拒绝。"""
        code = (
            'async def f1():\n    pass\n'
            'async def f2():\n    pass'
        )
        with pytest.raises(CodeValidationError, match="async def"):
            _validate_code(code)

    def test_reject_import(self) -> None:
        """import 语句应被拒绝。"""
        code = 'async def f():\n    import os\n    return "hi"'
        with pytest.raises(CodeValidationError, match="Import"):
            _validate_code(code)

    def test_reject_from_import(self) -> None:
        """from import 语句应被拒绝。"""
        code = 'async def f():\n    from pathlib import Path\n    return "hi"'
        with pytest.raises(CodeValidationError, match="Import"):
            _validate_code(code)

    def test_reject_eval(self) -> None:
        """eval 应被拒绝。"""
        code = 'async def f(s: str) -> str:\n    return eval(s)'
        with pytest.raises(CodeValidationError, match="eval"):
            _validate_code(code)

    def test_reject_exec(self) -> None:
        """exec 应被拒绝。"""
        code = 'async def f(s: str) -> str:\n    exec(s)\n    return "done"'
        with pytest.raises(CodeValidationError, match="exec"):
            _validate_code(code)

    def test_reject_dunder_attr(self) -> None:
        """双下划线属性访问应被拒绝。"""
        code = 'async def f():\n    return "".__class__'
        with pytest.raises(CodeValidationError, match="双下划线"):
            _validate_code(code)

    def test_reject_open(self) -> None:
        """open 应被拒绝。"""
        code = 'async def f():\n    return open("/etc/passwd")'
        with pytest.raises(CodeValidationError, match="open"):
            _validate_code(code)

    def test_reject_getattr(self) -> None:
        """getattr 应被拒绝。"""
        code = 'async def f():\n    return getattr(str, "join")'
        with pytest.raises(CodeValidationError, match="getattr"):
            _validate_code(code)

    def test_reject_code_too_long(self) -> None:
        """超长代码应被拒绝。"""
        code = 'async def f():\n    x = "' + "a" * 6000 + '"'
        with pytest.raises(CodeValidationError, match="超过上限"):
            _validate_code(code)

    def test_reject_syntax_error(self) -> None:
        """语法错误应被拒绝。"""
        code = 'async def f(:\n    pass'
        with pytest.raises(CodeValidationError, match="语法错误"):
            _validate_code(code)

    def test_valid_string_ops(self) -> None:
        """字符串操作应通过。"""
        code = (
            'async def process(text: str) -> str:\n'
            '    parts = text.split(",")\n'
            '    return ",".join(sorted(parts))'
        )
        _validate_code(code)

    def test_valid_list_comprehension(self) -> None:
        """列表推导应通过。"""
        code = (
            'async def squares(n: int) -> str:\n'
            '    return str([i ** 2 for i in range(n)])'
        )
        _validate_code(code)

    def test_valid_try_except(self) -> None:
        """try-except 应通过。"""
        code = (
            'async def safe_div(a: float, b: float) -> str:\n'
            '    try:\n'
            '        return str(a / b)\n'
            '    except Exception:\n'
            '        return "error"'
        )
        _validate_code(code)

    def test_valid_dict_operations(self) -> None:
        """字典操作应通过。"""
        code = (
            'async def merge(a: str, b: str) -> str:\n'
            '    d1 = json.loads(a)\n'
            '    d2 = json.loads(b)\n'
            '    d1.update(d2)\n'
            '    return json.dumps(d1)'
        )
        _validate_code(code)

    def test_reject_bare_expression(self) -> None:
        """顶层不是函数定义应被拒绝。"""
        code = 'x = 1'
        with pytest.raises(CodeValidationError, match="async def"):
            _validate_code(code)


# ==================== SkillFactory 核心测试 ====================


class TestSkillFactory:
    """SkillFactory 核心功能。"""

    @pytest.fixture()
    def factory(self) -> SkillFactory:
        """创建带内存持久化的工厂。"""
        return SkillFactory(
            persistence=InMemorySkillPersistence(),
            max_skills_per_agent=5,
        )

    @pytest.mark.asyncio
    async def test_create_simple_skill(self, factory: SkillFactory) -> None:
        """创建简单的加法技能。"""
        defn = SkillDefinition(
            name="add_numbers",
            description="将两个数字相加",
            code='async def add_numbers(x: int, y: int) -> str:\n    return str(x + y)',
            parameters_schema={
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        )

        tool = await factory.create_skill(defn, agent_name="test-agent")

        assert isinstance(tool, FunctionTool)
        assert tool.name == "add_numbers"
        assert tool.description == "将两个数字相加"
        assert tool.group == "agent-created:test-agent"

        # 实际执行
        result = await tool.execute({"x": 3, "y": 5})
        assert result == "8"

    @pytest.mark.asyncio
    async def test_create_with_test_cases(self, factory: SkillFactory) -> None:
        """带测试用例的技能创建。"""
        defn = SkillDefinition(
            name="reverse_text",
            description="反转文本字符串",
            code='async def reverse_text(text: str) -> str:\n    return text[::-1]',
            test_cases=[
                {"args": {"text": "hello"}, "expected_contains": "olleh"},
                {"args": {"text": "abc"}, "expected_contains": "cba"},
            ],
        )

        tool = await factory.create_skill(defn, agent_name="test-agent")
        assert tool.name == "reverse_text"

        result = await tool.execute({"text": "world"})
        assert result == "dlrow"

    @pytest.mark.asyncio
    async def test_failed_test_case(self, factory: SkillFactory) -> None:
        """测试用例失败应拒绝创建。"""
        defn = SkillDefinition(
            name="broken_tool",
            description="故意输出不匹配的工具",
            code='async def broken_tool(x: int) -> str:\n    return "wrong"',
            test_cases=[
                {"args": {"x": 1}, "expected_contains": "correct"},
            ],
        )

        with pytest.raises(SkillFactoryError, match="测试用例 #1 失败"):
            await factory.create_skill(defn, agent_name="test-agent")

    @pytest.mark.asyncio
    async def test_invalid_name(self, factory: SkillFactory) -> None:
        """无效名称应被拒绝。"""
        defn = SkillDefinition(
            name="Bad-Name!",
            description="名称格式错误",
            code='async def bad():\n    return "hi"',
        )

        with pytest.raises(SkillFactoryError, match="格式无效"):
            await factory.create_skill(defn, agent_name="test-agent")

    @pytest.mark.asyncio
    async def test_short_description(self, factory: SkillFactory) -> None:
        """描述过短应被拒绝。"""
        defn = SkillDefinition(
            name="short_desc",
            description="hi",
            code='async def short_desc():\n    return "hi"',
        )

        with pytest.raises(SkillFactoryError, match="描述过短"):
            await factory.create_skill(defn, agent_name="test-agent")

    @pytest.mark.asyncio
    async def test_max_skills_limit(self, factory: SkillFactory) -> None:
        """超过上限应被拒绝。"""
        for i in range(5):
            defn = SkillDefinition(
                name=f"skill_{i:03d}",
                description=f"技能 {i} 的描述",
                code=f'async def skill_{i:03d}() -> str:\n    return "ok"',
            )
            await factory.create_skill(defn, agent_name="test-agent")

        defn = SkillDefinition(
            name="skill_005",
            description="第 6 个技能超上限",
            code='async def skill_005() -> str:\n    return "ok"',
        )
        with pytest.raises(SkillFactoryError, match="已达技能上限"):
            await factory.create_skill(defn, agent_name="test-agent")

    @pytest.mark.asyncio
    async def test_update_existing_skill_bypasses_limit(self, factory: SkillFactory) -> None:
        """覆盖更新已有同名技能不应受上限限制。"""
        for i in range(5):
            defn = SkillDefinition(
                name=f"skill_{i:03d}",
                description=f"技能 {i} 的描述",
                code=f'async def skill_{i:03d}() -> str:\n    return "v1"',
            )
            await factory.create_skill(defn, agent_name="test-agent")

        # 覆盖更新 skill_000 应该成功（不是新增）
        defn = SkillDefinition(
            name="skill_000",
            description="更新版技能 0",
            code='async def skill_000() -> str:\n    return "v2"',
        )
        tool = await factory.create_skill(defn, agent_name="test-agent")
        result = await tool.execute({})
        assert result == "v2"

    @pytest.mark.asyncio
    async def test_unsafe_code_rejected(self, factory: SkillFactory) -> None:
        """不安全代码应在创建时被拒绝。"""
        defn = SkillDefinition(
            name="evil_tool",
            description="恶意工具试图导入 os",
            code='async def evil_tool():\n    import os\n    return os.listdir("/")',
        )

        with pytest.raises((SkillFactoryError, CodeValidationError)):
            await factory.create_skill(defn, agent_name="test-agent")


# ==================== 持久化测试 ====================


class TestSkillPersistence:
    """InMemorySkillPersistence 持久化。"""

    @pytest.fixture()
    def factory(self) -> SkillFactory:
        """共享持久化实例的工厂。"""
        return SkillFactory(
            persistence=InMemorySkillPersistence(),
        )

    @pytest.mark.asyncio
    async def test_persist_and_load(self, factory: SkillFactory) -> None:
        """创建后应可从持久化加载。"""
        defn = SkillDefinition(
            name="persisted_tool",
            description="可持久化的工具",
            code='async def persisted_tool(n: int) -> str:\n    return str(n * 2)',
        )
        await factory.create_skill(defn, agent_name="agent-a")

        # 新建工厂实例，但共享同一个持久化后端
        factory2 = SkillFactory(persistence=factory.persistence)
        tools = await factory2.load_agent_skills("agent-a")

        assert len(tools) == 1
        assert tools[0].name == "persisted_tool"

        result = await tools[0].execute({"n": 7})
        assert result == "14"

    @pytest.mark.asyncio
    async def test_delete_skill(self, factory: SkillFactory) -> None:
        """删除后应不再可加载。"""
        defn = SkillDefinition(
            name="temp_tool",
            description="临时工具将被删除",
            code='async def temp_tool() -> str:\n    return "temp"',
        )
        await factory.create_skill(defn, agent_name="agent-b")

        deleted = await factory.delete_skill("temp_tool", agent_name="agent-b")
        assert deleted is True

        tools = await factory.load_agent_skills("agent-b")
        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, factory: SkillFactory) -> None:
        """删除不存在的技能应返回 False。"""
        deleted = await factory.delete_skill("nonexistent", agent_name="agent-x")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_skills(self, factory: SkillFactory) -> None:
        """列出已创建的技能。"""
        for i in range(3):
            defn = SkillDefinition(
                name=f"list_tool_{i}",
                description=f"列表测试工具 {i}",
                code=f'async def list_tool_{i}() -> str:\n    return "{i}"',
            )
            await factory.create_skill(defn, agent_name="agent-c")

        skills = await factory.list_skills(agent_name="agent-c")
        assert len(skills) == 3
        names = {s.name for s in skills}
        assert names == {"list_tool_0", "list_tool_1", "list_tool_2"}

    @pytest.mark.asyncio
    async def test_agent_isolation(self, factory: SkillFactory) -> None:
        """不同 Agent 的技能互相隔离。"""
        defn_a = SkillDefinition(
            name="tool_alpha",
            description="Agent A 的工具",
            code='async def tool_alpha() -> str:\n    return "alpha"',
        )
        defn_b = SkillDefinition(
            name="tool_beta",
            description="Agent B 的工具",
            code='async def tool_beta() -> str:\n    return "beta"',
        )
        await factory.create_skill(defn_a, agent_name="agent-a")
        await factory.create_skill(defn_b, agent_name="agent-b")

        tools_a = await factory.load_agent_skills("agent-a")
        tools_b = await factory.load_agent_skills("agent-b")

        assert len(tools_a) == 1
        assert tools_a[0].name == "tool_alpha"
        assert len(tools_b) == 1
        assert tools_b[0].name == "tool_beta"


# ==================== 元工具测试 ====================


class TestBuildFactoryTool:
    """build_factory_tool 元工具测试。"""

    @pytest.fixture()
    def factory(self) -> SkillFactory:
        """工厂实例。"""
        return SkillFactory(
            persistence=InMemorySkillPersistence(),
        )

    def test_meta_tool_schema(self, factory: SkillFactory) -> None:
        """元工具的 schema 正确。"""
        tool = factory.build_factory_tool()

        assert tool.name == "create_skill_tool"
        assert "create" in tool.description.lower() or "创建" in tool.description
        assert tool.parameters_schema["type"] == "object"
        assert "skill_name" in tool.parameters_schema["properties"]
        assert "description" in tool.parameters_schema["properties"]
        assert "code" in tool.parameters_schema["properties"]

    @pytest.mark.asyncio
    async def test_meta_tool_create_success(self, factory: SkillFactory) -> None:
        """通过元工具创建技能应成功。"""
        tool = factory.build_factory_tool()

        result = await tool.execute({
            "skill_name": "multiply",
            "description": "将两个数字相乘",
            "code": 'async def multiply(a: int, b: int) -> str:\n    return str(a * b)',
            "agent_name": "meta-agent",
        })

        assert "成功" in result or "✅" in result

        # 验证实际创建
        created = await factory.get_skill_tool("multiply", agent_name="meta-agent")
        assert created is not None
        exec_result = await created.execute({"a": 4, "b": 5})
        assert exec_result == "20"

    @pytest.mark.asyncio
    async def test_meta_tool_create_failure(self, factory: SkillFactory) -> None:
        """通过元工具传入不安全代码应返回错误信息。"""
        tool = factory.build_factory_tool()

        result = await tool.execute({
            "skill_name": "evil",
            "description": "恶意工具试图导入 os",
            "code": 'async def evil():\n    import os\n    return "pwned"',
            "agent_name": "meta-agent",
        })

        assert "失败" in result or "❌" in result

    @pytest.mark.asyncio
    async def test_meta_tool_invalid_json(self, factory: SkillFactory) -> None:
        """无效 JSON 参数应返回友好错误。"""
        tool = factory.build_factory_tool()

        result = await tool.execute({
            "skill_name": "test_json",
            "description": "测试 JSON 解析",
            "code": 'async def test_json() -> str:\n    return "ok"',
            "parameters": "not-json{{",
            "agent_name": "meta-agent",
        })

        assert "JSON" in result


# ==================== 使用 json/re 内建测试 ====================


class TestSafeBuiltins:
    """验证安全 builtins 中的 json 和 re 可用。"""

    @pytest.fixture()
    def factory(self) -> SkillFactory:
        """工厂实例。"""
        return SkillFactory(persistence=InMemorySkillPersistence())

    @pytest.mark.asyncio
    async def test_json_usage(self, factory: SkillFactory) -> None:
        """技能中可使用 json 模块。"""
        defn = SkillDefinition(
            name="json_tool",
            description="JSON 序列化工具",
            code=(
                'async def json_tool(data: str) -> str:\n'
                '    obj = json.loads(data)\n'
                '    obj["processed"] = True\n'
                '    return json.dumps(obj)'
            ),
            test_cases=[
                {"args": {"data": '{"key": "val"}'}, "expected_contains": "processed"},
            ],
        )

        tool = await factory.create_skill(defn, agent_name="test")
        result = await tool.execute({"data": '{"x": 1}'})
        assert "processed" in result

    @pytest.mark.asyncio
    async def test_re_usage(self, factory: SkillFactory) -> None:
        """技能中可使用 re 模块。"""
        defn = SkillDefinition(
            name="regex_tool",
            description="正则表达式提取工具",
            code=(
                'async def regex_tool(text: str, pattern: str) -> str:\n'
                '    matches = re.findall(pattern, text)\n'
                '    return ",".join(matches)'
            ),
            test_cases=[
                {"args": {"text": "abc123def456", "pattern": r"\d+"}, "expected_contains": "123"},
            ],
        )

        tool = await factory.create_skill(defn, agent_name="test")
        result = await tool.execute({"text": "foo42bar99", "pattern": r"\d+"})
        assert "42" in result
        assert "99" in result
