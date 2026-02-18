from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from db.models import Base

engine = create_async_engine(settings.database_dsn, echo=False)
SessionFactory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with SessionFactory() as session:
        yield session


async def init_models() -> None:
    if not settings.db_auto_create:
        return

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
