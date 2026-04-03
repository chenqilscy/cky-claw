"""MCP Server 配置数据类。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MCPServerConfig:
    """MCP Server 连接配置。"""

    name: str
    """唯一标识"""

    transport: str
    """传输类型: stdio | sse | http"""

    command: str | None = None
    """stdio 模式的启动命令"""

    args: list[str] = field(default_factory=list)
    """stdio 模式的命令参数"""

    url: str | None = None
    """sse / http 模式的 URL"""

    env: dict[str, str] = field(default_factory=dict)
    """环境变量"""

    headers: dict[str, str] = field(default_factory=dict)
    """HTTP 请求头（sse/http 模式）"""

    connect_timeout: float = 30.0
    """连接超时（秒）"""

    tool_call_timeout: float = 60.0
    """工具调用超时（秒）"""
