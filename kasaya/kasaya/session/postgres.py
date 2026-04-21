"""PostgresSessionBackend — PostgreSQL 存储后端。

依赖 asyncpg，安装方式：
    pip install kasaya[postgres]
    # 或
    uv add kasaya[postgres]

首次使用前需建表，DDL 见 PostgresSessionBackend.DDL 常量。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from kasaya.model.message import Message
from kasaya.session.session import SessionBackend, SessionMetadata

logger = logging.getLogger(__name__)

# DDL: 建表脚本
DDL = """\
CREATE TABLE IF NOT EXISTS session_messages (
    id          BIGSERIAL    PRIMARY KEY,
    session_id  VARCHAR(128) NOT NULL,
    role        VARCHAR(16)  NOT NULL,
    content     TEXT         NOT NULL DEFAULT '',
    agent_name  VARCHAR(64),
    tool_call_id VARCHAR(64),
    tool_calls  JSONB,
    token_usage JSONB,
    metadata    JSONB        DEFAULT '{}',
    created_at  TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_messages_session
    ON session_messages(session_id, id);

CREATE TABLE IF NOT EXISTS session_metadata (
    session_id    VARCHAR(128) PRIMARY KEY,
    message_count INTEGER      DEFAULT 0,
    total_tokens  INTEGER      DEFAULT 0,
    last_agent    VARCHAR(64),
    extra         JSONB        DEFAULT '{}',
    created_at    TIMESTAMPTZ  DEFAULT now(),
    updated_at    TIMESTAMPTZ  DEFAULT now()
);
"""


class PostgresSessionBackend(SessionBackend):
    """PostgreSQL 存储后端——适合生产环境持久化。

    需要 asyncpg 连接池。使用前确保已执行 DDL 建表。

    用法：
        import asyncpg
        pool = await asyncpg.create_pool(dsn="postgresql://user:pass@host/db")
        backend = PostgresSessionBackend(pool)
    """

    DDL = DDL

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def load(self, session_id: str) -> list[Message] | None:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content, agent_name, tool_call_id, tool_calls, "
                "token_usage, metadata, created_at "
                "FROM session_messages WHERE session_id = $1 ORDER BY id",
                session_id,
            )
            if not rows:
                return None
            messages: list[Message] = []
            for row in rows:
                data: dict[str, Any] = {
                    "role": row["role"],
                    "content": row["content"] or "",
                    "agent_name": row["agent_name"],
                    "tool_call_id": row["tool_call_id"],
                    "tool_calls": json.loads(row["tool_calls"]) if row["tool_calls"] else None,
                    "token_usage": json.loads(row["token_usage"]) if row["token_usage"] else None,
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "timestamp": row["created_at"].isoformat(),
                }
                messages.append(Message.from_dict(data))
            return messages

    async def save(self, session_id: str, messages: list[Message]) -> None:
        if not messages:
            return
        async with self._pool.acquire() as conn, conn.transaction():
            for msg in messages:
                await conn.execute(
                    "INSERT INTO session_messages "
                    "(session_id, role, content, agent_name, tool_call_id, "
                    "tool_calls, token_usage, metadata) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                    session_id,
                    msg.role.value,
                    msg.content,
                    msg.agent_name,
                    msg.tool_call_id,
                    json.dumps(msg.tool_calls) if msg.tool_calls else None,
                    json.dumps({
                        "prompt_tokens": msg.token_usage.prompt_tokens,
                        "completion_tokens": msg.token_usage.completion_tokens,
                        "total_tokens": msg.token_usage.total_tokens,
                    }) if msg.token_usage else None,
                    json.dumps(msg.metadata) if msg.metadata else "{}",
                )
            # 更新元数据
            last_agent = None
            for m in reversed(messages):
                if m.agent_name:
                    last_agent = m.agent_name
                    break
            await conn.execute(
                "INSERT INTO session_metadata (session_id, message_count, last_agent, updated_at) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (session_id) DO UPDATE SET "
                "message_count = session_metadata.message_count + $2, "
                "last_agent = COALESCE($3, session_metadata.last_agent), "
                "updated_at = $4",
                session_id,
                len(messages),
                last_agent,
                datetime.now(UTC),
            )

    async def delete(self, session_id: str) -> None:
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute("DELETE FROM session_messages WHERE session_id = $1", session_id)
            await conn.execute("DELETE FROM session_metadata WHERE session_id = $1", session_id)

    async def list_sessions(self, **filters: Any) -> list[SessionMetadata]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT session_id, message_count, total_tokens, last_agent, "
                "extra, created_at, updated_at FROM session_metadata ORDER BY updated_at DESC",
            )
            result: list[SessionMetadata] = []
            for row in rows:
                result.append(SessionMetadata(
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    message_count=row["message_count"],
                    total_tokens=row["total_tokens"],
                    last_agent_name=row["last_agent"],
                    extra=json.loads(row["extra"]) if row["extra"] else {},
                ))
            return result

    async def load_metadata(self, session_id: str) -> SessionMetadata | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT session_id, message_count, total_tokens, last_agent, "
                "extra, created_at, updated_at FROM session_metadata WHERE session_id = $1",
                session_id,
            )
            if row is None:
                return None
            return SessionMetadata(
                session_id=row["session_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=row["message_count"],
                total_tokens=row["total_tokens"],
                last_agent_name=row["last_agent"],
                extra=json.loads(row["extra"]) if row["extra"] else {},
            )
