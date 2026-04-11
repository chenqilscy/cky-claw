"""CancellationToken — 层级化取消令牌。

提供父子级联取消机制：取消父 Token 会自动级联取消所有子 Token。
用于 Runner / TeamRunner / Workflow 的协作式取消。
"""

from __future__ import annotations

import asyncio
from typing import Callable


class CancellationToken:
    """层级化取消令牌。

    支持父→子级联取消：当父 Token 被取消时，所有子 Token 自动取消。
    Runner 在每次 LLM 调用和工具执行前检查此令牌。

    用法::

        parent = CancellationToken()
        child = parent.create_child()

        parent.cancel()          # 同时取消 parent 和 child
        assert child.is_cancelled
    """

    def __init__(self, *, parent: CancellationToken | None = None) -> None:
        """初始化取消令牌。

        Args:
            parent: 父级令牌。取消父级时自动级联取消本令牌。
        """
        self._event = asyncio.Event()
        self._children: list[CancellationToken] = []
        self._callbacks: list[Callable[[], None]] = []
        self._parent = parent
        if parent is not None:
            parent._children.append(self)
            # 如果父级已经取消，子级立即取消
            if parent.is_cancelled:
                self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """令牌是否已被取消。"""
        return self._event.is_set()

    def cancel(self) -> None:
        """取消此令牌及所有子令牌。"""
        if self._event.is_set():
            return
        self._event.set()
        # 级联取消所有子令牌
        for child in self._children:
            child.cancel()
        # 触发回调（单个回调异常不阻断后续回调）
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def create_child(self) -> CancellationToken:
        """创建子令牌。

        返回的子令牌在父令牌取消时自动取消。
        """
        return CancellationToken(parent=self)

    def on_cancel(self, callback: Callable[[], None]) -> None:
        """注册取消回调。

        Args:
            callback: 取消时调用的无参函数。如果令牌已取消则立即调用。
        """
        if self.is_cancelled:
            callback()
        else:
            self._callbacks.append(callback)

    async def wait(self) -> None:
        """异步等待直到令牌被取消。"""
        await self._event.wait()

    def check(self) -> None:
        """检查令牌状态，已取消则抛出 CancelledError。

        Raises:
            asyncio.CancelledError: 令牌已被取消。
        """
        if self._event.is_set():
            raise asyncio.CancelledError("Operation cancelled via CancellationToken")
