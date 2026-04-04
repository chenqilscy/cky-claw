"""沙箱配置。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SandboxConfig:
    """沙箱执行配置。

    Attributes:
        image: Docker 镜像名（仅 DockerSandbox 使用）。
        timeout: 执行超时（秒），0 表示不限。
        memory_limit_mb: 内存上限（MB），0 表示不限。
        cpu_limit: CPU 核数限制，0 表示不限。
        network_enabled: 是否允许网络访问。
        work_dir: 工作目录路径。若为空则自动创建临时目录。
        env: 额外环境变量。
    """

    image: str = "python:3.12-slim"
    timeout: int = 30
    memory_limit_mb: int = 256
    cpu_limit: float = 1.0
    network_enabled: bool = False
    work_dir: str = ""
    env: dict[str, str] = field(default_factory=dict)
