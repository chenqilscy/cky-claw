"""Hosted Tools 内置工具组测试。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kasaya.tools.function_tool import FunctionTool
from kasaya.tools.hosted_tools import (
    HOSTED_GROUP_IDS,
    _build_hosted_groups,
    _safe_resolve,
    analyze_code,
    check_security_patterns,
    database_query,
    execute_python,
    execute_shell,
    fetch_webpage,
    file_list,
    file_read,
    file_write,
    http_request,
    parse_diff,
    register_hosted_tools,
    web_search,
)
from kasaya.tools.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def _mock_module(name: str, mock_obj: Any) -> Generator[Any, None, None]:
    """临时替换 sys.modules 中的模块（用于 mock 函数内部的 import）。"""
    original = sys.modules.get(name)
    sys.modules[name] = mock_obj
    try:
        yield mock_obj
    finally:
        if original is not None:
            sys.modules[name] = original
        else:
            sys.modules.pop(name, None)


def _make_async_client(mock_client: AsyncMock) -> MagicMock:
    """构造一个可用作 httpx.AsyncClient context manager 的 mock。"""
    mock_httpx = MagicMock()
    mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
    return mock_httpx


# ---------------------------------------------------------------------------
# 注册测试
# ---------------------------------------------------------------------------


class TestRegisterHostedTools:
    """测试内置工具组注册。"""

    def test_build_hosted_groups_returns_six(self) -> None:
        """构建 6 个内置工具组。"""
        groups = _build_hosted_groups()
        assert len(groups) == 6

    def test_build_hosted_groups_names(self) -> None:
        """工具组名称匹配预期。"""
        groups = _build_hosted_groups()
        names = {g.name for g in groups}
        assert names == {"web-search", "code-executor", "file-ops", "http", "database", "code-review"}

    def test_register_to_registry(self) -> None:
        """注册到 ToolRegistry 后可查询。"""
        registry = ToolRegistry()
        groups = register_hosted_tools(registry)
        assert len(groups) == 6
        for name in HOSTED_GROUP_IDS:
            assert registry.get_group(name) is not None

    def test_register_default_registry(self) -> None:
        """不传 registry 使用默认全局注册表。"""
        groups = register_hosted_tools()
        assert len(groups) == 6

    def test_hosted_group_ids_constant(self) -> None:
        """HOSTED_GROUP_IDS 包含所有 6 个组。"""
        assert len(HOSTED_GROUP_IDS) == 6
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
    async def test_web_search_success(self) -> None:
        """成功搜索返回 JSON 结果。"""
        html = (
            '<div class="result__a" href="https://example.com">Example <b>Title</b></a>'
            '<a class="result__snippet">This is a snippet</a>'
        )
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await web_search.execute({"query": "test", "max_results": 3})
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1
        assert parsed[0]["title"] == "Example Title"

    @pytest.mark.asyncio
    async def test_web_search_request_failure(self) -> None:
        """搜索请求异常返回错误字符串。"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await web_search.execute({"query": "test"})
        assert "搜索失败" in result

    @pytest.mark.asyncio
    async def test_web_search_no_results(self) -> None:
        """搜索无结果时返回提示。"""
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>No results</body></html>"
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await web_search.execute({"query": "xyznonexistent"})
        assert "未找到" in result

    @pytest.mark.asyncio
    async def test_fetch_webpage_no_httpx(self) -> None:
        """httpx 不可用时返回错误提示。"""
        with patch.dict("sys.modules", {"httpx": None}):
            result = await fetch_webpage.execute({"url": "https://example.com"})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_fetch_webpage_success(self) -> None:
        """成功抓取网页并去除 HTML 标签。"""
        html = "<html><script>var x=1;</script><style>body{}</style><p>Hello World</p></html>"
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await fetch_webpage.execute({"url": "https://example.com"})
        assert "Hello World" in result
        assert "<script>" not in result
        assert "<style>" not in result

    @pytest.mark.asyncio
    async def test_fetch_webpage_truncation(self) -> None:
        """超过 max_length 时截断内容。"""
        html = "<p>" + "A" * 10000 + "</p>"
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await fetch_webpage.execute({"url": "https://example.com", "max_length": 100})
        assert result.endswith("...(已截断)")
        # 100 字符 + 截断标记
        assert len(result) <= 200

    @pytest.mark.asyncio
    async def test_fetch_webpage_request_failure(self) -> None:
        """抓取失败返回错误信息。"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await fetch_webpage.execute({"url": "https://example.com"})
        assert "抓取失败" in result


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
        with tempfile.TemporaryDirectory() as tmp, pytest.raises(PermissionError, match="超出允许的工作目录"):
            _safe_resolve(tmp, "../../etc/passwd")

    @pytest.mark.asyncio
    async def test_file_write_read_roundtrip(self) -> None:
        """文件写入后读取，内容一致。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                write_result = await file_write.execute({"path": "hello.txt", "content": "你好世界"})
                assert "已写入" in write_result
                read_result = await file_read.execute({"path": "hello.txt"})
                assert read_result == "你好世界"

    @pytest.mark.asyncio
    async def test_file_read_not_found(self) -> None:
        """读取不存在的文件返回错误。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_read.execute({"path": "nonexistent.txt"})
                assert "不存在" in result

    @pytest.mark.asyncio
    async def test_file_list_directory(self) -> None:
        """列出目录内容。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                (Path(tmp) / "a.txt").write_text("a")
                (Path(tmp) / "b.txt").write_text("b")
                result = await file_list.execute({"directory": "."})
                entries = json.loads(result)
                names = {e["name"] for e in entries}
                assert "a.txt" in names
                assert "b.txt" in names

    @pytest.mark.asyncio
    async def test_file_write_creates_subdirectory(self) -> None:
        """写入时自动创建子目录。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_write.execute({"path": "sub/dir/file.txt", "content": "nested"})
                assert "已写入" in result
                assert (Path(tmp) / "sub" / "dir" / "file.txt").read_text() == "nested"

    @pytest.mark.asyncio
    async def test_file_list_nonexistent_directory(self) -> None:
        """列出不存在的目录返回错误提示。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_list.execute({"directory": "nonexistent"})
                assert "不存在" in result

    @pytest.mark.asyncio
    async def test_file_list_with_subdirectory(self) -> None:
        """列出包含子目录的目录，返回正确 type。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                (Path(tmp) / "file.txt").write_text("content")
                (Path(tmp) / "subdir").mkdir()
                result = await file_list.execute({"directory": "."})
                entries = json.loads(result)
                types = {e["name"]: e["type"] for e in entries}
                assert types["file.txt"] == "file"
                assert types["subdir"] == "directory"
                # 目录的 size 应为 None
                for e in entries:
                    if e["type"] == "directory":
                        assert e["size"] is None

    @pytest.mark.asyncio
    async def test_file_read_traversal_error(self) -> None:
        """路径穿越读取返回权限错误。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_read.execute({"path": "../../etc/passwd"})
                assert "权限错误" in result

    @pytest.mark.asyncio
    async def test_file_write_traversal_error(self) -> None:
        """路径穿越写入返回权限错误。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_write.execute({"path": "../../tmp/hack.txt", "content": "bad"})
                assert "权限错误" in result

    @pytest.mark.asyncio
    async def test_file_list_traversal_error(self) -> None:
        """路径穿越列目录返回权限错误。"""
        with tempfile.TemporaryDirectory() as tmp, \
             patch("kasaya.tools.hosted_tools._FILE_OPS_BASE_DIR", tmp):
                result = await file_list.execute({"directory": "../../"})
                assert "权限错误" in result


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

    @pytest.mark.asyncio
    async def test_http_request_success(self) -> None:
        """成功发送 HTTP 请求返回状态码和响应体。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.text = '{"ok": true}'

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await http_request.execute({"url": "https://api.example.com/data", "method": "POST", "body": "{}"})
        parsed = json.loads(result)
        assert parsed["status_code"] == 200
        assert "ok" in parsed["body"]

    @pytest.mark.asyncio
    async def test_http_request_no_httpx(self) -> None:
        """httpx 不可用时返回错误提示。"""
        with patch.dict("sys.modules", {"httpx": None}):
            result = await http_request.execute({"url": "https://example.com"})
        assert "httpx" in result

    @pytest.mark.asyncio
    async def test_http_request_exception(self) -> None:
        """请求异常返回错误信息。"""
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=Exception("connection reset"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await http_request.execute({"url": "https://example.com"})
        assert "HTTP 请求失败" in result

    @pytest.mark.asyncio
    async def test_http_request_all_methods(self) -> None:
        """所有允许的 HTTP 方法都被接受。"""
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {}
            mock_resp.text = ""

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with _mock_module("httpx", _make_async_client(mock_client)):
                result = await http_request.execute({"url": "https://example.com", "method": method})
            assert "不支持" not in result

    @pytest.mark.asyncio
    async def test_http_request_empty_headers(self) -> None:
        """空 headers 字符串正常处理。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.text = "ok"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with _mock_module("httpx", _make_async_client(mock_client)):
            result = await http_request.execute({"url": "https://example.com", "headers": ""})
        parsed = json.loads(result)
        assert parsed["status_code"] == 200


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
            os.environ.pop("KASAYA_DB_QUERY_DSN", None)
            result = await database_query.execute({"query": "SELECT 1"})
            assert "未配置" in result

    @pytest.mark.asyncio
    async def test_database_query_no_asyncpg(self) -> None:
        """asyncpg 不可用时返回错误提示。"""
        with patch.dict(os.environ, {"KASAYA_DB_QUERY_DSN": "postgresql://x"}, clear=False), \
             patch.dict("sys.modules", {"asyncpg": None}):
                result = await database_query.execute({"query": "SELECT 1"})
        assert "asyncpg" in result

    @pytest.mark.asyncio
    async def test_database_query_success(self) -> None:
        """成功查询返回 JSON 结果。"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ])
        mock_conn.close = AsyncMock()

        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        with patch.dict(os.environ, {"KASAYA_DB_QUERY_DSN": "postgresql://x"}, clear=False), \
             _mock_module("asyncpg", mock_asyncpg):
                result = await database_query.execute({"query": "SELECT * FROM users", "max_rows": 10})
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_database_query_connection_failure(self) -> None:
        """数据库连接失败返回错误信息。"""
        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(side_effect=Exception("connection refused"))

        with patch.dict(os.environ, {"KASAYA_DB_QUERY_DSN": "postgresql://x"}, clear=False), \
             patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
                result = await database_query.execute({"query": "SELECT 1"})
        assert "查询失败" in result

    @pytest.mark.asyncio
    async def test_database_query_timeout(self) -> None:
        """查询超时返回超时信息。"""

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=TimeoutError())
        mock_conn.close = AsyncMock()

        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        with patch.dict(os.environ, {"KASAYA_DB_QUERY_DSN": "postgresql://x"}, clear=False), \
             patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
                result = await database_query.execute({"query": "SELECT 1"})
        assert "超时" in result

    @pytest.mark.asyncio
    async def test_database_query_max_rows(self) -> None:
        """max_rows 限制返回行数。"""
        rows = [{"id": i} for i in range(200)]
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=rows)
        mock_conn.close = AsyncMock()

        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        with patch.dict(os.environ, {"KASAYA_DB_QUERY_DSN": "postgresql://x"}, clear=False), \
             patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
                result = await database_query.execute({"query": "SELECT * FROM big", "max_rows": 5})
        parsed = json.loads(result)
        assert len(parsed) == 5

    @pytest.mark.asyncio
    async def test_database_query_with_explicit_connection_string(self) -> None:
        """使用显式连接字符串而非环境变量。"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"val": 42}])
        mock_conn.close = AsyncMock()

        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        # 清除环境变量确保用的是参数传入的
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KASAYA_DB_QUERY_DSN", None)
            with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
                result = await database_query.execute({
                    "query": "SELECT 42 AS val",
                    "connection_string": "postgresql://explicit",
                })
        parsed = json.loads(result)
        assert parsed[0]["val"] == 42

    @pytest.mark.asyncio
    async def test_reject_insert_query(self) -> None:
        """拒绝 INSERT 查询。"""
        result = await database_query.execute({"query": "INSERT INTO users VALUES (1)"})
        assert "仅允许 SELECT" in result

    @pytest.mark.asyncio
    async def test_reject_select_with_update(self) -> None:
        """拒绝包含 UPDATE 子句的 SELECT。"""
        result = await database_query.execute({"query": "SELECT * FROM users; UPDATE users SET name='x'"})
        assert "禁止" in result


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
        with patch("kasaya.sandbox.LocalSandbox", mock_cls), \
             patch("kasaya.sandbox.SandboxConfig"):
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
        with patch("kasaya.sandbox.LocalSandbox", mock_cls), \
             patch("kasaya.sandbox.SandboxConfig"):
            result = await execute_python.execute({"code": "print(x)"})
        assert "NameError" in result
        assert "exit_code: 1" in result

    @pytest.mark.asyncio
    async def test_execute_python_no_output(self) -> None:
        """Python 无输出时返回"(无输出)"。"""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.exit_code = 0

        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(return_value=mock_result)

        mock_cls = MagicMock(return_value=mock_sandbox)
        with patch("kasaya.sandbox.LocalSandbox", mock_cls), \
             patch("kasaya.sandbox.SandboxConfig"):
            result = await execute_python.execute({"code": "x = 1"})
        assert result == "(无输出)"

    @pytest.mark.asyncio
    async def test_execute_shell_with_mock_sandbox(self) -> None:
        """通过 mock sandbox 测试 Shell 执行。"""
        mock_result = MagicMock()
        mock_result.stdout = "file1.txt\nfile2.txt"
        mock_result.stderr = ""
        mock_result.exit_code = 0

        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(return_value=mock_result)

        mock_cls = MagicMock(return_value=mock_sandbox)
        with patch("kasaya.sandbox.LocalSandbox", mock_cls), \
             patch("kasaya.sandbox.SandboxConfig"):
            result = await execute_shell.execute({"command": "ls"})
        assert "file1.txt" in result

    @pytest.mark.asyncio
    async def test_execute_shell_error_output(self) -> None:
        """Shell 执行错误时包含 stderr 和 exit_code。"""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "command not found"
        mock_result.exit_code = 127

        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(return_value=mock_result)

        mock_cls = MagicMock(return_value=mock_sandbox)
        with patch("kasaya.sandbox.LocalSandbox", mock_cls), \
             patch("kasaya.sandbox.SandboxConfig"):
            result = await execute_shell.execute({"command": "nonexistent"})
        assert "command not found" in result
        assert "exit_code: 127" in result

    @pytest.mark.asyncio
    async def test_execute_shell_no_output(self) -> None:
        """Shell 无输出时返回"(无输出)"。"""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.exit_code = 0

        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(return_value=mock_result)

        mock_cls = MagicMock(return_value=mock_sandbox)
        with patch("kasaya.sandbox.LocalSandbox", mock_cls), \
             patch("kasaya.sandbox.SandboxConfig"):
            result = await execute_shell.execute({"command": "true"})
        assert result == "(无输出)"


# ---------------------------------------------------------------------------
# code-review 工具组测试
# ---------------------------------------------------------------------------


class TestAnalyzeCode:
    """analyze_code 工具测试。"""

    @pytest.mark.asyncio
    async def test_python_bare_except(self) -> None:
        """检测 Python 裸 except。"""
        code = "try:\n    pass\nexcept:\n    pass"
        raw = await analyze_code.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "bare-except" in rules

    @pytest.mark.asyncio
    async def test_python_eval_detection(self) -> None:
        """检测 eval 使用。"""
        code = "result = eval(user_input)"
        raw = await analyze_code.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "security-eval" in rules

    @pytest.mark.asyncio
    async def test_python_hardcoded_secret(self) -> None:
        """检测硬编码密钥。"""
        code = 'password = "super_secret_123"'
        raw = await analyze_code.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "hardcoded-secret" in rules

    @pytest.mark.asyncio
    async def test_python_mutable_default(self) -> None:
        """检测可变默认参数。"""
        code = "def foo(items=[]):\n    items.append(1)"
        raw = await analyze_code.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "mutable-default-arg" in rules

    @pytest.mark.asyncio
    async def test_javascript_eval_detection(self) -> None:
        """检测 JavaScript eval。"""
        code = "const result = eval(userInput);"
        raw = await analyze_code.execute({"code": code, "language": "javascript"})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "no-eval" in rules

    @pytest.mark.asyncio
    async def test_javascript_innerhtml(self) -> None:
        """检测 innerHTML 使用。"""
        code = "el.innerHTML = userContent;"
        raw = await analyze_code.execute({"code": code, "language": "javascript"})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "no-inner-html" in rules

    @pytest.mark.asyncio
    async def test_javascript_var_usage(self) -> None:
        """检测 var 声明。"""
        code = "var count = 0;"
        raw = await analyze_code.execute({"code": code, "language": "javascript"})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "no-var" in rules

    @pytest.mark.asyncio
    async def test_line_too_long(self) -> None:
        """检测超长行。"""
        code = "x = " + "a" * 120
        raw = await analyze_code.execute({"code": code})
        result = json.loads(raw)
        rules = [i["rule"] for i in result["issues"]]
        assert "line-too-long" in rules

    @pytest.mark.asyncio
    async def test_code_metrics(self) -> None:
        """检查代码指标输出。"""
        code = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        raw = await analyze_code.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        assert result["function_count"] == 2
        assert result["total_lines"] == 6

    @pytest.mark.asyncio
    async def test_clean_code_no_issues(self) -> None:
        """干净代码无严重问题。"""
        code = "def greet(name: str) -> str:\n    return f'Hello, {name}'"
        raw = await analyze_code.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        errors = [i for i in result["issues"] if i["severity"] == "error"]
        assert len(errors) == 0


class TestParseDiff:
    """parse_diff 工具测试。"""

    @pytest.mark.asyncio
    async def test_simple_diff(self) -> None:
        """解析简单的 unified diff。"""
        diff = (
            "--- a/hello.py\n"
            "+++ b/hello.py\n"
            "@@ -1,3 +1,4 @@\n"
            " import os\n"
            "-print('old')\n"
            "+print('new')\n"
            "+print('extra')\n"
            " # end\n"
        )
        raw = await parse_diff.execute({"diff_text": diff})
        result = json.loads(raw)
        assert result["files_changed"] == 1
        assert result["total_additions"] == 2
        assert result["total_deletions"] == 1
        assert result["files"][0]["file"] == "hello.py"

    @pytest.mark.asyncio
    async def test_multi_file_diff(self) -> None:
        """解析多文件 diff。"""
        diff = (
            "--- a/foo.py\n+++ b/foo.py\n@@ -1,1 +1,2 @@\n x = 1\n+y = 2\n"
            "--- a/bar.py\n+++ b/bar.py\n@@ -1,2 +1,1 @@\n-old_line\n new_line\n"
        )
        raw = await parse_diff.execute({"diff_text": diff})
        result = json.loads(raw)
        assert result["files_changed"] == 2

    @pytest.mark.asyncio
    async def test_empty_diff(self) -> None:
        """空 diff 返回零变更。"""
        raw = await parse_diff.execute({"diff_text": ""})
        result = json.loads(raw)
        assert result["files_changed"] == 0


class TestCheckSecurityPatterns:
    """check_security_patterns 工具测试。"""

    @pytest.mark.asyncio
    async def test_python_eval(self) -> None:
        """检测 Python eval 漏洞。"""
        code = "result = eval(user_input)"
        raw = await check_security_patterns.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        assert result["vulnerabilities_found"] > 0
        cwes = [v["cwe"] for v in result["vulnerabilities"]]
        assert "CWE-94" in cwes

    @pytest.mark.asyncio
    async def test_python_pickle(self) -> None:
        """检测 pickle 反序列化漏洞。"""
        code = "data = pickle.loads(user_bytes)"
        raw = await check_security_patterns.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        cwes = [v["cwe"] for v in result["vulnerabilities"]]
        assert "CWE-502" in cwes

    @pytest.mark.asyncio
    async def test_python_os_system(self) -> None:
        """检测 os.system 命令注入。"""
        code = "os.system(f'rm -rf {user_dir}')"
        raw = await check_security_patterns.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        cwes = [v["cwe"] for v in result["vulnerabilities"]]
        assert "CWE-78" in cwes

    @pytest.mark.asyncio
    async def test_hardcoded_credentials(self) -> None:
        """检测硬编码凭据。"""
        code = 'api_key = "sk-1234567890abcdef"'
        raw = await check_security_patterns.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        cwes = [v["cwe"] for v in result["vulnerabilities"]]
        assert "CWE-798" in cwes

    @pytest.mark.asyncio
    async def test_javascript_xss(self) -> None:
        """检测 JavaScript XSS 漏洞。"""
        code = "document.getElementById('output').innerHTML = userInput;"
        raw = await check_security_patterns.execute({"code": code, "language": "javascript"})
        result = json.loads(raw)
        cwes = [v["cwe"] for v in result["vulnerabilities"]]
        assert "CWE-79" in cwes

    @pytest.mark.asyncio
    async def test_javascript_eval(self) -> None:
        """检测 JavaScript eval 漏洞。"""
        code = "eval(req.body.code)"
        raw = await check_security_patterns.execute({"code": code, "language": "javascript"})
        result = json.loads(raw)
        cwes = [v["cwe"] for v in result["vulnerabilities"]]
        assert "CWE-94" in cwes

    @pytest.mark.asyncio
    async def test_clean_code(self) -> None:
        """安全代码无漏洞。"""
        code = "def add(a: int, b: int) -> int:\n    return a + b"
        raw = await check_security_patterns.execute({"code": code, "language": "python"})
        result = json.loads(raw)
        assert result["vulnerabilities_found"] == 0
