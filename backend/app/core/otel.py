"""OpenTelemetry 初始化 — 仅当 CKYCLAW_OTEL_ENABLED=true 时激活。"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_metrics_app: Any | None = None


def setup_otel() -> None:
    """初始化 OTel SDK，配置 OTLP exporter + FastAPI 自动埋点。

    依赖包（仅在 otel_enabled=True 时需要）：
        opentelemetry-api
        opentelemetry-sdk
        opentelemetry-exporter-otlp-proto-grpc
        opentelemetry-instrumentation-fastapi
    """
    if not settings.otel_enabled:
        logger.debug("OTel disabled, skipping initialization")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_endpoint,
            insecure=True,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info(
            "OTel initialized: service=%s endpoint=%s",
            settings.otel_service_name,
            settings.otel_exporter_endpoint,
        )
    except ImportError:
        logger.warning(
            "OTel enabled but packages not installed. "
            "Install: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-grpc"
        )
    except Exception as e:
        logger.error("Failed to initialize OTel: %s", e)

    # Prometheus metrics endpoint
    _setup_prometheus_metrics()


def _setup_prometheus_metrics() -> None:
    """创建 Prometheus WSGI app 供 /metrics 端点挂载。"""
    global _metrics_app
    try:
        from prometheus_client import make_asgi_app
        _metrics_app = make_asgi_app()
        logger.info("Prometheus metrics endpoint enabled")
    except ImportError:
        logger.debug("prometheus-client not installed, /metrics disabled")
    except Exception as e:
        logger.error("Failed to setup Prometheus metrics: %s", e)


def get_metrics_app() -> Any | None:
    """返回 Prometheus ASGI app（如果已初始化）。"""
    return _metrics_app


def instrument_fastapi(app: object) -> None:
    """对 FastAPI 应用添加 OTel 自动埋点。"""
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OTel instrumentation enabled")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-fastapi not installed, skipping")
    except Exception as e:
        logger.error("Failed to instrument FastAPI: %s", e)
