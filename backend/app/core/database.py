"""数据库连接管理。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""

    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """获取数据库 session（FastAPI 依赖注入）。"""
    async with async_session_factory() as session:
        yield session  # type: ignore[misc]
