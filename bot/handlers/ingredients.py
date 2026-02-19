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
from core.services.recipe_match_service import find_best_recipe_match
from core.services.safety_service import build_block_message, check_user_input
from db.repo import RecipeRepository
from db.session import SessionFactory
from schemas import RecipeResponse

logger = structlog.get_logger(__name__)
router = Router()
RECENT_USER_RECIPES_LIMIT = 150
RECENT_GLOBAL_RECIPES_LIMIT = 300


def _split_ingredients(text: str) -> list[str]:
    normalized = text.replace("\n", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _gigachat_error_message(exc: Exception) -> str:
    details = str(exc)
    details_upper = details.upper()
    if "UNSAFE_RECIPE" in details_upper:
        return (
            "Не удалось безопасно сгенерировать рецепт по этому запросу. "
            "Уточните съедобные ингредиенты и попробуйте снова."
        )
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

    safety_result = check_user_input(ingredients)
    if not safety_result.is_safe:
        logger.warning(
            "recipe_blocked_by_safety",
            mode="ingredients",
            category=safety_result.category,
            matched_terms=list(safety_result.matched_terms),
        )
        await message.answer(build_block_message(safety_result))
        await state.set_state(UserMode.main_menu)
        return

    plate_service = PlateService()
    analysis = plate_service.analyze(ingredients)
    await message.answer(format_plate_analysis(analysis))

    user_id: int | None = None
    user_preferences_text = "нет"
    reused_payload: dict | None = None
    reused_recipe_id: int | None = None
    reused_rating = 0
    reused_similarity = 0.0
    reused_scope: str | None = None
    reused_is_favorite = False
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=message.from_user.id,
            username=message.from_user.username,
        )
        user_id = user.id
        settings = await repo.get_user_settings(user.id)
        user_preferences_text = settings.prompt_text()

        user_candidates = await repo.list_recent_recipes_with_rating_for_user(
            user_id=user.id,
            limit=RECENT_USER_RECIPES_LIMIT,
        )
        match = find_best_recipe_match(ingredients, user_candidates)
        if match is not None:
            reused_scope = "user"
        else:
            global_candidates = await repo.list_recent_recipes_with_rating_global(
                limit=RECENT_GLOBAL_RECIPES_LIMIT,
                exclude_user_id=user.id,
            )
            match = find_best_recipe_match(ingredients, global_candidates)
            if match is not None:
                reused_scope = "global"

        if match is not None:
            reused_payload = match.item.recipe.llm_response or {}
            reused_recipe_id = match.item.recipe.id
            reused_rating = match.item.rating
            reused_similarity = match.similarity
            reused_is_favorite = reused_recipe_id in await repo.get_user_favorite_recipe_ids(user.id)
        await session.commit()

    if reused_payload and reused_recipe_id is not None:
        try:
            reused_recipe = RecipeResponse.model_validate(reused_payload)
        except Exception:
            logger.warning("recipe_reuse_skipped_invalid_payload", recipe_id=reused_recipe_id)
        else:
            logger.info(
                "recipe_reused",
                scope=reused_scope,
                matched_recipe_id=reused_recipe_id,
                similarity=reused_similarity,
            )
            await message.answer(
                format_recipe(reused_recipe),
                reply_markup=recipe_actions_keyboard(recipe_id=reused_recipe_id, is_favorite=reused_is_favorite),
            )
            await message.answer(
                f"Найден похожий рецепт #{reused_recipe_id} (scope: {reused_scope}, "
                f"similarity: {reused_similarity:.2f}). Новая генерация не выполнялась. "
                f"Рейтинг: {reused_rating:+d}"
            )
            await state.set_state(UserMode.main_menu)
            return

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
