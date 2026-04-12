"""PostgresSkillPersistence 单元测试 — 使用 mock DB 验证核心逻辑。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.skills.factory import SkillDefinition


class _FakeResult:
    """模拟 SQLAlchemy execute 返回。"""

    def __init__(self, records: list) -> None:
        self._records = records

    def scalar_one_or_none(self):
        return self._records[0] if self._records else None

    def scalars(self):
        return self

    def all(self):
        return self._records


class _FakeSkillRecord:
    """模拟 SkillRecord ORM。"""

    def __init__(self, *, name: str, description: str, content: str,
                 category: str, metadata_: dict, created_at: datetime | None = None,
                 is_deleted: bool = False, deleted_at: datetime | None = None) -> None:
        self.name = name
        self.description = description
        self.content = content
        self.category = category
        self.metadata_ = metadata_
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.is_deleted = is_deleted
        self.deleted_at = deleted_at


@pytest.fixture()
def mock_db():
    """创建 mock AsyncSession。"""
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_save_new_skill(mock_db: AsyncMock) -> None:
    """保存新技能应调用 db.add。"""
    from app.services.skill_factory_persistence import PostgresSkillPersistence

    mock_db.execute.return_value = _FakeResult([])

    persistence = PostgresSkillPersistence(mock_db)
    defn = SkillDefinition(
        name="test_tool",
        description="测试工具",
        code='async def test_tool():\n    return "ok"',
        parameters_schema={"type": "object", "properties": {}},
    )

    await persistence.save("agent-x", defn)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_save_update_existing(mock_db: AsyncMock) -> None:
    """保存已存在的技能应更新而非新增。"""
    from app.services.skill_factory_persistence import PostgresSkillPersistence

    existing = _FakeSkillRecord(
        name="test_tool",
        description="旧描述",
        content="old code",
        category="agent-created",
        metadata_={"agent_name": "agent-x"},
    )
    mock_db.execute.return_value = _FakeResult([existing])

    persistence = PostgresSkillPersistence(mock_db)
    defn = SkillDefinition(
        name="test_tool",
        description="新描述",
        code='async def test_tool():\n    return "new"',
    )

    await persistence.save("agent-x", defn)

    assert existing.description == "新描述"
    assert existing.content == 'async def test_tool():\n    return "new"'
    mock_db.add.assert_not_called()  # 更新不应 add
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_load_agent_skills(mock_db: AsyncMock) -> None:
    """加载应返回对应 Agent 的技能定义。"""
    from app.services.skill_factory_persistence import PostgresSkillPersistence

    records = [
        _FakeSkillRecord(
            name="tool_a",
            description="工具 A",
            content='async def tool_a():\n    return "a"',
            category="agent-created",
            metadata_={"agent_name": "agent-1", "parameters_schema": {}, "test_cases": []},
        ),
        _FakeSkillRecord(
            name="tool_b",
            description="工具 B",
            content='async def tool_b():\n    return "b"',
            category="agent-created",
            metadata_={"agent_name": "agent-2", "parameters_schema": {}, "test_cases": []},
        ),
    ]
    mock_db.execute.return_value = _FakeResult(records)

    persistence = PostgresSkillPersistence(mock_db)
    definitions = await persistence.load("agent-1")

    assert len(definitions) == 1
    assert definitions[0].name == "tool_a"
    assert definitions[0].agent_name == "agent-1"


@pytest.mark.asyncio
async def test_delete_skill(mock_db: AsyncMock) -> None:
    """删除技能应软删除。"""
    from app.services.skill_factory_persistence import PostgresSkillPersistence

    record = _FakeSkillRecord(
        name="to_delete",
        description="待删除",
        content="code",
        category="agent-created",
        metadata_={"agent_name": "agent-x"},
    )
    mock_db.execute.return_value = _FakeResult([record])

    persistence = PostgresSkillPersistence(mock_db)
    result = await persistence.delete("agent-x", "to_delete")

    assert result is True
    assert record.is_deleted is True
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_nonexistent(mock_db: AsyncMock) -> None:
    """删除不存在的技能应返回 False。"""
    from app.services.skill_factory_persistence import PostgresSkillPersistence

    mock_db.execute.return_value = _FakeResult([])

    persistence = PostgresSkillPersistence(mock_db)
    result = await persistence.delete("agent-x", "nonexistent")

    assert result is False


@pytest.mark.asyncio
async def test_delete_wrong_agent(mock_db: AsyncMock) -> None:
    """删除其他 Agent 的技能应返回 False。"""
    from app.services.skill_factory_persistence import PostgresSkillPersistence

    record = _FakeSkillRecord(
        name="other_tool",
        description="其他 Agent 的工具",
        content="code",
        category="agent-created",
        metadata_={"agent_name": "agent-y"},
    )
    mock_db.execute.return_value = _FakeResult([record])

    persistence = PostgresSkillPersistence(mock_db)
    result = await persistence.delete("agent-x", "other_tool")

    assert result is False
    assert record.is_deleted is False
