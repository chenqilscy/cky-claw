"""Hosted Tools — 平台内置工具组。

提供开箱即用的 5 组内置工具：
- web-search: 网络搜索 + 页面抓取
- code-executor: Python/Shell 代码执行（沙箱）
- file-ops: 文件读写 + 目录列表
- http: HTTP 请求
- database: 只读 SQL 查询
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from ckyclaw_framework.tools.function_tool import function_tool
from ckyclaw_framework.tools.tool_group import ToolGroup
from ckyclaw_framework.tools.tool_registry import ToolRegistry, get_default_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# web-search 工具组
# ---------------------------------------------------------------------------


@function_tool(name="web_search", description="搜索互联网并返回相关结果摘要。")
async def web_search(query: str, max_results: int = 5) -> str:
    """搜索互联网内容。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数（默认 5）
    """
    try:
        import httpx
    except ImportError:
        return "Error: httpx 未安装，无法执行网络搜索。请安装: pip install httpx"

    url = "https://html.duckduckgo.com/html/"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data={"q": query})
            resp.raise_for_status()
    except Exception as exc:
        return f"搜索失败: {exc}"

    # 简单解析 DuckDuckGo HTML 结果
    results: list[dict[str, str]] = []
    pattern = re.compile(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
    snippet_pattern = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
    links = pattern.findall(resp.text)
    snippets = snippet_pattern.findall(resp.text)

    for i, (href, title) in enumerate(links[:max_results]):
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""
        results.append({"title": clean_title, "url": href, "snippet": snippet})

    if not results:
        return f"未找到关于 '{query}' 的搜索结果。"
    return json.dumps(results, ensure_ascii=False, indent=2)


@function_tool(name="fetch_webpage", description="抓取指定 URL 的网页内容并返回纯文本。")
async def fetch_webpage(url: str, max_length: int = 5000) -> str:
    """抓取网页内容。

    Args:
        url: 要抓取的网页 URL
        max_length: 返回内容最大字符数（默认 5000）
    """
    try:
        import httpx
    except ImportError:
        return "Error: httpx 未安装。请安装: pip install httpx"

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        return f"抓取失败: {exc}"

    # 简单去 HTML 标签
    text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_length:
        text = text[:max_length] + "...(已截断)"
    return text


# ---------------------------------------------------------------------------
# code-executor 工具组
# ---------------------------------------------------------------------------


@function_tool(name="execute_python", description="在沙箱中执行 Python 代码并返回输出。")
async def execute_python(code: str) -> str:
    """执行 Python 代码。

    Args:
        code: 要执行的 Python 代码
    """
    from ckyclaw_framework.sandbox import LocalSandbox, SandboxConfig

    config = SandboxConfig(timeout=30)
    sandbox = LocalSandbox(config)
    result = await sandbox.execute(code, language="python")
    output_parts: list[str] = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(f"[stderr] {result.stderr}")
    if result.exit_code != 0:
        output_parts.append(f"[exit_code: {result.exit_code}]")
    return "\n".join(output_parts) if output_parts else "(无输出)"


@function_tool(name="execute_shell", description="在沙箱中执行 Shell 命令并返回输出。")
async def execute_shell(command: str) -> str:
    """执行 Shell 命令。

    Args:
        command: 要执行的 Shell 命令
    """
    from ckyclaw_framework.sandbox import LocalSandbox, SandboxConfig

    config = SandboxConfig(timeout=30)
    sandbox = LocalSandbox(config)
    result = await sandbox.execute(command, language="bash")
    output_parts: list[str] = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(f"[stderr] {result.stderr}")
    if result.exit_code != 0:
        output_parts.append(f"[exit_code: {result.exit_code}]")
    return "\n".join(output_parts) if output_parts else "(无输出)"


# ---------------------------------------------------------------------------
# file-ops 工具组
# ---------------------------------------------------------------------------

# 工作目录限制（防目录穿越）
_FILE_OPS_BASE_DIR = os.environ.get("CKYCLAW_FILE_OPS_BASE_DIR", "/tmp/ckyclaw-files")


def _safe_resolve(base: str, target: str) -> Path:
    """安全解析路径，防止目录穿越攻击。"""
    base_path = Path(base).resolve()
    full_path = (base_path / target).resolve()
    if not str(full_path).startswith(str(base_path)):
        raise PermissionError(f"路径 '{target}' 超出允许的工作目录")
    return full_path


@function_tool(name="file_read", description="读取文件内容。路径限制在工作目录内。")
async def file_read(path: str) -> str:
    """读取文件内容。

    Args:
        path: 文件相对路径
    """
    try:
        full_path = _safe_resolve(_FILE_OPS_BASE_DIR, path)
        content = await asyncio.to_thread(full_path.read_text, encoding="utf-8")
        return content
    except PermissionError as exc:
        return f"权限错误: {exc}"
    except FileNotFoundError:
        return f"文件不存在: {path}"
    except Exception as exc:
        return f"读取失败: {exc}"


@function_tool(name="file_write", description="写入内容到文件。路径限制在工作目录内。")
async def file_write(path: str, content: str) -> str:
    """写入文件。

    Args:
        path: 文件相对路径
        content: 要写入的内容
    """
    try:
        full_path = _safe_resolve(_FILE_OPS_BASE_DIR, path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(full_path.write_text, content, encoding="utf-8")
        return f"已写入 {len(content)} 字符到 {path}"
    except PermissionError as exc:
        return f"权限错误: {exc}"
    except Exception as exc:
        return f"写入失败: {exc}"


@function_tool(name="file_list", description="列出目录内容。路径限制在工作目录内。")
async def file_list(directory: str = ".") -> str:
    """列出目录内容。

    Args:
        directory: 目录相对路径（默认为工作目录根）
    """
    try:
        full_path = _safe_resolve(_FILE_OPS_BASE_DIR, directory)
        if not full_path.is_dir():
            return f"目录不存在: {directory}"
        entries: list[dict[str, Any]] = []

        def _scan() -> None:
            for item in sorted(full_path.iterdir()):
                rel = item.relative_to(Path(_FILE_OPS_BASE_DIR).resolve())
                entries.append({
                    "name": item.name,
                    "path": str(rel),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                })

        await asyncio.to_thread(_scan)
        return json.dumps(entries, ensure_ascii=False, indent=2)
    except PermissionError as exc:
        return f"权限错误: {exc}"
    except Exception as exc:
        return f"列目录失败: {exc}"


# ---------------------------------------------------------------------------
# http 工具组
# ---------------------------------------------------------------------------


@function_tool(name="http_request", description="发送 HTTP 请求并返回响应。")
async def http_request(
    url: str,
    method: str = "GET",
    headers: str = "{}",
    body: str = "",
) -> str:
    """发送 HTTP 请求。

    Args:
        url: 请求 URL
        method: HTTP 方法（GET/POST/PUT/DELETE）
        headers: 请求头 JSON 字符串
        body: 请求体
    """
    try:
        import httpx
    except ImportError:
        return "Error: httpx 未安装。请安装: pip install httpx"

    allowed = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    method_upper = method.upper()
    if method_upper not in allowed:
        return f"不支持的 HTTP 方法: {method}"

    try:
        req_headers = json.loads(headers) if headers else {}
    except json.JSONDecodeError:
        return "headers 格式错误，需要有效 JSON"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.request(
                method=method_upper,
                url=url,
                headers=req_headers,
                content=body if body else None,
            )
        result = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text[:10000],
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        return f"HTTP 请求失败: {exc}"


# ---------------------------------------------------------------------------
# database 工具组
# ---------------------------------------------------------------------------


@function_tool(name="database_query", description="执行只读 SQL 查询并返回结果。需配置数据库连接。")
async def database_query(
    query: str,
    connection_string: str = "",
    max_rows: int = 100,
) -> str:
    """执行只读 SQL 查询。

    Args:
        query: SQL 查询语句（仅支持 SELECT）
        connection_string: 数据库连接字符串（如未提供，使用环境变量 CKYCLAW_DB_QUERY_DSN）
        max_rows: 最大返回行数（默认 100）
    """
    # 安全检查：仅允许 SELECT
    normalized = query.strip().upper()
    if not normalized.startswith("SELECT"):
        return "安全限制：仅允许 SELECT 查询。"

    # 阻止危险关键词
    dangerous = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE"}
    tokens = set(re.findall(r"\b[A-Z]+\b", normalized))
    blocked = tokens & dangerous
    if blocked:
        return f"安全限制：查询中包含禁止的关键词: {', '.join(blocked)}"

    dsn = connection_string or os.environ.get("CKYCLAW_DB_QUERY_DSN", "")
    if not dsn:
        return "错误：未配置数据库连接。请设置 CKYCLAW_DB_QUERY_DSN 环境变量或传入 connection_string 参数。"

    try:
        import asyncpg
    except ImportError:
        return "Error: asyncpg 未安装。请安装: pip install asyncpg"

    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=10.0)
        try:
            rows = await asyncio.wait_for(conn.fetch(query), timeout=30.0)
            result = [dict(r) for r in rows[:max_rows]]
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        finally:
            await conn.close()
    except TimeoutError:
        return "查询超时（30 秒限制）"
    except Exception as exc:
        return f"查询失败: {exc}"


# ---------------------------------------------------------------------------
# code-review 工具组
# ---------------------------------------------------------------------------


@function_tool(name="analyze_code", description="分析代码片段，检测复杂度、风格问题和常见 Bug 模式。")
async def analyze_code(code: str, language: str = "python") -> str:
    """对代码进行静态分析。

    Args:
        code: 待审查的源代码文本
        language: 编程语言（python/javascript/typescript/java/go 等）
    """
    issues: list[dict[str, str]] = []
    lines = code.split("\n")

    # 通用检查
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip()
        # 过长行
        if len(stripped) > 120:
            issues.append({"line": str(i), "severity": "warning", "rule": "line-too-long",
                           "message": f"行长度 {len(stripped)} 超过 120 字符"})
        # 行尾空格
        if line.rstrip() != line.rstrip("\n") and line.endswith(" "):
            issues.append({"line": str(i), "severity": "info", "rule": "trailing-whitespace",
                           "message": "行尾包含多余空格"})

    lang = language.lower()
    if lang in ("python", "py"):
        _analyze_python(code, lines, issues)
    elif lang in ("javascript", "js", "typescript", "ts"):
        _analyze_javascript(code, lines, issues)

    # 复杂度估算
    func_count = sum(1 for ln in lines if ln.strip().startswith(("def ", "function ", "async def ", "async function ")))
    total_lines = len(lines)
    blank_lines = sum(1 for ln in lines if not ln.strip())
    comment_lines = sum(1 for ln in lines if ln.strip().startswith(("#", "//", "/*", "*")))

    summary = {
        "total_lines": total_lines,
        "code_lines": total_lines - blank_lines - comment_lines,
        "blank_lines": blank_lines,
        "comment_lines": comment_lines,
        "function_count": func_count,
        "issues_found": len(issues),
        "issues": issues[:50],  # 限制返回数量
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def _analyze_python(code: str, lines: list[str], issues: list[dict[str, str]]) -> None:
    """Python 特定的静态分析。"""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # 裸 except
        if re.match(r"except\s*:", stripped):
            issues.append({"line": str(i), "severity": "error", "rule": "bare-except",
                           "message": "使用裸 except，应指定异常类型"})
        # eval/exec 使用
        if re.search(r"\b(eval|exec)\s*\(", stripped):
            issues.append({"line": str(i), "severity": "error", "rule": "security-eval",
                           "message": "使用 eval/exec 存在代码注入风险"})
        # 硬编码密码/密钥模式
        if re.search(r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]", stripped, re.IGNORECASE):
            issues.append({"line": str(i), "severity": "error", "rule": "hardcoded-secret",
                           "message": "检测到硬编码的密码/密钥，应使用环境变量"})
        # TODO/FIXME 标记
        if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", stripped):
            issues.append({"line": str(i), "severity": "info", "rule": "todo-marker",
                           "message": "包含待处理标记"})
        # 可变默认参数
        if re.match(r"def\s+\w+\(.*=\s*(\[\]|\{\}|set\(\))", stripped):
            issues.append({"line": str(i), "severity": "warning", "rule": "mutable-default-arg",
                           "message": "使用可变对象作为默认参数，可能导致意外行为"})

    # SQL 注入模式
    if re.search(r"(execute|cursor\.execute)\s*\(.*(f\"|f'|%s|\.format\(|\" \+|\' \+)", code, re.DOTALL):
        issues.append({"line": "N/A", "severity": "error", "rule": "sql-injection",
                       "message": "检测到可能的 SQL 注入风险：使用字符串拼接构造 SQL"})


def _analyze_javascript(code: str, lines: list[str], issues: list[dict[str, str]]) -> None:
    """JavaScript/TypeScript 特定的静态分析。"""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # eval 使用
        if re.search(r"\beval\s*\(", stripped):
            issues.append({"line": str(i), "severity": "error", "rule": "no-eval",
                           "message": "使用 eval() 存在代码注入风险"})
        # innerHTML
        if ".innerHTML" in stripped and "=" in stripped:
            issues.append({"line": str(i), "severity": "warning", "rule": "no-inner-html",
                           "message": "直接设置 innerHTML 可能导致 XSS 漏洞"})
        # var 声明
        if re.match(r"var\s+\w+", stripped):
            issues.append({"line": str(i), "severity": "warning", "rule": "no-var",
                           "message": "使用 var 声明，建议使用 let 或 const"})
        # console.log
        if re.search(r"\bconsole\.(log|debug|info)\(", stripped):
            issues.append({"line": str(i), "severity": "info", "rule": "no-console",
                           "message": "残留的 console 调试语句"})


@function_tool(name="parse_diff", description="解析 unified diff 格式的代码变更，提取新增、修改和删除的代码行。")
async def parse_diff(diff_text: str) -> str:
    """解析 unified diff 格式文本。

    Args:
        diff_text: unified diff 格式的文本（如 git diff 输出）
    """
    files: list[dict[str, Any]] = []
    current_file: dict[str, Any] | None = None
    added_lines: list[dict[str, Any]] = []
    removed_lines: list[dict[str, Any]] = []
    line_num_new = 0
    line_num_old = 0

    for line in diff_text.split("\n"):
        # 新文件头
        if line.startswith("+++ "):
            if current_file is not None:
                current_file["added"] = added_lines
                current_file["removed"] = removed_lines
                files.append(current_file)
            filename = line[4:].strip()
            if filename.startswith("b/"):
                filename = filename[2:]
            current_file = {"file": filename, "added": [], "removed": []}
            added_lines = []
            removed_lines = []
        # hunk 头 @@ -a,b +c,d @@
        elif line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            line_num_new = int(match.group(1)) if match else 0
            match_old = re.search(r"-(\d+)", line)
            line_num_old = int(match_old.group(1)) if match_old else 0
        elif line.startswith("+") and not line.startswith("+++"):
            added_lines.append({"line": line_num_new, "content": line[1:]})
            line_num_new += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines.append({"line": line_num_old, "content": line[1:]})
            line_num_old += 1
        else:
            line_num_new += 1
            line_num_old += 1

    if current_file is not None:
        current_file["added"] = added_lines
        current_file["removed"] = removed_lines
        files.append(current_file)

    summary = {
        "files_changed": len(files),
        "total_additions": sum(len(f["added"]) for f in files),
        "total_deletions": sum(len(f["removed"]) for f in files),
        "files": files,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


@function_tool(name="check_security_patterns", description="检查代码中的安全漏洞模式（OWASP Top 10）。")
async def check_security_patterns(code: str, language: str = "python") -> str:
    """检查常见安全漏洞模式。

    Args:
        code: 待检查的源代码
        language: 编程语言
    """
    vulnerabilities: list[dict[str, str]] = []
    lang = language.lower()

    # 通用安全模式
    patterns: list[tuple[str, str, str]] = [
        (r"(password|secret|api_key|token|private_key)\s*=\s*['\"][^'\"]{3,}['\"]",
         "CWE-798", "硬编码凭据：密码/密钥不应硬编码在源代码中"),
        (r"https?://[^\s]*\?.*=(password|token|secret|key)=[^&\s]+",
         "CWE-598", "URL 中包含敏感参数，可能泄露到日志或浏览器历史"),
    ]

    if lang in ("python", "py"):
        patterns.extend([
            (r"\b(eval|exec)\s*\(", "CWE-94", "代码注入：eval/exec 可执行任意代码"),
            (r"pickle\.loads?\(", "CWE-502", "反序列化漏洞：pickle 可执行任意代码"),
            (r"subprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True",
             "CWE-78", "命令注入：shell=True 允许 shell 注入"),
            (r"os\.system\s*\(", "CWE-78", "命令注入：os.system 容易被注入"),
            (r"yaml\.load\s*\((?!.*Loader)", "CWE-502", "YAML 反序列化漏洞：应使用 yaml.safe_load"),
            (r"\.format\(.*\)|f['\"].*\{.*\}.*['\"].*execute|cursor\.execute\s*\(.*(\+|format|f['\"])",
             "CWE-89", "SQL 注入：使用字符串拼接构造 SQL 语句"),
        ])
    elif lang in ("javascript", "js", "typescript", "ts"):
        patterns.extend([
            (r"\beval\s*\(", "CWE-94", "代码注入：eval() 可执行任意代码"),
            (r"\.innerHTML\s*=", "CWE-79", "XSS 漏洞：直接设置 innerHTML"),
            (r"document\.write\s*\(", "CWE-79", "XSS 漏洞：document.write 可注入脚本"),
            (r"new\s+Function\s*\(", "CWE-94", "代码注入：通过 new Function 执行动态代码"),
            (r"child_process\.(exec|spawn)\s*\(", "CWE-78", "命令注入：应验证和转义用户输入"),
        ])

    for pattern, cwe, desc in patterns:
        matches = list(re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE))
        for match in matches:
            # 计算行号
            line_start = code[:match.start()].count("\n") + 1
            vulnerabilities.append({
                "line": str(line_start),
                "cwe": cwe,
                "severity": "critical" if "injection" in desc.lower() or "CWE-94" in cwe else "high",
                "description": desc,
                "matched": match.group(0)[:80],
            })

    result = {
        "language": language,
        "vulnerabilities_found": len(vulnerabilities),
        "vulnerabilities": vulnerabilities[:30],
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 工具组注册
# ---------------------------------------------------------------------------


def _build_hosted_groups() -> list[ToolGroup]:
    """构建所有内置工具组。"""
    web_search_group = ToolGroup(name="web-search", description="网络搜索与页面抓取")
    web_search_group.register(web_search)
    web_search_group.register(fetch_webpage)

    code_executor_group = ToolGroup(name="code-executor", description="代码执行（Python/Shell 沙箱）")
    code_executor_group.register(execute_python)
    code_executor_group.register(execute_shell)

    file_ops_group = ToolGroup(name="file-ops", description="文件读写与目录操作")
    file_ops_group.register(file_read)
    file_ops_group.register(file_write)
    file_ops_group.register(file_list)

    http_group = ToolGroup(name="http", description="HTTP 请求工具")
    http_group.register(http_request)

    database_group = ToolGroup(name="database", description="只读 SQL 查询")
    database_group.register(database_query)

    code_review_group = ToolGroup(name="code-review", description="代码审查与安全检测")
    code_review_group.register(analyze_code)
    code_review_group.register(parse_diff)
    code_review_group.register(check_security_patterns)

    return [web_search_group, code_executor_group, file_ops_group, http_group, database_group, code_review_group]


def register_hosted_tools(registry: ToolRegistry | None = None) -> list[ToolGroup]:
    """注册所有内置工具组到 ToolRegistry。

    Args:
        registry: 目标注册表，None 则使用全局默认注册表

    Returns:
        注册的 ToolGroup 列表
    """
    reg = registry or get_default_registry()
    groups = _build_hosted_groups()
    for group in groups:
        reg.register_group(group)
        logger.info("注册内置工具组: %s (%d 个工具)", group.name, len(group.tools))
    return groups


# 所有内置工具组 ID
HOSTED_GROUP_IDS = ["web-search", "code-executor", "file-ops", "http", "database", "code-review"]
