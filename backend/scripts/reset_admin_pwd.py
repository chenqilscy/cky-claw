"""重置 admin 用户密码。"""
from __future__ import annotations

import asyncio

import bcrypt
from sqlalchemy import text

from app.core.database import engine


async def main() -> None:
    hashed = bcrypt.hashpw("Admin888!".encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    async with engine.begin() as conn:
        r = await conn.execute(
            text("UPDATE users SET hashed_password = :pw WHERE username = 'admin' RETURNING id, username, role"),
            {"pw": hashed},
        )
        rows = r.fetchall()
        if not rows:
            print("No admin user found")
        for row in rows:
            print(f"Reset: id={row[0]}, username={row[1]}, role={row[2]}")


if __name__ == "__main__":
    asyncio.run(main())
