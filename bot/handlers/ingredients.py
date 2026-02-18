from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.formatters import format_plate_analysis, format_recipe
from bot.keyboards.browse import recipe_actions_keyboard
from bot.states import UserMode
from core.services.gigachat_service import GigaChatClient, GigaChatError
from core.services.plate_service import PlateService
from db.repo import RecipeRepository
from db.session import SessionFactory
from schemas import RecipeResponse

logger = structlog.get_logger(__name__)
router = Router()


def _split_ingredients(text: str) -> list[str]:
    normalized = text.replace("\n", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _fallback_recipe(ingredients: list[str], recommendations: list[str]) -> RecipeResponse:
    final_ingredients = ingredients + [item for item in recommendations if item not in ingredients]
    payload = {
        "title": "Сбалансированная тарелка",
        "ingredients": final_ingredients,
        "steps": [
            "Подготовьте и нарежьте все ингредиенты.",
            "Соберите тарелку: половина овощей, четверть белка, четверть цельных злаков.",
            "Добавьте полезные жиры и подавайте.",
        ],
        "time_minutes": 20,
        "servings": 1,
        "plate_map": {
            "veggies_fruits": [item for item in final_ingredients if "салат" in item.lower() or "овощ" in item.lower()],
            "whole_grains": [],
            "proteins": [],
            "fats": [],
            "dairy(optional)": [],
            "others": final_ingredients,
        },
        "nutrition": None,
        "tips": ["При возможности добавьте больше овощей для половины тарелки."],
    }
    return RecipeResponse.model_validate(payload)


@router.message(UserMode.entering_ingredients, F.text)
async def ingredients_input_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    ingredients = _split_ingredients(message.text or "")
    if not ingredients:
        await message.answer("Не вижу ингредиентов. Отправьте список через запятую или с новой строки.")
        return

    plate_service = PlateService()
    analysis = plate_service.analyze(ingredients)
    await message.answer(format_plate_analysis(analysis))

    recipe_source = "llm"
    try:
        recipe = await GigaChatClient().generate_recipe(
            ingredients=ingredients,
            missing_groups=analysis.missing_groups,
        )
    except (GigaChatError, Exception) as exc:
        recipe_source = "fallback"
        logger.warning("recipe_generation_fallback", error=str(exc))
        recipe = _fallback_recipe(ingredients, analysis.recommendations)

    recipe_id: int | None = None
    is_favorite = False
    rating = 0
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=message.from_user.id,
            username=message.from_user.username,
        )
        saved = await repo.save_recipe(
            user_id=user.id,
            request_type="ingredients",
            source_ingredients=ingredients,
            supplemented_ingredients=analysis.recommendations,
            llm_response=recipe.model_dump(by_alias=True),
        )
        recipe_id = saved.id
        rating = await repo.get_rating(saved.id)
        is_favorite = saved.id in await repo.get_user_favorite_recipe_ids(user.id)
        await session.commit()

    await message.answer(
        format_recipe(recipe),
        reply_markup=recipe_actions_keyboard(recipe_id=recipe_id, is_favorite=is_favorite),
    )
    await message.answer(f"Рецепт #{recipe_id} сохранен. Источник: {recipe_source}. Рейтинг: {rating:+d}")
    await state.set_state(UserMode.main_menu)
