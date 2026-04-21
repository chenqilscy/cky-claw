"""创建 kasaya 数据库（如不存在）。"""
import asyncio

import asyncpg


async def main() -> None:
    conn = await asyncpg.connect(
        host="fn.cky", port=15432, user="admin", password="Admin888", database="postgres"
    )
    exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'kasaya'")
    if not exists:
        await conn.execute("CREATE DATABASE kasaya")
        print("Database kasaya created")
    else:
        print("Database kasaya already exists")
    await conn.close()


asyncio.run(main())
