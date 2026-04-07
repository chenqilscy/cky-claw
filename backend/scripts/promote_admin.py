"""临时脚本：将 admin 用户提升为 admin 角色。"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import engine


async def main() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE users SET role = 'admin' WHERE username = 'admin' RETURNING id, username, role")
        )
        for row in result.fetchall():
            print(f"Updated: id={row[0]}, username={row[1]}, role={row[2]}")


if __name__ == "__main__":
    asyncio.run(main())
