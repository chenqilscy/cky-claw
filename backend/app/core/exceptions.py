"""全局异常处理。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """应用级异常基类。"""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    """资源不存在。"""

    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404)


class AuthenticationError(AppError):
    """认证失败。"""

    def __init__(self, message: str = "认证失败") -> None:
        super().__init__(message=message, code="UNAUTHORIZED", status_code=401)


class ConflictError(AppError):
    """资源冲突。"""

    def __init__(self, message: str = "资源冲突") -> None:
        super().__init__(message=message, code="CONFLICT", status_code=409)


class ValidationError(AppError):
    """参数校验失败。"""

    def __init__(self, message: str = "参数校验失败") -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误",
                }
            },
        )
