"""Run Registry — 追踪运行中 Run 的 CancellationToken。

内存级注册表，仅当前进程有效。用于从外部 API 取消正在执行的 Run。
"""

from __future__ import annotations

import threading

from ckyclaw_framework.runner.cancellation import CancellationToken


class RunRegistry:
    """线程安全的 Run 注册表，存储 run_id → CancellationToken 映射。"""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}
        self._lock = threading.Lock()

    def register(self, run_id: str, token: CancellationToken) -> None:
        """注册运行中 Run 的取消令牌。"""
        with self._lock:
            self._tokens[run_id] = token

    def unregister(self, run_id: str) -> None:
        """注销已结束 Run 的取消令牌。"""
        with self._lock:
            self._tokens.pop(run_id, None)

    def cancel(self, run_id: str) -> bool:
        """取消指定 Run。返回是否找到并取消成功。"""
        with self._lock:
            token = self._tokens.get(run_id)
        if token is None:
            return False
        token.cancel()
        return True

    def is_running(self, run_id: str) -> bool:
        """检查指定 Run 是否仍在运行。"""
        with self._lock:
            token = self._tokens.get(run_id)
        return token is not None and not token.is_cancelled

    def active_count(self) -> int:
        """当前活跃 Run 数量。"""
        with self._lock:
            return sum(1 for t in self._tokens.values() if not t.is_cancelled)


# 全局单例
run_registry = RunRegistry()
