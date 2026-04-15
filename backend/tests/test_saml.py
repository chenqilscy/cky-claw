"""SAML 2.0 SSO 接口测试。"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree import ElementTree as ET

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE_URL = "http://test"
PREFIX = "/api/v1/auth/saml"


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- 辅助工具 ----


def _make_idp_config(**overrides):
    """构造 SamlIdpConfig mock 对象。"""
    defaults = {
        "id": uuid.uuid4(),
        "name": "Test IdP",
        "entity_id": "https://idp.example.com/metadata",
        "sso_url": "https://idp.example.com/sso",
        "slo_url": "",
        "x509_cert": "MIICdummy...",
        "metadata_xml": None,
        "attribute_mapping": {"email": "urn:oid:0.9.2342.19200300.100.1.3"},
        "is_enabled": True,
        "is_default": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)

    config = MagicMock()
    for k, v in defaults.items():
        setattr(config, k, v)
    return config


def _build_saml_response_xml(
    issuer: str = "https://idp.example.com/metadata",
    name_id: str = "user@example.com",
    in_response_to: str | None = None,
    audience: str = "https://sp.example.com",
    status: str = "urn:oasis:names:tc:SAML:2.0:status:Success",
) -> str:
    """构建最小化合法的 SAML Response XML。"""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    in_resp = f' InResponseTo="{in_response_to}"' if in_response_to else ""
    return (
        f'<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
        f' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
        f' ID="_resp123" Version="2.0" IssueInstant="{now}"{in_resp}>'
        f'<samlp:Status><samlp:StatusCode Value="{status}"/></samlp:Status>'
        f'<saml:Assertion Version="2.0" ID="_assert123" IssueInstant="{now}">'
        f'<saml:Issuer>{issuer}</saml:Issuer>'
        f'<saml:Subject><saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID></saml:Subject>'
        f'<saml:Conditions NotBefore="2020-01-01T00:00:00Z" NotOnOrAfter="2099-12-31T23:59:59Z">'
        f'<saml:AudienceRestriction><saml:Audience>{audience}</saml:Audience></saml:AudienceRestriction>'
        f'</saml:Conditions>'
        f'<saml:AttributeStatement>'
        f'<saml:Attribute Name="urn:oid:0.9.2342.19200300.100.1.3"><saml:AttributeValue>{name_id}</saml:AttributeValue></saml:Attribute>'
        f'</saml:AttributeStatement>'
        f'</saml:Assertion>'
        f'</samlp:Response>'
    )


# ---- SP 元数据测试 ----


class TestSpMetadata:
    """SP 元数据端点测试。"""

    @pytest.mark.anyio
    async def test_get_sp_metadata_success(self):
        """SP 配置完整时返回元数据。"""
        with (
            patch("app.services.saml_service.settings") as mock_svc_settings,
            patch("app.api.saml.settings") as mock_api_settings,
        ):
            for s in (mock_svc_settings, mock_api_settings):
                s.saml_sp_entity_id = "https://sp.example.com"
                s.saml_sp_acs_url = "https://sp.example.com/acs"
                s.saml_sp_sls_url = ""
                s.saml_sp_x509_cert = ""
                s.access_token_expire_minutes = 1440

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/metadata")
                assert resp.status_code == 200
                data = resp.json()
                assert data["entity_id"] == "https://sp.example.com"
                assert "metadata_xml" in data

    @pytest.mark.anyio
    async def test_get_sp_metadata_xml(self):
        """返回 XML 格式的 SP 元数据。"""
        with patch("app.services.saml_service.settings") as mock_settings:
            mock_settings.saml_sp_entity_id = "https://sp.example.com"
            mock_settings.saml_sp_acs_url = "https://sp.example.com/acs"
            mock_settings.saml_sp_sls_url = ""
            mock_settings.saml_sp_x509_cert = ""

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/metadata.xml")
                assert resp.status_code == 200
                assert "application/xml" in resp.headers.get("content-type", "")

    @pytest.mark.anyio
    async def test_get_sp_metadata_not_configured(self):
        """SP 未配置时返回错误。"""
        with patch("app.services.saml_service.settings") as mock_settings:
            mock_settings.saml_sp_entity_id = ""
            mock_settings.saml_sp_acs_url = ""

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/metadata")
                assert resp.status_code in (400, 422)


# ---- IdP 配置 CRUD 测试 ----


class TestIdpConfigCrud:
    """IdP 配置管理测试。"""

    @pytest.mark.anyio
    async def test_list_idp_configs(self):
        """获取 IdP 配置列表。"""
        mock_configs = [_make_idp_config()]
        with patch("app.services.saml_service.list_idp_configs", new_callable=AsyncMock, return_value=mock_configs):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/idp-configs")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1

    @pytest.mark.anyio
    async def test_create_idp_config(self):
        """创建 IdP 配置。"""
        mock_config = _make_idp_config()
        with patch("app.services.saml_service.create_idp_config", new_callable=AsyncMock, return_value=mock_config):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.post(
                    f"{PREFIX}/idp-configs",
                    json={
                        "name": "Test IdP",
                        "entity_id": "https://idp.example.com",
                        "sso_url": "https://idp.example.com/sso",
                        "x509_cert": "MIICdummy...",
                    },
                )
                assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_idp_config_validation(self):
        """创建 IdP 配置缺少必填字段。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=BASE_URL
        ) as client:
            resp = await client.post(
                f"{PREFIX}/idp-configs",
                json={"name": ""},
            )
            assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_get_idp_config(self):
        """获取指定 IdP 配置。"""
        mock_config = _make_idp_config()
        with patch("app.services.saml_service.get_idp_config", new_callable=AsyncMock, return_value=mock_config):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/idp-configs/{mock_config.id}")
                assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_idp_config(self):
        """更新 IdP 配置。"""
        mock_config = _make_idp_config()
        with patch("app.services.saml_service.update_idp_config", new_callable=AsyncMock, return_value=mock_config):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.patch(
                    f"{PREFIX}/idp-configs/{mock_config.id}",
                    json={"name": "Updated IdP"},
                )
                assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_delete_idp_config(self):
        """删除 IdP 配置。"""
        with patch("app.services.saml_service.delete_idp_config", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.delete(f"{PREFIX}/idp-configs/{uuid.uuid4()}")
                assert resp.status_code == 204


# ---- SAML 登录流程测试 ----


class TestSamlLogin:
    """SAML SSO 登录流程测试。"""

    @pytest.mark.anyio
    async def test_saml_login_success(self):
        """成功发起 SAML 登录。"""
        with patch(
            "app.services.saml_service.create_authn_request",
            new_callable=AsyncMock,
            return_value=("https://idp.example.com/sso?SAMLRequest=xxx", "_req123"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.post(f"{PREFIX}/login", json={})
                assert resp.status_code == 200
                data = resp.json()
                assert "redirect_url" in data

    @pytest.mark.anyio
    async def test_saml_login_with_idp_id(self):
        """指定 IdP ID 发起登录。"""
        idp_id = str(uuid.uuid4())
        with patch(
            "app.services.saml_service.create_authn_request",
            new_callable=AsyncMock,
            return_value=("https://idp.example.com/sso?SAMLRequest=xxx", "_req456"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.post(f"{PREFIX}/login", json={"idp_id": idp_id})
                assert resp.status_code == 200


# ---- ACS 测试 ----


class TestAcs:
    """SAML ACS (Assertion Consumer Service) 测试。"""

    @pytest.mark.anyio
    async def test_acs_success(self):
        """成功处理 SAML Response。"""
        jwt_token = "eyJ..."
        with patch(
            "app.services.saml_service.process_saml_response",
            new_callable=AsyncMock,
            return_value=jwt_token,
        ), patch("app.api.saml.settings") as mock_settings:
            mock_settings.access_token_expire_minutes = 1440
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.post(
                    f"{PREFIX}/acs",
                    data={
                        "SAMLResponse": base64.b64encode(b"<xml/>").decode(),
                        "RelayState": "",
                    },
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["access_token"] == jwt_token

    @pytest.mark.anyio
    async def test_acs_missing_saml_response(self):
        """缺少 SAMLResponse 参数。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=BASE_URL
        ) as client:
            resp = await client.post(f"{PREFIX}/acs", data={})
            assert resp.status_code == 422


# ---- 公开查询测试 ----


class TestEnabledIdps:
    """已启用 IdP 列表测试。"""

    @pytest.mark.anyio
    async def test_get_enabled_idps(self):
        """返回已启用的 IdP 列表。"""
        mock_config = _make_idp_config(is_enabled=True)
        disabled_config = _make_idp_config(is_enabled=False, name="Disabled IdP")
        with patch(
            "app.services.saml_service.list_idp_configs",
            new_callable=AsyncMock,
            return_value=[mock_config, disabled_config],
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=BASE_URL
            ) as client:
                resp = await client.get(f"{PREFIX}/enabled-idps")
                assert resp.status_code == 200
                data = resp.json()
                # 只返回启用的
                assert len(data["idps"]) == 1
                assert data["idps"][0]["name"] == "Test IdP"


# ---- Service 单元测试 ----


class TestSamlServiceUnit:
    """SAML Service 纯函数/生成器测试。"""

    def test_generate_sp_metadata(self):
        """生成 SP 元数据 XML。"""
        from app.services.saml_service import generate_sp_metadata

        with patch("app.services.saml_service.settings") as mock_settings:
            mock_settings.saml_sp_entity_id = "https://sp.test.com"
            mock_settings.saml_sp_acs_url = "https://sp.test.com/acs"
            mock_settings.saml_sp_sls_url = "https://sp.test.com/sls"
            mock_settings.saml_sp_x509_cert = ""

            xml = generate_sp_metadata()
            assert "https://sp.test.com" in xml
            assert "AssertionConsumerService" in xml
            assert "SingleLogoutService" in xml

    def test_generate_sp_metadata_with_cert(self):
        """SP 元数据包含签名证书。"""
        from app.services.saml_service import generate_sp_metadata

        with patch("app.services.saml_service.settings") as mock_settings:
            mock_settings.saml_sp_entity_id = "https://sp.test.com"
            mock_settings.saml_sp_acs_url = "https://sp.test.com/acs"
            mock_settings.saml_sp_sls_url = ""
            mock_settings.saml_sp_x509_cert = "MIICdummy..."

            xml = generate_sp_metadata()
            assert "MIICdummy..." in xml
            assert "KeyDescriptor" in xml

    def test_generate_sp_metadata_not_configured(self):
        """SP 未配置时抛出异常。"""
        from app.core.exceptions import ValidationError
        from app.services.saml_service import generate_sp_metadata

        with patch("app.services.saml_service.settings") as mock_settings:
            mock_settings.saml_sp_entity_id = ""
            mock_settings.saml_sp_acs_url = ""

            with pytest.raises(ValidationError):
                generate_sp_metadata()

    def test_extract_attributes(self):
        """从 SAML Assertion 提取属性。"""
        from app.services.saml_service import _extract_attributes

        xml = (
            '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
            '<saml:AttributeStatement>'
            '<saml:Attribute Name="urn:oid:email">'
            '<saml:AttributeValue>john@example.com</saml:AttributeValue>'
            '</saml:Attribute>'
            '<saml:Attribute Name="urn:oid:name">'
            '<saml:AttributeValue>john</saml:AttributeValue>'
            '</saml:Attribute>'
            '</saml:AttributeStatement>'
            '</saml:Assertion>'
        )
        assertion = ET.fromstring(xml)
        mapping = {"email": "urn:oid:email", "username": "urn:oid:name"}
        attrs = _extract_attributes(assertion, mapping)
        assert attrs["email"] == "john@example.com"
        assert attrs["username"] == "john"

    def test_extract_attributes_default_mapping(self):
        """无映射时使用默认属性名匹配。"""
        from app.services.saml_service import _extract_attributes

        xml = (
            '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
            '<saml:AttributeStatement>'
            '<saml:Attribute Name="email">'
            '<saml:AttributeValue>auto@example.com</saml:AttributeValue>'
            '</saml:Attribute>'
            '</saml:AttributeStatement>'
            '</saml:Assertion>'
        )
        assertion = ET.fromstring(xml)
        attrs = _extract_attributes(assertion, {})
        assert attrs["email"] == "auto@example.com"

    def test_xml_escape(self):
        """XML 转义。"""
        from app.services.saml_service import _xml_escape

        assert _xml_escape('a&b<c>d"e') == 'a&amp;b&lt;c&gt;d&quot;e'

    @pytest.mark.anyio
    async def test_process_saml_response_bad_base64(self):
        """无效 Base64 输入。"""
        from app.core.exceptions import AuthenticationError
        from app.services.saml_service import process_saml_response

        mock_db = AsyncMock()
        with pytest.raises(AuthenticationError, match="解码失败"):
            await process_saml_response(mock_db, "!!!invalid!!!")

    @pytest.mark.anyio
    async def test_process_saml_response_bad_xml(self):
        """无效 XML。"""
        from app.core.exceptions import AuthenticationError
        from app.services.saml_service import process_saml_response

        mock_db = AsyncMock()
        encoded = base64.b64encode(b"not xml").decode()
        with pytest.raises(AuthenticationError, match="XML 解析失败"):
            await process_saml_response(mock_db, encoded)

    @pytest.mark.anyio
    async def test_process_saml_response_failed_status(self):
        """SAML 认证失败状态。"""
        from app.core.exceptions import AuthenticationError
        from app.services.saml_service import process_saml_response

        mock_db = AsyncMock()
        xml = _build_saml_response_xml(
            status="urn:oasis:names:tc:SAML:2.0:status:Requester"
        )
        encoded = base64.b64encode(xml.encode()).decode()
        with pytest.raises(AuthenticationError, match="认证失败"):
            await process_saml_response(mock_db, encoded)

    @pytest.mark.anyio
    async def test_process_saml_response_success(self):
        """完整的 SAML Response 处理流程。"""
        from app.services.saml_service import process_saml_response

        mock_db = AsyncMock()
        idp_config = _make_idp_config()

        # Mock 数据库查询
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = idp_config
        mock_db.execute.return_value = mock_result

        xml = _build_saml_response_xml(
            issuer="https://idp.example.com/metadata",
            name_id="testuser@example.com",
            audience="https://sp.example.com",
        )
        encoded = base64.b64encode(xml.encode()).decode()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.role = "user"

        with (
            patch("app.services.saml_service.settings") as mock_settings,
            patch(
                "app.services.saml_service._find_or_create_saml_user",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
        ):
            mock_settings.saml_sp_entity_id = "https://sp.example.com"

            token = await process_saml_response(mock_db, encoded)
            assert isinstance(token, str)
            assert len(token) > 0
