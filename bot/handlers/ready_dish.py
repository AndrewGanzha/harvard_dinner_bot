from __future__ import annotations

import re

import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.formatters import format_recipe
from bot.keyboards.browse import recipe_actions_keyboard
from bot.states import UserMode
from core.services.gigachat_service import GigaChatClient, GigaChatError
from db.repo import RecipeRepository
from db.session import SessionFactory

logger = structlog.get_logger(__name__)
router = Router()


def _extract_source_ingredients(request_text: str) -> list[str]:
    normalized = request_text.replace("\n", ",").replace(";", ",")
    items = [item.strip() for item in normalized.split(",") if item.strip()]
    if len(items) > 1:
        return items[:8]

    tokens = re.findall(r"[a-zа-я0-9]+", request_text.lower())
    return tokens[:6]


@router.message(UserMode.choosing_ready_dish, F.text)
async def ready_dish_input_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    dish_request = (message.text or "").strip()
    if not dish_request:
        await message.answer("Опишите, какое блюдо хотите: например, 'быстрый вегетарианский ужин'.")
        return

    user_id: int | None = None
    user_preferences_text = "нет"
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=message.from_user.id,
            username=message.from_user.username,
        )
        user_id = user.id
        settings = await repo.get_user_settings(user.id)
        user_preferences_text = settings.prompt_text()
        await session.commit()

    source_ingredients = _extract_source_ingredients(dish_request)
    try:
        recipe = await GigaChatClient().generate_ready_dish(
            dish_request=dish_request,
            user_preferences=user_preferences_text,
        )
        if not source_ingredients:
            source_ingredients = recipe.ingredients[:6]
    except GigaChatError as exc:
        logger.warning("recipe_generation_failed", mode="ready_dish", error=str(exc))
        await message.answer("Не удалось получить рецепт от GigaChat. Проверьте токен и попробуйте еще раз.")
        await state.set_state(UserMode.main_menu)
        return
    except Exception as exc:
        logger.exception("recipe_generation_failed_unexpected", mode="ready_dish", error=str(exc))
        await message.answer("Произошла ошибка при генерации рецепта. Попробуйте повторить запрос.")
        await state.set_state(UserMode.main_menu)
        return

    recipe_id: int | None = None
    is_favorite = False
    rating = 0
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        if user_id is None:
            user = await repo.ensure_user(
                tg_user_id=message.from_user.id,
                username=message.from_user.username,
            )
            user_id = user.id

        saved = await repo.save_recipe(
            user_id=user_id,
            request_type="random",
            source_ingredients=source_ingredients,
            supplemented_ingredients=[],
            llm_response=recipe.model_dump(by_alias=True),
        )
        recipe_id = saved.id
        rating = await repo.get_rating(saved.id)
        is_favorite = saved.id in await repo.get_user_favorite_recipe_ids(user_id)
        await session.commit()

    await message.answer(
        format_recipe(recipe),
        reply_markup=recipe_actions_keyboard(recipe_id=recipe_id, is_favorite=is_favorite),
    )
    await message.answer(f"Рецепт #{recipe_id} сохранен. Источник: llm. Рейтинг: {rating:+d}")
    await state.set_state(UserMode.main_menu)