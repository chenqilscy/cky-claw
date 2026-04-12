"""SkillFactory — Agent 自主创建技能的工厂。

用于在运行时让 Agent 动态创建 FunctionTool，并注册到 ToolRegistry。
安全机制：AST 白名单 + 受限 builtins + 代码长度限制 + 每 Agent 上限。
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ckyclaw_framework.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)

# ---------- 安全白名单 ----------

# 允许的 AST 节点类型（白名单模式）
_ALLOWED_AST_NODES: frozenset[type] = frozenset({
    # 模块/函数
    ast.Module, ast.AsyncFunctionDef, ast.FunctionDef,
    ast.arguments, ast.arg, ast.Return, ast.Pass,
    # 语句
    ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.For, ast.AsyncFor, ast.While, ast.If,
    ast.With, ast.AsyncWith,
    ast.Raise, ast.Try, ast.ExceptHandler,
    ast.Expr, ast.Break, ast.Continue,
    # 表达式
    ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Call, ast.keyword,
    ast.IfExp, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.comprehension,
    ast.Await, ast.YieldFrom, ast.Yield,
    ast.FormattedValue, ast.JoinedStr,
    # 下标/属性
    ast.Attribute, ast.Subscript, ast.Starred, ast.Name, ast.Slice,
    # 容器
    ast.List, ast.Tuple, ast.Set, ast.Dict,
    # 字面量
    ast.Constant, ast.NamedExpr,
    # 运算符
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv,
    ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd,
    ast.And, ast.Or, ast.Not, ast.Invert, ast.UAdd, ast.USub,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
    ast.In, ast.NotIn,
    # 加载/存储
    ast.Load, ast.Store, ast.Del,
    # 类型注解辅助
    ast.Nonlocal,
})

# 禁止的内置函数/属性名（黑名单补充）
_FORBIDDEN_NAMES: frozenset[str] = frozenset({
    "__import__", "eval", "exec", "compile", "execfile",
    "getattr", "setattr", "delattr", "globals", "locals",
    "vars", "dir", "type", "super", "classmethod", "staticmethod",
    "property", "memoryview", "bytearray", "breakpoint",
    "open", "input", "exit", "quit",
})

# 禁止的模块（import 检查）
_FORBIDDEN_MODULES: frozenset[str] = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib", "io",
    "socket", "http", "urllib", "requests", "aiohttp",
    "ctypes", "importlib", "pickle", "marshal", "shelve",
    "signal", "threading", "multiprocessing", "asyncio",
})

# 受限 builtins —— exec 环境中可用的安全内建函数
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "all": all, "any": any,
    "bool": bool, "chr": chr, "dict": dict,
    "enumerate": enumerate, "filter": filter,
    "float": float, "frozenset": frozenset,
    "hash": hash, "hex": hex, "int": int,
    "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list,
    "map": map, "max": max, "min": min,
    "next": next, "oct": oct, "ord": ord,
    "pow": pow, "print": print, "range": range,
    "repr": repr, "reversed": reversed, "round": round,
    "set": set, "slice": slice, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple,
    "zip": zip,
    # 常用模块
    "json": json, "re": re,
    # 异常
    "Exception": Exception, "ValueError": ValueError,
    "TypeError": TypeError, "KeyError": KeyError,
    "IndexError": IndexError, "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
    "True": True, "False": False, "None": None,
}

_SKILL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,49}$")
_MAX_CODE_LENGTH = 5000


class SkillFactoryError(Exception):
    """Skill Factory 相关错误。"""


class CodeValidationError(SkillFactoryError):
    """代码安全验证失败。"""


# ---------- 数据类 ----------


@dataclass
class SkillDefinition:
    """Agent 创建的技能定义。"""

    name: str
    """工具名（snake_case，3-50 字符）。"""

    description: str
    """功能描述。"""

    parameters_schema: dict[str, Any] = field(default_factory=dict)
    """JSON Schema 参数定义。"""

    code: str = ""
    """Python async 函数体（完整函数定义，必须以 async def 开头）。"""

    test_cases: list[dict[str, Any]] = field(default_factory=list)
    """验证用例 [{"args": {...}, "expected_contains": "..."}, ...]。"""

    agent_name: str = ""
    """创建此技能的 Agent 名称。"""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """创建时间。"""


# ---------- 持久化抽象 ----------


class SkillPersistence(ABC):
    """技能持久化抽象基类。"""

    @abstractmethod
    async def save(self, agent_name: str, definition: SkillDefinition) -> None:
        """保存技能定义。同名覆盖。"""

    @abstractmethod
    async def load(self, agent_name: str) -> list[SkillDefinition]:
        """加载指定 Agent 的所有自创建技能。"""

    @abstractmethod
    async def delete(self, agent_name: str, skill_name: str) -> bool:
        """删除技能。返回是否成功。"""

    @abstractmethod
    async def list_all(self, agent_name: str) -> list[SkillDefinition]:
        """列出指定 Agent 的技能（不含 code）。"""


class InMemorySkillPersistence(SkillPersistence):
    """内存持久化实现（测试用）。"""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, SkillDefinition]] = {}
        self._lock = asyncio.Lock()

    async def save(self, agent_name: str, definition: SkillDefinition) -> None:
        """保存技能定义。"""
        async with self._lock:
            if agent_name not in self._store:
                self._store[agent_name] = {}
            self._store[agent_name][definition.name] = definition

    async def load(self, agent_name: str) -> list[SkillDefinition]:
        """加载全部技能。"""
        async with self._lock:
            return list(self._store.get(agent_name, {}).values())

    async def delete(self, agent_name: str, skill_name: str) -> bool:
        """删除技能。"""
        async with self._lock:
            agent_skills = self._store.get(agent_name, {})
            if skill_name in agent_skills:
                del agent_skills[skill_name]
                return True
            return False

    async def list_all(self, agent_name: str) -> list[SkillDefinition]:
        """列出技能。"""
        return await self.load(agent_name)


# ---------- 代码验证 ----------


def _validate_code(code: str) -> None:
    """AST 白名单验证代码安全性。

    Args:
        code: 完整的 async def 函数定义字符串。

    Raises:
        CodeValidationError: 代码不安全时抛出。
    """
    if len(code) > _MAX_CODE_LENGTH:
        raise CodeValidationError(
            f"代码长度 {len(code)} 超过上限 {_MAX_CODE_LENGTH} 字符"
        )

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeValidationError(f"语法错误: {e}") from e

    # 必须是单个 async def
    if (
        len(tree.body) != 1
        or not isinstance(tree.body[0], ast.AsyncFunctionDef)
    ):
        raise CodeValidationError(
            "代码必须是且仅是一个 async def 函数定义"
        )

    # 遍历所有节点，白名单检查
    for node in ast.walk(tree):
        node_type = type(node)
        if node_type not in _ALLOWED_AST_NODES:
            raise CodeValidationError(
                f"禁止的语法结构: {node_type.__name__} (行 {getattr(node, 'lineno', '?')})"
            )

        # 检查 Name 节点是否引用禁止的内建
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise CodeValidationError(
                f"禁止使用: {node.id} (行 {node.lineno})"
            )

        # 检查 import（不在白名单中，但为显式错误信息做二次检查）
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise CodeValidationError(
                f"禁止使用 import 语句 (行 {node.lineno})"
            )

        # 检查属性访问中的魔法方法
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise CodeValidationError(
                f"禁止访问双下划线属性: {node.attr} (行 {node.lineno})"
            )


def _compile_skill_function(code: str) -> Any:
    """在受限环境中编译并执行代码，返回函数对象。

    Args:
        code: 已验证的 async def 函数字符串。

    Returns:
        编译后的 async 函数对象。

    Raises:
        SkillFactoryError: 编译失败。
    """
    _validate_code(code)

    namespace: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
    try:
        compiled = compile(code, "<skill>", "exec")
        exec(compiled, namespace)  # noqa: S102
    except Exception as e:
        raise SkillFactoryError(f"技能编译失败: {e}") from e

    # 找到定义的函数
    func_name: str | None = None
    for key, val in namespace.items():
        if key != "__builtins__" and callable(val):
            func_name = key
            break

    if func_name is None:
        raise SkillFactoryError("技能代码中未找到可调用函数")

    return namespace[func_name]


# ---------- SkillFactory 核心 ----------


@dataclass
class SkillFactory:
    """Agent 自主创建技能的工厂。

    安全机制：
    - AST 白名单验证（仅允许安全语法节点）
    - 受限 builtins（无 open/eval/exec/__import__）
    - 代码长度限制（5000 字符）
    - 每 Agent 技能上限
    - 可选沙箱执行测试用例
    """

    persistence: SkillPersistence | None = None
    """持久化后端。None 表示仅内存不持久化。"""

    max_skills_per_agent: int = 50
    """每个 Agent 最多创建的技能数。"""

    _runtime_skills: dict[str, dict[str, FunctionTool]] = field(
        default_factory=dict, repr=False,
    )
    """运行时缓存: {agent_name: {skill_name: FunctionTool}}。"""

    async def create_skill(
        self,
        definition: SkillDefinition,
        *,
        agent_name: str,
    ) -> FunctionTool:
        """创建新技能。

        流程：验证名称 → 验证代码 → 编译 → 运行测试 → 注册 → 持久化。

        Args:
            definition: 技能定义。
            agent_name: 创建者 Agent 名称。

        Returns:
            创建的 FunctionTool。

        Raises:
            SkillFactoryError: 名称/代码/测试验证失败时抛出。
        """
        # 名称格式校验
        if not _SKILL_NAME_PATTERN.match(definition.name):
            raise SkillFactoryError(
                f"技能名 '{definition.name}' 格式无效（要求：小写字母开头，3-50 字符，"
                "仅含小写字母/数字/下划线）"
            )

        # 描述必须有内容
        if not definition.description or len(definition.description.strip()) < 5:
            raise SkillFactoryError("技能描述过短（至少 5 个字符）")

        # 数量上限检查（同名覆盖不算新增）
        agent_skills = self._runtime_skills.get(agent_name, {})
        is_update = definition.name in agent_skills
        if not is_update and len(agent_skills) >= self.max_skills_per_agent:
            raise SkillFactoryError(
                f"Agent '{agent_name}' 已达技能上限 {self.max_skills_per_agent}"
            )

        # 编译代码
        fn = _compile_skill_function(definition.code)

        # 运行测试用例
        for i, case in enumerate(definition.test_cases):
            args = case.get("args", {})
            expected = case.get("expected_contains", "")
            try:
                result = await fn(**args)
                result_str = str(result)
                if expected and expected not in result_str:
                    raise SkillFactoryError(
                        f"测试用例 #{i + 1} 失败: 结果 '{result_str}' "
                        f"不包含预期 '{expected}'"
                    )
            except SkillFactoryError:
                raise
            except Exception as e:
                raise SkillFactoryError(
                    f"测试用例 #{i + 1} 执行异常: {e}"
                ) from e

        # 构建 FunctionTool
        tool = FunctionTool(
            name=definition.name,
            description=definition.description,
            fn=fn,
            parameters_schema=definition.parameters_schema or {"type": "object", "properties": {}},
            group=f"agent-created:{agent_name}",
        )

        # 注册到运行时缓存
        if agent_name not in self._runtime_skills:
            self._runtime_skills[agent_name] = {}
        self._runtime_skills[agent_name][definition.name] = tool

        # 持久化
        definition.agent_name = agent_name
        if self.persistence is not None:
            await self.persistence.save(agent_name, definition)

        logger.info(
            "Agent '%s' 创建技能 '%s' 成功",
            agent_name, definition.name,
        )
        return tool

    async def load_agent_skills(self, agent_name: str) -> list[FunctionTool]:
        """从持久化后端加载 Agent 的自创建技能。

        Args:
            agent_name: Agent 名称。

        Returns:
            加载成功的 FunctionTool 列表。跳过编译失败的技能。
        """
        if self.persistence is None:
            return list(self._runtime_skills.get(agent_name, {}).values())

        definitions = await self.persistence.load(agent_name)
        tools: list[FunctionTool] = []

        for defn in definitions:
            try:
                fn = _compile_skill_function(defn.code)
                tool = FunctionTool(
                    name=defn.name,
                    description=defn.description,
                    fn=fn,
                    parameters_schema=defn.parameters_schema or {"type": "object", "properties": {}},
                    group=f"agent-created:{agent_name}",
                )
                if agent_name not in self._runtime_skills:
                    self._runtime_skills[agent_name] = {}
                self._runtime_skills[agent_name][defn.name] = tool
                tools.append(tool)
            except (SkillFactoryError, CodeValidationError) as e:
                logger.warning(
                    "加载技能 '%s' 失败（Agent '%s'）: %s",
                    defn.name, agent_name, e,
                )

        return tools

    async def delete_skill(self, name: str, *, agent_name: str) -> bool:
        """删除技能。

        Args:
            name: 技能名称。
            agent_name: Agent 名称。

        Returns:
            是否成功删除。
        """
        # 从运行时缓存移除
        agent_skills = self._runtime_skills.get(agent_name, {})
        removed = agent_skills.pop(name, None) is not None

        # 从持久化层移除
        if self.persistence is not None:
            removed = await self.persistence.delete(agent_name, name) or removed

        if removed:
            logger.info("Agent '%s' 删除技能 '%s'", agent_name, name)

        return removed

    async def list_skills(self, *, agent_name: str) -> list[SkillDefinition]:
        """列出 Agent 已创建的技能。

        Args:
            agent_name: Agent 名称。

        Returns:
            技能定义列表。
        """
        if self.persistence is not None:
            return await self.persistence.list_all(agent_name)
        # 无持久化时，从运行时缓存构造
        cache = self._runtime_skills.get(agent_name, {})
        return [
            SkillDefinition(
                name=tool.name,
                description=tool.description,
                parameters_schema=tool.parameters_schema,
                agent_name=agent_name,
            )
            for tool in cache.values()
        ]

    async def get_skill_tool(self, name: str, *, agent_name: str) -> FunctionTool | None:
        """获取运行时缓存中的技能工具。

        Args:
            name: 技能名称。
            agent_name: Agent 名称。

        Returns:
            FunctionTool 或 None。
        """
        return self._runtime_skills.get(agent_name, {}).get(name)

    def build_factory_tool(self) -> FunctionTool:
        """构建元工具 create_skill_tool，供 Agent 直接调用以创建新技能。

        Returns:
            FunctionTool 实例（元工具）。
        """
        factory = self

        async def create_skill_tool(
            skill_name: str,
            description: str,
            code: str,
            parameters: str = "{}",
            test_input: str = "{}",
            agent_name: str = "default",
        ) -> str:
            """创建新技能工具。Agent 可调用此函数动态创建可复用的工具。

            Args:
                skill_name: 技能名（snake_case，3-50 字符）。
                description: 技能功能描述（至少 5 个字符）。
                code: 完整的 async def 函数定义（Python 代码）。
                parameters: JSON Schema 参数定义（JSON 字符串）。
                test_input: 测试输入参数（JSON 字符串，可选）。
                agent_name: 创建者 Agent 名称。
            """
            try:
                params_schema = json.loads(parameters) if parameters else {}
            except json.JSONDecodeError:
                return "错误：parameters 不是有效 JSON"

            test_cases: list[dict[str, Any]] = []
            if test_input and test_input != "{}":
                try:
                    test_args = json.loads(test_input)
                    test_cases.append({"args": test_args})
                except json.JSONDecodeError:
                    return "错误：test_input 不是有效 JSON"

            defn = SkillDefinition(
                name=skill_name,
                description=description,
                parameters_schema=params_schema,
                code=code,
                test_cases=test_cases,
            )

            try:
                tool = await factory.create_skill(defn, agent_name=agent_name)
                return (
                    f"✅ 技能 '{tool.name}' 创建成功。\n"
                    f"描述: {tool.description}\n"
                    f"工具组: {tool.group}\n"
                    f"参数: {json.dumps(tool.parameters_schema, ensure_ascii=False)}"
                )
            except (SkillFactoryError, CodeValidationError) as e:
                return f"❌ 技能创建失败: {e}"

        return FunctionTool(
            name="create_skill_tool",
            description=(
                "创建新的可复用技能工具。传入技能名称、描述、Python async def 函数代码和参数定义。"
                "创建后的技能可在后续对话中复用。代码必须是单个 async def 函数定义，"
                "禁止 import/eval/exec/open 等不安全操作。"
            ),
            fn=create_skill_tool,
            parameters_schema={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "技能名称（snake_case，3-50 字符，小写字母开头）",
                    },
                    "description": {
                        "type": "string",
                        "description": "技能功能描述（至少 5 个字符）",
                    },
                    "code": {
                        "type": "string",
                        "description": (
                            "完整的 Python async def 函数定义。"
                            "例如: async def my_tool(x: int, y: int) -> str:\\n    return str(x + y)"
                        ),
                    },
                    "parameters": {
                        "type": "string",
                        "description": "JSON Schema 参数定义（JSON 字符串），可选",
                        "default": "{}",
                    },
                    "test_input": {
                        "type": "string",
                        "description": "测试输入参数（JSON 字符串），可选",
                        "default": "{}",
                    },
                    "agent_name": {
                        "type": "string",
                        "description": "创建者 Agent 名称",
                        "default": "default",
                    },
                },
                "required": ["skill_name", "description", "code"],
            },
            group="skill-factory",
        )
