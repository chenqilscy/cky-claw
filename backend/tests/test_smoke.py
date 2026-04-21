"""Kasaya Backend 基础冒烟测试。"""

from __future__ import annotations


def test_health_endpoint_exists() -> None:
    """验证 health 路由已注册。"""
    from app.main import app

    routes = [route.path for route in app.routes]
    assert "/health" in routes
