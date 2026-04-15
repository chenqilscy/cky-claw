"""PostgresSkillPersistence — 将 Agent 自创建技能持久化到 PostgreSQL。

桥接 Framework 的 SkillPersistence ABC 到 Backend 的 SkillRecord ORM。
技能存储在 skills 表中，category='agent-created'，agent_name 存于 metadata。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.skill import SkillRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 使用延迟导入避免 Framework 未安装时的 ImportError
_FACTORY_IMPORTED = False
_SkillPersistence: type | None = None
_SkillDefinition: type | None = None


def _ensure_imports() -> None:
    """延迟导入 Framework 类型。"""
    global _FACTORY_IMPORTED, _SkillPersistence, _SkillDefinition  # noqa: PLW0603
    if not _FACTORY_IMPORTED:
        from ckyclaw_framework.skills.factory import (
            SkillDefinition,
            SkillPersistence,
        )
        _SkillPersistence = SkillPersistence
        _SkillDefinition = SkillDefinition
        _FACTORY_IMPORTED = True


# Agent 自创建技能的固定分类标识
_AGENT_CREATED_CATEGORY = "agent-created"


class PostgresSkillPersistence:
    """PostgreSQL 持久化后端 — 实现 SkillPersistence ABC。

    将 Agent 自创建的 SkillDefinition 存储到 skills 表中，
    通过 category='agent-created' 和 metadata.agent_name 区分。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        _ensure_imports()

    async def save(self, agent_name: str, definition: Any) -> None:
        """保存技能定义。同名覆盖。"""
        stmt = select(SkillRecord).where(
            SkillRecord.name == definition.name,
            SkillRecord.category == _AGENT_CREATED_CATEGORY,
            SkillRecord.is_deleted == False,  # noqa: E712
        )
        existing = (await self._db.execute(stmt)).scalar_one_or_none()

        metadata: dict[str, Any] = {
            "agent_name": agent_name,
            "parameters_schema": definition.parameters_schema,
            "test_cases": definition.test_cases,
        }

        if existing is not None:
            existing.description = definition.description
            existing.content = definition.code
            existing.category = _AGENT_CREATED_CATEGORY
            existing.metadata_ = metadata
            existing.updated_at = datetime.now(UTC)
        else:
            record = SkillRecord(
                name=definition.name,
                version="1.0.0",
                description=definition.description,
                content=definition.code,
                category=_AGENT_CREATED_CATEGORY,
                tags=["agent-created"],
                applicable_agents=[agent_name],
                author=f"agent:{agent_name}",
                metadata_=metadata,
            )
            self._db.add(record)

        await self._db.commit()
        logger.info("保存 Agent '%s' 自创建技能 '%s'", agent_name, definition.name)

    async def load(self, agent_name: str) -> list[Any]:
        """加载指定 Agent 的所有自创建技能。"""
        _ensure_imports()
        assert _SkillDefinition is not None

        stmt = select(SkillRecord).where(
            SkillRecord.category == _AGENT_CREATED_CATEGORY,
            SkillRecord.is_deleted == False,  # noqa: E712
        )
        result = await self._db.execute(stmt)
        records = result.scalars().all()

        definitions: list[Any] = []
        for r in records:
            meta = r.metadata_ or {}
            if meta.get("agent_name") != agent_name:
                continue
            definitions.append(_SkillDefinition(
                name=r.name,
                description=r.description,
                parameters_schema=meta.get("parameters_schema", {}),
                code=r.content,
                test_cases=meta.get("test_cases", []),
                agent_name=agent_name,
                created_at=r.created_at,
            ))

        return definitions

    async def delete(self, agent_name: str, skill_name: str) -> bool:
        """软删除技能。"""
        stmt = select(SkillRecord).where(
            SkillRecord.name == skill_name,
            SkillRecord.category == _AGENT_CREATED_CATEGORY,
            SkillRecord.is_deleted == False,  # noqa: E712
        )
        record = (await self._db.execute(stmt)).scalar_one_or_none()

        if record is None:
            return False

        meta = record.metadata_ or {}
        if meta.get("agent_name") != agent_name:
            return False

        record.is_deleted = True
        record.deleted_at = datetime.now(UTC)
        await self._db.commit()
        logger.info("删除 Agent '%s' 自创建技能 '%s'", agent_name, skill_name)
        return True

    async def list_all(self, agent_name: str) -> list[Any]:
        """列出指定 Agent 的技能（含 code）。"""
        return await self.load(agent_name)


# 注册为 SkillPersistence 子类（运行时 ABC 注册）
def _register_abc() -> None:
    """在 import 时注册 ABC，使 isinstance 检查生效。"""
    try:
        _ensure_imports()
        if _SkillPersistence is not None:
            _SkillPersistence.register(PostgresSkillPersistence)  # type: ignore[attr-defined]
    except ImportError:
        pass


_register_abc()
