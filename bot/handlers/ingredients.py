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

logger = structlog.get_logger(__name__)
router = Router()


def _split_ingredients(text: str) -> list[str]:
    normalized = text.replace("\n", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _gigachat_error_message(exc: Exception) -> str:
    details = str(exc)
    details_upper = details.upper()
    if "SSL" in details_upper or "TLS" in details_upper or "CERT" in details_upper:
        return (
            "Не удалось установить защищенное соединение с GigaChat. "
            "Проверьте сертификаты (Минцифры) или установите GIGACHAT_SSL_VERIFY=false."
        )
    if "HTTP 401" in details_upper:
        return "Ошибка авторизации GigaChat (401). Проверьте Basic-ключ в GIGACHAT_AUTH_KEY."
    if "HTTP 403" in details_upper:
        return "Доступ к GigaChat отклонен (403). Проверьте права ключа и scope."
    if "HTTP 400" in details_upper:
        return "Некорректный запрос к GigaChat (400). Проверьте модель и параметры запроса."
    return "Не удалось получить рецепт от GigaChat. Проверьте токен и попробуйте еще раз."


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

    try:
        recipe = await GigaChatClient().generate_recipe_from_ingredients(
            ingredients=ingredients,
            missing_groups=analysis.missing_groups,
            user_preferences=user_preferences_text,
        )
    except GigaChatError as exc:
        logger.warning("recipe_generation_failed", mode="ingredients", error=str(exc))
        await message.answer(_gigachat_error_message(exc))
        await state.set_state(UserMode.main_menu)
        return
    except Exception as exc:
        logger.exception("recipe_generation_failed_unexpected", mode="ingredients", error=str(exc))
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
            request_type="ingredients",
            source_ingredients=ingredients,
            supplemented_ingredients=analysis.recommendations,
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