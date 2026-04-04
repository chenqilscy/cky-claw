"""YAML/JSON 声明式配置导入导出 (#30) 测试。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundError
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_config(**overrides: object) -> MagicMock:
    """构造模拟 AgentConfig ORM 对象。"""
    now = datetime.now(timezone.utc)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "test-agent",
        "description": "测试 Agent",
        "instructions": "你是一个助手",
        "model": "gpt-4o",
        "provider_name": "openai",
        "model_settings": {"temperature": 0.7},
        "tool_groups": ["search"],
        "handoffs": [],
        "guardrails": {"input": [], "output": [], "tool": []},
        "approval_mode": "suggest",
        "mcp_servers": [],
        "agent_tools": [],
        "skills": [],
        "output_type": None,
        "metadata_": {},
        "org_id": None,
        "is_active": True,
        "created_by": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture()
def client() -> TestClient:
    """同步测试客户端。"""
    return TestClient(app)


# ---------------------------------------------------------------------------
# 导出测试
# ---------------------------------------------------------------------------


class TestExportAgent:
    """测试 Agent 导出 API。"""

    def test_export_yaml(self, client: TestClient) -> None:
        """导出 YAML 格式，包含正确字段。"""
        agent = _make_agent_config()
        with patch("app.services.agent.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            resp = client.get("/api/v1/agents/test-agent/export?format=yaml")
        assert resp.status_code == 200
        assert "application/x-yaml" in resp.headers["content-type"]
        assert 'filename="test-agent.yaml"' in resp.headers.get("content-disposition", "")
        data = yaml.safe_load(resp.text)
        assert data["name"] == "test-agent"
        assert data["model"] == "gpt-4o"
        assert data["provider_name"] == "openai"
        assert data["model_settings"] == {"temperature": 0.7}

    def test_export_json(self, client: TestClient) -> None:
        """导出 JSON 格式。"""
        agent = _make_agent_config()
        with patch("app.services.agent.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            resp = client.get("/api/v1/agents/test-agent/export?format=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        assert 'filename="test-agent.json"' in resp.headers.get("content-disposition", "")
        data = json.loads(resp.text)
        assert data["name"] == "test-agent"

    def test_export_default_format_is_yaml(self, client: TestClient) -> None:
        """不指定 format 默认导出 YAML。"""
        agent = _make_agent_config()
        with patch("app.services.agent.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            resp = client.get("/api/v1/agents/test-agent/export")
        assert resp.status_code == 200
        assert "yaml" in resp.headers["content-type"]

    def test_export_excludes_system_fields(self, client: TestClient) -> None:
        """导出排除系统字段（id, org_id, timestamps 等）。"""
        agent = _make_agent_config()
        with patch("app.services.agent.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            resp = client.get("/api/v1/agents/test-agent/export?format=json")
        data = json.loads(resp.text)
        excluded = {"id", "org_id", "is_active", "created_by", "created_at", "updated_at"}
        for field in excluded:
            assert field not in data, f"导出不应包含系统字段 {field}"

    def test_export_nonexistent_agent(self, client: TestClient) -> None:
        """导出不存在的 Agent 返回 404。"""
        with patch(
            "app.services.agent.get_agent_by_name",
            new_callable=AsyncMock,
            side_effect=NotFoundError("Agent 'no-such' 不存在"),
        ):
            resp = client.get("/api/v1/agents/no-such/export")
        assert resp.status_code == 404

    def test_export_yaml_unicode(self, client: TestClient) -> None:
        """导出 YAML 支持中文等 Unicode 字符。"""
        agent = _make_agent_config(description="中文描述", instructions="你好世界")
        with patch("app.services.agent.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            resp = client.get("/api/v1/agents/test-agent/export?format=yaml")
        data = yaml.safe_load(resp.text)
        assert data["description"] == "中文描述"
        assert data["instructions"] == "你好世界"


# ---------------------------------------------------------------------------
# 导入测试
# ---------------------------------------------------------------------------


class TestImportAgent:
    """测试 Agent 导入 API。"""

    def _make_created_agent(self, **overrides: object) -> MagicMock:
        """构造导入后返回的 mock 对象。"""
        return _make_agent_config(name="imported-agent", description="导入的 Agent", **overrides)

    def test_import_yaml(self, client: TestClient) -> None:
        """导入 YAML 文件创建 Agent。"""
        yaml_content = yaml.dump({"name": "imported-agent", "description": "导入的 Agent", "model": "gpt-4o"})
        agent = self._make_created_agent()
        with patch("app.services.agent.create_agent", new_callable=AsyncMock, return_value=agent):
            resp = client.post(
                "/api/v1/agents/import",
                files={"file": ("agent.yaml", BytesIO(yaml_content.encode()), "application/x-yaml")},
            )
        assert resp.status_code == 201
        assert resp.json()["name"] == "imported-agent"

    def test_import_yml_extension(self, client: TestClient) -> None:
        """导入 .yml 扩展名也被识别为 YAML。"""
        yaml_content = yaml.dump({"name": "imported-agent", "model": "gpt-4o"})
        agent = self._make_created_agent()
        with patch("app.services.agent.create_agent", new_callable=AsyncMock, return_value=agent):
            resp = client.post(
                "/api/v1/agents/import",
                files={"file": ("agent.yml", BytesIO(yaml_content.encode()), "application/x-yaml")},
            )
        assert resp.status_code == 201

    def test_import_json(self, client: TestClient) -> None:
        """导入 JSON 文件创建 Agent。"""
        json_content = json.dumps({"name": "imported-agent", "model": "gpt-4o"})
        agent = self._make_created_agent()
        with patch("app.services.agent.create_agent", new_callable=AsyncMock, return_value=agent):
            resp = client.post(
                "/api/v1/agents/import",
                files={"file": ("agent.json", BytesIO(json_content.encode()), "application/json")},
            )
        assert resp.status_code == 201

    def test_import_non_dict_returns_400(self, client: TestClient) -> None:
        """导入内容不是对象（如数组/字符串）返回 400。"""
        yaml_content = yaml.dump(["not", "a", "dict"])
        resp = client.post(
            "/api/v1/agents/import",
            files={"file": ("bad.yaml", BytesIO(yaml_content.encode()), "application/x-yaml")},
        )
        assert resp.status_code == 400

    def test_import_missing_required_field(self, client: TestClient) -> None:
        """导入缺少 name 字段返回 422。"""
        yaml_content = yaml.dump({"description": "没有名字"})
        resp = client.post(
            "/api/v1/agents/import",
            files={"file": ("noname.yaml", BytesIO(yaml_content.encode()), "application/x-yaml")},
        )
        assert resp.status_code == 422

    def test_import_invalid_name(self, client: TestClient) -> None:
        """导入 name 不合规则返回 422。"""
        yaml_content = yaml.dump({"name": "INVALID_NAME!"})
        resp = client.post(
            "/api/v1/agents/import",
            files={"file": ("bad-name.yaml", BytesIO(yaml_content.encode()), "application/x-yaml")},
        )
        assert resp.status_code == 422

    def test_import_passes_data_to_create(self, client: TestClient) -> None:
        """导入时传入的字段被正确传给 create_agent。"""
        config = {"name": "imported-agent", "model": "claude-3", "instructions": "自定义指令", "tool_groups": ["web"]}
        yaml_content = yaml.dump(config)
        agent = self._make_created_agent()
        with patch("app.services.agent.create_agent", new_callable=AsyncMock, return_value=agent) as mock_create:
            client.post(
                "/api/v1/agents/import",
                files={"file": ("cfg.yaml", BytesIO(yaml_content.encode()), "application/x-yaml")},
            )
        # 验证 AgentCreate 参数
        call_args = mock_create.call_args
        agent_create = call_args[0][1]  # 第二个位置参数
        assert agent_create.name == "imported-agent"
        assert agent_create.model == "claude-3"
        assert agent_create.tool_groups == ["web"]


# ---------------------------------------------------------------------------
# 往返一致性
# ---------------------------------------------------------------------------


class TestExportImportRoundTrip:
    """测试导出再导入的往返一致性。"""

    def test_yaml_roundtrip_fields_preserved(self) -> None:
        """YAML 序列化/反序列化不丢失字段。"""
        config = {
            "name": "roundtrip-agent",
            "description": "往返测试",
            "instructions": "中文指令内容",
            "model": "claude-3",
            "tool_groups": ["web-search", "code-exec"],
            "guardrails": {"input": ["safety"], "output": [], "tool": []},
            "model_settings": {"temperature": 0.7},
        }
        yaml_str = yaml.dump(config, allow_unicode=True, default_flow_style=False)
        parsed = yaml.safe_load(yaml_str)
        for k, v in config.items():
            assert parsed[k] == v, f"字段 {k} 不一致: {parsed[k]} != {v}"

    def test_json_roundtrip_fields_preserved(self) -> None:
        """JSON 序列化/反序列化不丢失字段。"""
        config = {
            "name": "roundtrip-agent",
            "model_settings": {"temperature": 0.5, "top_p": 0.9},
            "metadata": {"team": "infra"},
        }
        json_str = json.dumps(config, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed == config

    def test_export_then_import(self, client: TestClient) -> None:
        """导出 YAML → 解析 → 可作为 AgentCreate 验证通过。"""
        from app.schemas.agent import AgentCreate

        agent = _make_agent_config(name="full-agent", tool_groups=["search", "code"])
        with patch("app.services.agent.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            resp = client.get("/api/v1/agents/full-agent/export?format=yaml")
        exported = yaml.safe_load(resp.text)
        # 应能直接创建 AgentCreate（不抛异常）
        create = AgentCreate(**exported)
        assert create.name == "full-agent"
        assert create.tool_groups == ["search", "code"]
