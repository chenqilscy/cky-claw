"""清理 e2e 测试遗留的脏数据。

用法: cd backend && uv run python scripts/cleanup_e2e_data.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import engine as async_engine

# e2e 数据匹配条件
E2E_WHERE = "name LIKE 'e2e-%' OR name LIKE 'f6-%' OR name LIKE 'minimax-test-%'"
E2E_AGENT_WHERE = E2E_WHERE.replace("name", "agent_name")


def _in_clause(ids: list[str]) -> str:
    """构造安全的 IN (...) 子句，值来自数据库查询结果而非用户输入。"""
    return ", ".join(f"'{i}'" for i in ids)


async def main() -> None:
    """扫描并清理 e2e 测试数据。"""
    async with async_engine.begin() as conn:
        # 1. 扫描 e2e provider
        r = await conn.execute(
            text("SELECT id, name FROM provider_configs WHERE name LIKE 'e2e-provider-%'")
        )
        providers = r.fetchall()
        print(f"[SCAN] e2e providers: {len(providers)}")
        for p in providers:
            print(f"  {p[0]} - {p[1]}")

        # 2. 扫描 e2e/test agent
        r = await conn.execute(text(f"SELECT id, name FROM agent_configs WHERE {E2E_WHERE}"))
        agents = r.fetchall()
        print(f"[SCAN] e2e/test agents: {len(agents)}")
        for a in agents:
            print(f"  {a[0]} - {a[1]}")

        # 3. 扫描 e2e session
        r = await conn.execute(
            text(f"SELECT id FROM sessions WHERE {E2E_AGENT_WHERE}")
        )
        session_rows = r.fetchall()
        session_ids = [str(row[0]) for row in session_rows]
        print(f"[SCAN] e2e sessions: {len(session_ids)}")

        # --- 执行清理 ---
        print("\n--- CLEANUP ---")

        # 删除 session_messages
        if session_ids:
            r2 = await conn.execute(
                text(f"DELETE FROM session_messages WHERE session_id IN ({_in_clause(session_ids)})")
            )
            print(f"  Deleted {r2.rowcount} e2e session_messages")

        # 删除 sessions
        if session_ids:
            r2 = await conn.execute(
                text(f"DELETE FROM sessions WHERE {E2E_AGENT_WHERE}")
            )
            print(f"  Deleted {r2.rowcount} e2e sessions")

        # 删除 traces 关联的 spans
        r2 = await conn.execute(
            text(f"SELECT id FROM traces WHERE {E2E_AGENT_WHERE}")
        )
        trace_ids = [str(row[0]) for row in r2.fetchall()]
        if trace_ids:
            r2 = await conn.execute(
                text(f"DELETE FROM spans WHERE trace_id IN ({_in_clause(trace_ids)})")
            )
            print(f"  Deleted {r2.rowcount} e2e spans")

        # 删除 traces
        r2 = await conn.execute(text(f"DELETE FROM traces WHERE {E2E_AGENT_WHERE}"))
        print(f"  Deleted {r2.rowcount} e2e traces")

        # 删除 agent 版本快照（表可能不存在）
        if agents:
            agent_ids = [str(a[0]) for a in agents]
            table_exists = await conn.execute(
                text("SELECT to_regclass('public.agent_versions')")
            )
            if table_exists.scalar() is not None:
                r2 = await conn.execute(
                    text(f"DELETE FROM agent_versions WHERE agent_id IN ({_in_clause(agent_ids)})")
                )
                print(f"  Deleted {r2.rowcount} e2e agent_versions")
            else:
                print("  [SKIP] agent_versions table does not exist")

        # 删除 agents
        if agents:
            r2 = await conn.execute(text(f"DELETE FROM agent_configs WHERE {E2E_WHERE}"))
            print(f"  Deleted {r2.rowcount} e2e agents")

        # 删除 providers
        if providers:
            r2 = await conn.execute(
                text("DELETE FROM provider_configs WHERE name LIKE 'e2e-provider-%'")
            )
            print(f"  Deleted {r2.rowcount} e2e providers")

        # 删除 token_usage（表可能不存在）
        table_exists = await conn.execute(text("SELECT to_regclass('public.token_usage')"))
        if table_exists.scalar() is not None:
            r2 = await conn.execute(text(f"DELETE FROM token_usage WHERE {E2E_AGENT_WHERE}"))
            print(f"  Deleted {r2.rowcount} e2e token_usage records")
        else:
            print("  [SKIP] token_usage table does not exist")

        print("\n[DONE] Cleanup complete!")


if __name__ == "__main__":
    asyncio.run(main())
