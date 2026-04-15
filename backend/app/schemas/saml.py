"""SAML 2.0 请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- IdP 配置 CRUD ----


class SamlIdpConfigCreate(BaseModel):
    """创建 SAML IdP 配置请求。"""

    name: str = Field(..., min_length=1, max_length=128, description="IdP 显示名称")
    entity_id: str = Field(..., min_length=1, max_length=512, description="IdP Entity ID")
    sso_url: str = Field(..., min_length=1, max_length=1024, description="SSO URL")
    slo_url: str = Field("", max_length=1024, description="SLO URL")
    x509_cert: str = Field(..., min_length=1, description="X.509 证书（PEM 格式，不含头尾标记）")
    metadata_xml: str | None = Field(None, description="完整 IdP 元数据 XML")
    attribute_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="属性映射：{email, username, display_name, groups} → SAML Attribute Name",
    )
    is_enabled: bool = True
    is_default: bool = False


class SamlIdpConfigUpdate(BaseModel):
    """更新 SAML IdP 配置请求。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    entity_id: str | None = Field(None, min_length=1, max_length=512)
    sso_url: str | None = Field(None, min_length=1, max_length=1024)
    slo_url: str | None = Field(None, max_length=1024)
    x509_cert: str | None = Field(None, min_length=1)
    metadata_xml: str | None = None
    attribute_mapping: dict[str, str] | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None


class SamlIdpConfigResponse(BaseModel):
    """SAML IdP 配置响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    entity_id: str
    sso_url: str
    slo_url: str
    x509_cert: str
    metadata_xml: str | None = None
    attribute_mapping: dict[str, str]
    is_enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ---- SAML 登录流程 ----


class SamlLoginRequest(BaseModel):
    """SAML 登录请求 — 可选指定 IdP ID。"""

    idp_id: uuid.UUID | None = Field(None, description="指定 IdP ID，为空则使用默认 IdP")


class SamlLoginResponse(BaseModel):
    """SAML 登录响应 — 返回 AuthnRequest 重定向信息。"""

    redirect_url: str = Field(..., description="IdP SSO 重定向 URL（含 SAMLRequest 参数）")


class SamlSpMetadataResponse(BaseModel):
    """SP 元数据响应。"""

    entity_id: str
    acs_url: str
    sls_url: str
    metadata_xml: str
