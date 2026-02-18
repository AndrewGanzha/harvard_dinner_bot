import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import browse_router, ingredients_router, menu_router, settings_router, start_router
from bot.middlewares.logging import UpdateLoggingMiddleware
from core.config import settings
from core.logging import configure_logging
from db.session import init_models

logger = structlog.get_logger(__name__)


async def main() -> None:
    configure_logging(settings.log_level)
    logger.info("bot_starting")
    await init_models()

    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(UpdateLoggingMiddleware())
    dp.include_router(start_router)
    dp.include_router(ingredients_router)
    dp.include_router(browse_router)
    dp.include_router(settings_router)
    dp.include_router(menu_router)

    bot = Bot(token=settings.tg_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
