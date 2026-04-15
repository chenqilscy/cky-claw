"""Compliance 合规框架数据模型。"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin


class DataClassification(enum.StrEnum):
    """数据分类等级。"""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    PII = "pii"
    PHI = "phi"


class RetentionStatus(enum.StrEnum):
    """保留策略执行状态。"""

    ACTIVE = "active"
    EXPIRED = "expired"
    DELETED = "deleted"


class ErasureStatus(enum.StrEnum):
    """删除请求状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataClassificationLabel(SoftDeleteMixin, Base):
    """数据分类标签 — 标记资源的数据敏感等级。"""

    __tablename__ = "data_classification_labels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="资源类型(trace/session/audit_log/agent)"
    )
    resource_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="资源 ID"
    )
    classification: Mapped[DataClassification] = mapped_column(
        Enum(DataClassification, name="data_classification_enum"),
        nullable=False,
        server_default=text("'internal'"),
        index=True,
    )
    auto_detected: Mapped[bool] = mapped_column(
        default=False, comment="是否自动检测"
    )
    reason: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''"), comment="标记原因"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class RetentionPolicy(SoftDeleteMixin, Base):
    """数据保留策略 — 按数据分类 + 资源类型定义保留天数。"""

    __tablename__ = "retention_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="资源类型"
    )
    classification: Mapped[DataClassification] = mapped_column(
        Enum(DataClassification, name="data_classification_enum", create_type=False),
        nullable=False,
    )
    retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="保留天数"
    )
    status: Mapped[RetentionStatus] = mapped_column(
        Enum(RetentionStatus, name="retention_status_enum"),
        nullable=False,
        server_default=text("'active'"),
    )
    last_executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="上次执行时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ErasureRequest(SoftDeleteMixin, Base):
    """Right-to-Erasure 删除请求。"""

    __tablename__ = "erasure_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
        comment="被删除数据的用户"
    )
    status: Mapped[ErasureStatus] = mapped_column(
        Enum(ErasureStatus, name="erasure_status_enum"),
        nullable=False,
        server_default=text("'pending'"),
        index=True,
    )
    scanned_resources: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="已扫描资源数"
    )
    deleted_resources: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), comment="已删除资源数"
    )
    report: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="合规报告 JSON"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ComplianceControlPoint(SoftDeleteMixin, Base):
    """SOC2 控制点映射 — 将现有安全措施映射到 SOC2 TSC。"""

    __tablename__ = "compliance_control_points"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    control_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True, comment="控制点编号(如 CC6.1)"
    )
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SOC2 TSC 类别"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="控制点描述"
    )
    implementation: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''"), comment="实施说明"
    )
    evidence_links: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="证据链接"
    )
    is_satisfied: Mapped[bool] = mapped_column(
        default=False, comment="是否已满足"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
