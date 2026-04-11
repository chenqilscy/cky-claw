"""自定义中间件。"""

from __future__ import annotations

import contextvars
import uuid
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 全局 context var，供日志 Filter 读取
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求注入唯一 X-Request-ID，并写入 contextvars 供日志自动采集。"""

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)
