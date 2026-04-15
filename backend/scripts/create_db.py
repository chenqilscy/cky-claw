"""创建 ckyclaw 数据库（如不存在）。"""
import asyncio

import asyncpg


async def main() -> None:
    conn = await asyncpg.connect(
        host="fn.cky", port=15432, user="admin", password="Admin888", database="postgres"
    )
    exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'ckyclaw'")
    if not exists:
        await conn.execute("CREATE DATABASE ckyclaw")
        print("Database ckyclaw created")
    else:
        print("Database ckyclaw already exists")
    await conn.close()


asyncio.run(main())
