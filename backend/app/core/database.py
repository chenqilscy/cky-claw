"""数据库连接管理。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """
        在 from __future__ import annotations 模式下，
        SQLAlchemy 需要在类命名空间中 eval() 解析 Mapped 注解。
        将常用类型注入子类 __dict__，确保 eval('datetime | None') 等能找到。
        必须在 super().__init_subclass__() 之前注入，因为 SQLAlchemy 在其中解析注解。
        """
        # 注入常用类型到类命名空间，供 SQLAlchemy de-stringify 使用
        for _name, _val in (
            ("datetime", datetime),
            ("uuid", uuid),
        ):
            if _name not in cls.__dict__:
                setattr(cls, _name, _val)
        super().__init_subclass__(**kwargs)


class SoftDeleteMixin:
    """软删除 Mixin，提供 is_deleted 和 deleted_at 字段。"""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库 session（FastAPI 依赖注入）。"""
    async with async_session_factory() as session:
        yield session
