"""CkyClaw Backend 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestIDMiddleware
from app.api.agents import router as agents_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.providers import router as providers_router
from app.api.sessions import router as sessions_router
from app.api.supervision import router as supervision_router
from app.api.token_usage import router as token_usage_router


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    app = FastAPI(
        title="CkyClaw",
        description="AI Agent 管理与运行平台",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # 中间件（后添加的先执行）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    # 全局异常处理
    register_exception_handlers(app)

    # 路由
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(agents_router)
    app.include_router(providers_router)
    app.include_router(sessions_router)
    app.include_router(supervision_router)
    app.include_router(token_usage_router)

    return app


app = create_app()
