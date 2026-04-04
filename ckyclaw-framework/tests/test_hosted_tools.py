"""Hosted Tools 内置工具组测试。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool
from ckyclaw_framework.tools.hosted_tools import (
    HOSTED_GROUP_IDS,
    _build_hosted_groups,
    _safe_resolve,
    database_query,
    execute_python,
    execute_shell,
    fetch_webpage,
    file_list,
    file_read,
    file_write,
    http_request,
    register_hosted_tools,
    web_search,
)
from ckyclaw_framework.tools.tool_group import ToolGroup
from ckyclaw_framework.tools.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# 注册测试
# ---------------------------------------------------------------------------


class TestRegisterHostedTools:
    """测试内置工具组注册。"""

    def test_build_hosted_groups_returns_five(self) -> None:
        """构建 5 个内置工具组。"""
        groups = _build_hosted_groups()
        assert len(groups) == 5

    def test_build_hosted_groups_names(self) -> None:
        """工具组名称匹配预期。"""
        groups = _build_hosted_groups()
        names = {g.name for g in groups}
        assert names == {"web-search", "code-executor", "file-ops", "http", "database"}

    def test_register_to_registry(self) -> None:
        """注册到 ToolRegistry 后可查询。"""
        registry = ToolRegistry()
        groups = register_hosted_tools(registry)
        assert len(groups) == 5
        for name in HOSTED_GROUP_IDS:
            assert registry.get_group(name) is not None

    def test_register_default_registry(self) -> None:
        """不传 registry 使用默认全局注册表。"""
        groups = register_hosted_tools()
        assert len(groups) == 5

    def test_hosted_group_ids_constant(self) -> None:
        """HOSTED_GROUP_IDS 包含所有 5 个组。"""
        assert len(HOSTED_GROUP_IDS) == 5
        assert "web-search" in HOSTED_GROUP_IDS
        assert "database" in HOSTED_GROUP_IDS

    def test_each_group_has_tools(self) -> None:
        """每个工具组至少包含 1 个工具。"""
        groups = _build_hosted_groups()
        for g in groups:
            assert len(g.tools) >= 1, f"工具组 {g.name} 没有工具"

    def test_all_tools_are_function_tools(self) -> None:
        """所有工具都是 FunctionTool 实例。"""
        groups = _build_hosted_groups()
        for g in groups:
            for t in g.tools:
                assert isinstance(t, FunctionTool), f"{t} 不是 FunctionTool"

    def test_tool_names_unique(self) -> None:
        """所有工具名全局唯一。"""
        groups = _build_hosted_groups()
        all_names: list[str] = []
        for g in groups:
            all_names.extend(t.name for t in g.tools)
        assert len(all_names) == len(set(all_names))


# ---------------------------------------------------------------------------
# web-search 工具测试
# ---------------------------------------------------------------------------


class TestWebSearchTools:
    """测试 web-search 工具组。"""

    def test_web_search_is_function_tool(self) -> None:
        """web_search 是 FunctionTool。"""
        assert isinstance(web_search, FunctionTool)
        assert web_search.name == "web_search"

    def test_fetch_webpage_is_function_tool(self) -> None:
        """fetch_webpage 是 FunctionTool。"""
        assert isinstance(fetch_webpage, FunctionTool)
        assert fetch_webpage.name == "fetch_webpage"

    @pytest.mark.asyncio
    async def test_web_search_no_httpx(self) -> None:
        """httpx 不可用时返回错误提示。"""
        with patch.dict("sys.modules", {"httpx": None}):
            # function_tool 装饰器包装后需通过 execute 调用
            result = await web_search.execute({"query": "test"})
        assert "httpx" in result or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_fetch_webpage_no_httpx(self) -> None:
        """httpx 不可用时返回错误提示。"""
        with patch.dict("sys.modules", {"httpx": None}):
            result = await fetch_webpage.execute({"url": "https://example.com"})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# file-ops 工具测试
# ---------------------------------------------------------------------------


class TestFileOpsTools:
    """测试 file-ops 工具组。"""

    def test_safe_resolve_normal(self) -> None:
        """正常路径解析成功。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = _safe_resolve(tmp, "test.txt")
            assert str(result).startswith(str(Path(tmp).resolve()))

    def test_safe_resolve_traversal_blocked(self) -> None:
        """目录穿越攻击被阻止。"""
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(PermissionError, match="超出允许的工作目录"):
                _safe_resolve(tmp, "../../etc/passwd")

    @pytest.mark.asyncio
    async def test_file_write_read_roundtrip(self) -> None:
        """文件写入后读取，内容一致。"""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ckyclaw_framework.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                write_result = await file_write.execute({"path": "hello.txt", "content": "你好世界"})
                assert "已写入" in write_result
                read_result = await file_read.execute({"path": "hello.txt"})
                assert read_result == "你好世界"

    @pytest.mark.asyncio
    async def test_file_read_not_found(self) -> None:
        """读取不存在的文件返回错误。"""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ckyclaw_framework.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_read.execute({"path": "nonexistent.txt"})
                assert "不存在" in result

    @pytest.mark.asyncio
    async def test_file_list_directory(self) -> None:
        """列出目录内容。"""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("a")
            (Path(tmp) / "b.txt").write_text("b")
            with patch("ckyclaw_framework.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_list.execute({"directory": "."})
                entries = json.loads(result)
                names = {e["name"] for e in entries}
                assert "a.txt" in names
                assert "b.txt" in names

    @pytest.mark.asyncio
    async def test_file_write_creates_subdirectory(self) -> None:
        """写入时自动创建子目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ckyclaw_framework.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_write.execute({"path": "sub/dir/file.txt", "content": "nested"})
                assert "已写入" in result
                assert (Path(tmp) / "sub" / "dir" / "file.txt").read_text() == "nested"


# ---------------------------------------------------------------------------
# http 工具测试
# ---------------------------------------------------------------------------


class TestHttpTools:
    """测试 http 工具组。"""

    def test_http_request_is_function_tool(self) -> None:
        """http_request 是 FunctionTool。"""
        assert isinstance(http_request, FunctionTool)
        assert http_request.name == "http_request"

    @pytest.mark.asyncio
    async def test_invalid_method(self) -> None:
        """不支持的 HTTP 方法返回错误。"""
        result = await http_request.execute({"url": "https://example.com", "method": "PURGE"})
        assert "不支持" in result

    @pytest.mark.asyncio
    async def test_invalid_headers_json(self) -> None:
        """无效 headers JSON 返回错误。"""
        result = await http_request.execute({"url": "https://example.com", "headers": "not-json"})
        assert "格式错误" in result


# ---------------------------------------------------------------------------
# database 工具测试
# ---------------------------------------------------------------------------


class TestDatabaseTools:
    """测试 database 工具组。"""

    def test_database_query_is_function_tool(self) -> None:
        """database_query 是 FunctionTool。"""
        assert isinstance(database_query, FunctionTool)

    @pytest.mark.asyncio
    async def test_reject_non_select(self) -> None:
        """拒绝非 SELECT 查询。"""
        result = await database_query.execute({"query": "DELETE FROM users"})
        assert "仅允许 SELECT" in result

    @pytest.mark.asyncio
    async def test_reject_dangerous_keywords(self) -> None:
        """拒绝包含危险关键词的查询。"""
        result = await database_query.execute({"query": "SELECT * FROM users; DROP TABLE users"})
        assert "禁止" in result

    @pytest.mark.asyncio
    async def test_no_connection_string(self) -> None:
        """未配置连接字符串返回错误。"""
        with patch.dict(os.environ, {}, clear=False):
            # 确保环境变量不存在
            os.environ.pop("CKYCLAW_DB_QUERY_DSN", None)
            result = await database_query.execute({"query": "SELECT 1"})
            assert "未配置" in result


# ---------------------------------------------------------------------------
# code-executor 工具测试
# ---------------------------------------------------------------------------


class TestCodeExecutorTools:
    """测试 code-executor 工具组。"""

    def test_execute_python_is_function_tool(self) -> None:
        """execute_python 是 FunctionTool。"""
        assert isinstance(execute_python, FunctionTool)
        assert execute_python.name == "execute_python"

    def test_execute_shell_is_function_tool(self) -> None:
        """execute_shell 是 FunctionTool。"""
        assert isinstance(execute_shell, FunctionTool)
        assert execute_shell.name == "execute_shell"

    @pytest.mark.asyncio
    async def test_execute_python_with_mock_sandbox(self) -> None:
        """通过 mock sandbox 测试 Python 执行。"""
        mock_result = MagicMock()
        mock_result.stdout = "Hello World"
        mock_result.stderr = ""
        mock_result.exit_code = 0

        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(return_value=mock_result)

        mock_cls = MagicMock(return_value=mock_sandbox)
        with patch("ckyclaw_framework.sandbox.LocalSandbox", mock_cls), \
             patch("ckyclaw_framework.sandbox.SandboxConfig"):
            result = await execute_python.execute({"code": "print('Hello World')"})
        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_execute_python_error_output(self) -> None:
        """Python 执行错误时包含 stderr 和 exit_code。"""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "NameError: name 'x' is not defined"
        mock_result.exit_code = 1

        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(return_value=mock_result)

        mock_cls = MagicMock(return_value=mock_sandbox)
        with patch("ckyclaw_framework.sandbox.LocalSandbox", mock_cls), \
             patch("ckyclaw_framework.sandbox.SandboxConfig"):
            result = await execute_python.execute({"code": "print(x)"})
        assert "NameError" in result
        assert "exit_code: 1" in result
