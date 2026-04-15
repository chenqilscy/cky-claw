"""审计日志中间件 — 自动记录所有写操作（批量刷写）。"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from typing import TYPE_CHECKING, Any, cast

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import async_session_factory

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)

# 只记录写操作
_AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# 从 URL 路径中提取资源类型和资源 ID
# 匹配 /api/v1/{resource_type} 或 /api/v1/{resource_type}/{resource_id}
_PATH_PATTERN = re.compile(r"^/api/v1/([a-z_-]+)(?:/([^/]+))?")

# 不需要审计的路径
_SKIP_PATHS = {"/api/v1/audit-logs", "/api/v1/auth/login", "/api/v1/auth/register"}

# HTTP 方法 → 操作名
_METHOD_ACTION_MAP = {
    "POST": "CREATE",
    "PUT": "UPDATE",
    "PATCH": "UPDATE",
    "DELETE": "DELETE",
}

# 批量刷写配置
_FLUSH_INTERVAL_SECONDS = 2.0
_FLUSH_BATCH_SIZE = 50

# 模块级单例引用，供 shutdown 使用
_instance: AuditLogMiddleware | None = None


async def flush_audit_buffer() -> None:
    """刷写审计缓冲区残留条目，供应用 shutdown 时调用。"""
    if _instance is not None:
        await _instance._flush()


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP，支持 X-Forwarded-For 代理头。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class AuditLogMiddleware(BaseHTTPMiddleware):
    """审计日志中间件：自动记录 POST/PUT/PATCH/DELETE 操作，批量刷写到数据库。"""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._buffer: deque[dict[str, Any]] = deque()
        self._flush_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        # 注册模块级引用，便于 lifespan shutdown 时 flush 残留条目
        global _instance  # noqa: PLW0603
        _instance = self

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        method = request.method.upper()
        path = request.url.path

        # 非写操作或跳过路径，直接放行
        if method not in _AUDIT_METHODS or path in _SKIP_PATHS:
            return cast("Response", await call_next(request))

        # 确保后台刷写任务已启动
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._periodic_flush())

        # 执行请求
        response: Response = await call_next(request)

        # 收集审计条目到缓冲区
        try:
            self._collect_entry(request, response, method, path)
        except Exception:
            logger.exception("Failed to collect audit entry for %s %s", method, path)

        # 缓冲区满时立即触发刷写
        if len(self._buffer) >= _FLUSH_BATCH_SIZE:
            asyncio.create_task(self._flush())

        return response

    def _collect_entry(
        self,
        request: Request,
        response: Response,
        method: str,
        path: str,
    ) -> None:
        """将审计条目加入内存缓冲区。"""
        match = _PATH_PATTERN.match(path)
        if not match:
            return

        resource_type = match.group(1).replace("-", "_")
        resource_id = match.group(2)
        action = _METHOD_ACTION_MAP.get(method, method)

        user_id: str | None = None
        if hasattr(request.state, "user_id"):
            user_id = str(request.state.user_id)

        self._buffer.append({
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "detail": {"path": path, "method": method},
            "ip_address": _get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", "")[:500],
            "request_id": getattr(request.state, "request_id", None),
            "status_code": response.status_code,
        })

    async def _periodic_flush(self) -> None:
        """后台定期刷写任务。"""
        while True:
            await asyncio.sleep(_FLUSH_INTERVAL_SECONDS)
            await self._flush()

    async def _flush(self) -> None:
        """将缓冲区中的审计条目批量写入数据库。"""
        async with self._lock:
            if not self._buffer:
                return

            entries = list(self._buffer)
            self._buffer.clear()

        try:
            from app.models.audit_log import AuditLog

            async with async_session_factory() as db:
                for entry in entries:
                    db.add(AuditLog(**entry))
                await db.commit()
        except Exception:
            logger.exception("Failed to flush %d audit log entries", len(entries))
