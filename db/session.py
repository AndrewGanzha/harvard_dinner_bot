from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from db.models import Base

engine = create_async_engine(settings.db_dsn, echo=False)
SessionFactory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with SessionFactory() as session:
        yield session


async def init_models() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        if connection.dialect.name == "sqlite":
            result = await connection.execute(text("PRAGMA table_info(users)"))
            existing_columns = {row[1] for row in result.fetchall()}
            pending_columns = {
                "goal": "goal VARCHAR(32)",
                "allergies": "allergies JSON",
                "excluded_products": "excluded_products JSON",
                "preferred_cuisine": "preferred_cuisine VARCHAR(64)",
                "preferred_complexity": "preferred_complexity VARCHAR(32)",
                "time_limit_minutes": "time_limit_minutes INTEGER",
            }
            for column_name, ddl in pending_columns.items():
                if column_name not in existing_columns:
                    await connection.execute(text(f"ALTER TABLE users ADD COLUMN {ddl}"))
