"""沙箱执行器抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ckyclaw_framework.sandbox.config import SandboxConfig


@dataclass
class SandboxResult:
    """沙箱执行结果。

    Attributes:
        exit_code: 进程退出码。
        stdout: 标准输出。
        stderr: 标准错误。
        timed_out: 是否超时。
        duration_ms: 执行时长（毫秒）。
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_ms: float = 0.0


class SandboxExecutor(ABC):
    """沙箱执行器协议 — 子类实现 execute 方法。"""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()

    @abstractmethod
    async def execute(self, code: str, *, language: str = "python") -> SandboxResult:
        """在沙箱中执行代码。

        Args:
            code: 要执行的代码内容。
            language: 编程语言（默认 python）。

        Returns:
            SandboxResult: 执行结果。
        """
        ...

    async def cleanup(self) -> None:
        """清理沙箱资源。子类可覆盖。"""
        pass
