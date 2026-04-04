"""审计日志中间件 — 自动记录所有写操作。"""

from __future__ import annotations

import logging
import re
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import async_session_factory

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


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP，支持 X-Forwarded-For 代理头。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class AuditLogMiddleware(BaseHTTPMiddleware):
    """审计日志中间件：自动记录 POST/PUT/PATCH/DELETE 操作。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[type-arg]
        method = request.method.upper()
        path = request.url.path

        # 非写操作或跳过路径，直接放行
        if method not in _AUDIT_METHODS or path in _SKIP_PATHS:
            return await call_next(request)

        # 执行请求
        response = await call_next(request)

        # Fire-and-forget: 独立 session 写审计日志
        try:
            await self._write_audit_log(request, response, method, path)
        except Exception:
            logger.exception("Failed to write audit log for %s %s", method, path)

        return response

    async def _write_audit_log(
        self,
        request: Request,
        response: Response,
        method: str,
        path: str,
    ) -> None:
        """使用独立 DB session 写入审计日志。"""
        from app.models.audit_log import AuditLog

        match = _PATH_PATTERN.match(path)
        if not match:
            return

        resource_type = match.group(1).replace("-", "_")
        resource_id = match.group(2)
        action = _METHOD_ACTION_MAP.get(method, method)

        # 从 JWT 中提取 user_id（如果有认证）
        user_id: str | None = None
        if hasattr(request.state, "user_id"):
            user_id = str(request.state.user_id)

        ip_address = _get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:500]
        request_id = getattr(request.state, "request_id", None)

        async with async_session_factory() as db:
            record = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail={"path": path, "method": method},
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                status_code=response.status_code,
            )
            db.add(record)
            await db.commit()
