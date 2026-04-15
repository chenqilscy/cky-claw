"""CkyClaw 结构化日志配置。

使用 python-json-logger 将标准库 logging 输出格式化为 JSON，
便于 Promtail 采集后写入 Loki 进行聚合查询。

配置说明：
- 开发环境（debug=True）：可读的彩色文本格式
- 生产环境（debug=False）：JSON 格式，含 timestamp / level / logger / message + extra fields
"""

from __future__ import annotations

import logging
import logging.config
import sys
from typing import Any

from app.core.config import settings


class _HealthFilter(logging.Filter):
    """过滤 /health 健康检查端点的访问日志，减少噪音。"""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/health" not in msg


class _RequestIDFilter(logging.Filter):
    """自动注入 request_id 到每条日志记录（从 contextvars 读取）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        from app.core.middleware import request_id_var
        record.request_id = request_id_var.get("-")
        return True


def setup_logging() -> None:
    """初始化全局日志配置。

    在生产环境输出 JSON 格式日志。JSON 字段包含：
    - timestamp: ISO8601 时间戳
    - level: 日志级别
    - logger: 日志器名称
    - message: 日志内容
    - request_id: 请求 ID（如已注入）
    - exc_info: 异常堆栈（如有）
    """
    log_level = "DEBUG" if settings.debug else "INFO"

    if settings.debug:
        # 开发环境：人类可读格式
        fmt = "%(asctime)s [%(levelname)-8s] %(name)s [%(request_id)s]: %(message)s"
        handlers: dict[str, Any] = {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "text",
                "filters": ["health_filter", "request_id_filter"],
            }
        }
        formatters: dict[str, Any] = {
            "text": {
                "format": fmt,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        }
    else:
        # 生产环境：JSON 格式
        handlers = {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
                "filters": ["health_filter", "request_id_filter"],
            }
        }
        formatters = {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
                "rename_fields": {"asctime": "timestamp", "levelname": "level", "name": "logger"},
                "datefmt": "%Y-%m-%dT%H:%M:%S.%fZ",
            }
        }

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "health_filter": {
                "()": _HealthFilter,
            },
            "request_id_filter": {
                "()": _RequestIDFilter,
            },
        },
        "formatters": formatters,
        "handlers": handlers,
        "loggers": {
            # 降低三方库噪音
            "asyncio": {"level": "WARNING"},
            "uvicorn.access": {"level": "WARNING"},
            "uvicorn.error": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "litellm": {"level": "WARNING"},
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
    })

    logger = logging.getLogger(__name__)
    logger.info(
        "日志系统初始化完成",
        extra={
            "log_format": "text" if settings.debug else "json",
            "log_level": log_level,
        },
    )
