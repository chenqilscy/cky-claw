"""CkyClaw Backend 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware
from app.core.audit_middleware import AuditLogMiddleware
from app.core.otel import setup_otel, instrument_fastapi, get_metrics_app
from app.api.agents import router as agents_router
from app.api.agent_locales import router as agent_locales_router
from app.api.alerts import router as alerts_router
from app.api.apm import router as apm_router
from app.api.agent_templates import router as agent_templates_router
from app.api.agent_versions import router as agent_versions_router
from app.api.approvals import router as approvals_router
from app.api.audit_logs import router as audit_logs_router
from app.api.auth import router as auth_router
from app.api.oauth import router as oauth_router
from app.api.evaluations import router as evaluations_router
from app.api.evolution import router as evolution_router
from app.api.health import router as health_router
from app.api.providers import router as providers_router
from app.api.provider_models import router as provider_models_router
from app.api.roles import router as roles_router
from app.api.sandbox import router as sandbox_router
from app.api.scheduled_tasks import router as scheduled_tasks_router
from app.api.sessions import router as sessions_router
from app.api.supervision import router as supervision_router
from app.api.token_usage import router as token_usage_router
from app.api.traces import router as traces_router
from app.api.guardrails import router as guardrails_router
from app.api.im_channels import router as im_channels_router
from app.api.mcp_servers import router as mcp_servers_router
from app.api.memories import router as memories_router
from app.api.organizations import router as organizations_router
from app.api.skills import router as skills_router
from app.api.tool_groups import router as tool_groups_router
from app.api.workflows import router as workflows_router
from app.api.teams import router as teams_router
from app.api.ws import router as ws_router
from app.api.config_reload import router as config_reload_router
from app.api.cost_router import router as cost_router_router
from app.api.checkpoints import router as checkpoints_router
from app.api.intent import router as intent_router
from app.api.ab_test import router as ab_test_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理 — 启动/关闭 Redis 订阅 + Seed 内置工具组。"""
    from app.api.ws import start_subscriber, stop_subscriber
    from app.core.database import async_session_factory
    from app.core.redis import close_redis
    from app.services.tool_group import seed_hosted_tool_groups

    # Seed 内置工具组
    try:
        async with async_session_factory() as db:
            await seed_hosted_tool_groups(db)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Seed 内置工具组失败，跳过", exc_info=True)

    await start_subscriber()

    # 启动定时任务调度器
    from app.services.scheduler_engine import start_scheduler
    start_scheduler()

    yield

    # 停止调度器
    from app.services.scheduler_engine import stop_scheduler
    stop_scheduler()

    # 刷写审计缓冲区残留条目
    from app.core.audit_middleware import flush_audit_buffer
    await flush_audit_buffer()

    await stop_subscriber()
    await close_redis()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    # 日志系统优先初始化（在 OTel 之前）
    setup_logging()

    # OTel 必须在 app 创建前初始化
    setup_otel()

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
    app.add_middleware(AuditLogMiddleware)

    # 全局异常处理
    register_exception_handlers(app)

    # 路由
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(oauth_router)
    app.include_router(audit_logs_router)
    app.include_router(agents_router)
    app.include_router(agent_locales_router)
    app.include_router(alerts_router)
    app.include_router(apm_router)
    app.include_router(agent_templates_router)
    app.include_router(agent_versions_router)
    app.include_router(approvals_router)
    app.include_router(evaluations_router)
    app.include_router(evolution_router)
    app.include_router(providers_router)
    app.include_router(provider_models_router)
    app.include_router(roles_router)
    app.include_router(sandbox_router)
    app.include_router(scheduled_tasks_router)
    app.include_router(sessions_router)
    app.include_router(supervision_router)
    app.include_router(token_usage_router)
    app.include_router(traces_router)
    app.include_router(guardrails_router)
    app.include_router(im_channels_router)
    app.include_router(mcp_servers_router)
    app.include_router(memories_router)
    app.include_router(organizations_router)
    app.include_router(skills_router)
    app.include_router(tool_groups_router)
    app.include_router(workflows_router)
    app.include_router(teams_router)
    app.include_router(ws_router)
    app.include_router(config_reload_router)
    app.include_router(cost_router_router)
    app.include_router(checkpoints_router)
    app.include_router(intent_router)
    app.include_router(ab_test_router)

    # OTel FastAPI 自动埋点（最后添加）
    instrument_fastapi(app)

    # Prometheus metrics endpoint
    metrics_app = get_metrics_app()
    if metrics_app:
        app.mount("/metrics", metrics_app)

    return app


app = create_app()
