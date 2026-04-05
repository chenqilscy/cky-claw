"""PostgresSessionBackend 单元测试 — 使用 mock asyncpg pool 覆盖全部 54 行。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.session.postgres import PostgresSessionBackend
from ckyclaw_framework.session.session import SessionMetadata


class _FakeRow(dict):
    """模拟 asyncpg.Record，支持字典式 + 索引式访问。"""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            return dict.__getitem__(self, key)
        return list(self.values())[key]


def _make_pool() -> MagicMock:
    """创建 mock asyncpg pool。"""
    pool = MagicMock()
    conn = MagicMock()  # 使用 MagicMock 而非 AsyncMock，避免 transaction() 变成 coroutine
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    # conn.transaction() 返回异步上下文管理器（非 coroutine）
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=None)
    tx_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = tx_ctx
    # 将需要 await 的方法设为 AsyncMock
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    return pool, conn


class TestPostgresSessionBackendLoad:
    """load 方法测试。"""

    @pytest.mark.asyncio
    async def test_load_no_rows(self) -> None:
        """无数据 → 返回 None。"""
        pool, conn = _make_pool()
        conn.fetch = AsyncMock(return_value=[])
        backend = PostgresSessionBackend(pool)
        result = await backend.load("session1")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_with_rows(self) -> None:
        """有数据 → 转为 Message 列表。"""
        pool, conn = _make_pool()
        row = _FakeRow({
            "role": "user",
            "content": "hello",
            "agent_name": "agent1",
            "tool_call_id": None,
            "tool_calls": None,
            "token_usage": json.dumps({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            "metadata": json.dumps({"key": "val"}),
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        })
        conn.fetch = AsyncMock(return_value=[row])
        backend = PostgresSessionBackend(pool)
        messages = await backend.load("session1")
        assert messages is not None
        assert len(messages) == 1
        assert messages[0].content == "hello"

    @pytest.mark.asyncio
    async def test_load_with_tool_calls(self) -> None:
        """含 tool_calls 的行。"""
        pool, conn = _make_pool()
        tc_data = [{"id": "tc1", "name": "tool1", "arguments": "{}"}]
        row = _FakeRow({
            "role": "assistant",
            "content": "",
            "agent_name": "agent1",
            "tool_call_id": None,
            "tool_calls": json.dumps(tc_data),
            "token_usage": None,
            "metadata": None,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        })
        conn.fetch = AsyncMock(return_value=[row])
        backend = PostgresSessionBackend(pool)
        messages = await backend.load("session1")
        assert messages is not None
        assert len(messages) == 1


class TestPostgresSessionBackendSave:
    """save 方法测试。"""

    @pytest.mark.asyncio
    async def test_save_empty(self) -> None:
        """空消息列表 → 不执行 SQL。"""
        pool, conn = _make_pool()
        backend = PostgresSessionBackend(pool)
        await backend.save("session1", [])
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_save_messages(self) -> None:
        """保存消息 + 更新元数据。"""
        pool, conn = _make_pool()
        conn.execute = AsyncMock()
        backend = PostgresSessionBackend(pool)

        msgs = [
            Message(role=MessageRole.USER, content="hi"),
            Message(role=MessageRole.ASSISTANT, content="hello", agent_name="bot"),
        ]
        await backend.save("session1", msgs)
        # INSERT 2 次 + 1 次 metadata upsert = 至少 3 次 execute
        assert conn.execute.await_count >= 3

    @pytest.mark.asyncio
    async def test_save_with_token_usage(self) -> None:
        """含 token_usage 的消息序列化。"""
        pool, conn = _make_pool()
        conn.execute = AsyncMock()
        backend = PostgresSessionBackend(pool)

        msg = Message(
            role=MessageRole.ASSISTANT,
            content="response",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        await backend.save("session1", [msg])
        # 验证 execute 被调用（含 JSON 序列化后的 token_usage）
        calls = conn.execute.call_args_list
        # 最少 2 次: 1 INSERT + 1 metadata
        assert len(calls) >= 2

    @pytest.mark.asyncio
    async def test_save_last_agent_detection(self) -> None:
        """自动检测最后一个 agent_name。"""
        pool, conn = _make_pool()
        conn.execute = AsyncMock()
        backend = PostgresSessionBackend(pool)

        msgs = [
            Message(role=MessageRole.USER, content="hi"),
            Message(role=MessageRole.ASSISTANT, content="hello", agent_name="final_agent"),
        ]
        await backend.save("session1", msgs)
        # metadata upsert 的参数中应该有 "final_agent"
        last_call = conn.execute.call_args_list[-1]
        # 第 3 个参数 ($3) 应该是 "final_agent"
        assert "final_agent" in str(last_call)


class TestPostgresSessionBackendDelete:
    """delete 方法测试。"""

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """删除 session 数据。"""
        pool, conn = _make_pool()
        conn.execute = AsyncMock()
        backend = PostgresSessionBackend(pool)
        await backend.delete("session1")
        assert conn.execute.await_count == 2  # messages + metadata


class TestPostgresSessionBackendListSessions:
    """list_sessions 方法测试。"""

    @pytest.mark.asyncio
    async def test_list_empty(self) -> None:
        """无 session。"""
        pool, conn = _make_pool()
        conn.fetch = AsyncMock(return_value=[])
        backend = PostgresSessionBackend(pool)
        result = await backend.list_sessions()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_data(self) -> None:
        """有 session 数据。"""
        pool, conn = _make_pool()
        now = datetime.now(timezone.utc)
        row = _FakeRow({
            "session_id": "s1",
            "message_count": 5,
            "total_tokens": 100,
            "last_agent": "agent1",
            "extra": json.dumps({"key": "val"}),
            "created_at": now,
            "updated_at": now,
        })
        conn.fetch = AsyncMock(return_value=[row])
        backend = PostgresSessionBackend(pool)
        result = await backend.list_sessions()
        assert len(result) == 1
        assert result[0].session_id == "s1"
        assert result[0].message_count == 5

    @pytest.mark.asyncio
    async def test_list_null_extra(self) -> None:
        """extra 为 None 时不崩溃。"""
        pool, conn = _make_pool()
        now = datetime.now(timezone.utc)
        row = _FakeRow({
            "session_id": "s1",
            "message_count": 0,
            "total_tokens": 0,
            "last_agent": None,
            "extra": None,
            "created_at": now,
            "updated_at": now,
        })
        conn.fetch = AsyncMock(return_value=[row])
        backend = PostgresSessionBackend(pool)
        result = await backend.list_sessions()
        assert result[0].extra == {}


class TestPostgresSessionBackendLoadMetadata:
    """load_metadata 方法测试。"""

    @pytest.mark.asyncio
    async def test_load_metadata_none(self) -> None:
        """不存在 → None。"""
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value=None)
        backend = PostgresSessionBackend(pool)
        result = await backend.load_metadata("session_x")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_metadata_found(self) -> None:
        """存在 → SessionMetadata。"""
        pool, conn = _make_pool()
        now = datetime.now(timezone.utc)
        row = _FakeRow({
            "session_id": "s1",
            "message_count": 10,
            "total_tokens": 200,
            "last_agent": "bot",
            "extra": json.dumps({}),
            "created_at": now,
            "updated_at": now,
        })
        conn.fetchrow = AsyncMock(return_value=row)
        backend = PostgresSessionBackend(pool)
        result = await backend.load_metadata("s1")
        assert result is not None
        assert result.session_id == "s1"
        assert result.message_count == 10


class TestDDL:
    """DDL 常量测试。"""

    def test_ddl_contains_tables(self) -> None:
        """DDL 包含建表语句。"""
        assert "session_messages" in PostgresSessionBackend.DDL
        assert "session_metadata" in PostgresSessionBackend.DDL
