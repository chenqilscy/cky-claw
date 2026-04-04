"""Backend 测试公共 conftest — 全局依赖覆盖。"""

from __future__ import annotations

import pytest

from app.core.tenant import get_org_id
from app.main import app


@pytest.fixture(autouse=True)
def _override_org_id():
    """全局覆盖 get_org_id 依赖，避免未认证测试触发 401。

    需要真实 org_id 的测试可自行设置 dependency_overrides 覆盖此默认值。
    """
    app.dependency_overrides[get_org_id] = lambda: None
    yield
    app.dependency_overrides.pop(get_org_id, None)
