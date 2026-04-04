"""CkyClaw Backend 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestIDMiddleware
from app.api.agents import router as agents_router
from app.api.agent_templates import router as agent_templates_router
from app.api.agent_versions import router as agent_versions_router
from app.api.approvals import router as approvals_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.providers import router as providers_router
from app.api.sessions import router as sessions_router
from app.api.supervision import router as supervision_router
from app.api.token_usage import router as token_usage_router
from app.api.traces import router as traces_router
from app.api.guardrails import router as guardrails_router
from app.api.mcp_servers import router as mcp_servers_router
from app.api.memories import router as memories_router
from app.api.skills import router as skills_router
from app.api.tool_groups import router as tool_groups_router
from app.api.workflows import router as workflows_router
from app.api.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理 — 启动/关闭 Redis 订阅。"""
    from app.api.ws import start_subscriber, stop_subscriber
    from app.core.redis import close_redis

    await start_subscriber()
    yield
    await stop_subscriber()
    await close_redis()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    app = FastAPI(
        title="CkyClaw",
        description="AI Agent 管理与运行平台",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
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
    app.include_router(agent_templates_router)
    app.include_router(agent_versions_router)
    app.include_router(approvals_router)
    app.include_router(providers_router)
    app.include_router(sessions_router)
    app.include_router(supervision_router)
    app.include_router(token_usage_router)
    app.include_router(traces_router)
    app.include_router(guardrails_router)
    app.include_router(mcp_servers_router)
    app.include_router(memories_router)
    app.include_router(skills_router)
    app.include_router(tool_groups_router)
    app.include_router(workflows_router)
    app.include_router(ws_router)

    return app


app = create_app()
