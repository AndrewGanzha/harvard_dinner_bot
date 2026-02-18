from bot.handlers.browse import router as browse_router
from bot.handlers.ingredients import router as ingredients_router
from bot.handlers.menu import router as menu_router
from bot.handlers.start import router as start_router

__all__ = ["browse_router", "ingredients_router", "menu_router", "start_router"]
