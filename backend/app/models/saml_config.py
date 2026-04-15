"""SAML 2.0 IdP 配置数据模型。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SamlIdpConfig(Base):
    """SAML IdP 配置表 — 存储每个 IdP 的元数据和属性映射。

    支持多 IdP 同时配置，按 entity_id 唯一标识。
    """

    __tablename__ = "saml_idp_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="IdP 显示名称"
    )
    entity_id: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True, comment="IdP Entity ID"
    )
    sso_url: Mapped[str] = mapped_column(
        String(1024), nullable=False, comment="IdP SSO URL (HTTP-Redirect / HTTP-POST)"
    )
    slo_url: Mapped[str] = mapped_column(
        String(1024), nullable=False, server_default=text("''"), comment="IdP SLO URL"
    )
    x509_cert: Mapped[str] = mapped_column(
        Text, nullable=False, comment="IdP X.509 签名证书（PEM 格式，不含头尾）"
    )
    metadata_xml: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="IdP 完整元数据 XML（可选，方便导出）"
    )
    attribute_mapping: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="SAML 属性映射：{email, username, display_name, groups} → SAML Attribute Name",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), comment="是否启用"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), comment="是否为默认 IdP"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )
