"""检查数据库表和迁移状态。"""
from __future__ import annotations

import asyncio

import asyncpg


async def main() -> None:
    c = await asyncpg.connect("postgresql://admin:Admin888@fn.cky:15432/kasaya")
    tables = await c.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    print(f"=== 共 {len(tables)} 张表 ===")
    for t in tables:
        print(f"  {t['tablename']}")

    # 检查 alembic_version
    try:
        ver = await c.fetchval("SELECT version_num FROM alembic_version")
        print(f"\n=== Alembic 当前版本: {ver} ===")
    except Exception as e:
        print(f"\n=== Alembic 版本表不存在: {e} ===")

    await c.close()


asyncio.run(main())
