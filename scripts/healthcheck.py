from __future__ import annotations

import asyncio

from sqlalchemy import text

from db.session import engine


async def main() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


if __name__ == "__main__":
    asyncio.run(main())
