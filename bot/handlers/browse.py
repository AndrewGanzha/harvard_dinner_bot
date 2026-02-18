from __future__ import annotations

from math import ceil
from typing import Literal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message

from bot.formatters import SCOPE_TITLE, format_recipe, format_recipe_card
from bot.keyboards.browse import BrowseContext, browse_keyboard, parse_context, recipe_actions_keyboard
from bot.keyboards.main_menu import MENU_FAVORITES, MENU_HISTORY, MENU_TOP
from bot.states import UserMode
from db.repo import RecipeRepository, RecipeWithRating
from db.session import SessionFactory
from schemas import RecipeResponse

router = Router()
PAGE_SIZE = 5

SCOPE_BY_CALLBACK = {
    "menu:top": "top",
    "menu:favorites": "favorites",
    "menu:history": "history",
}
SCOPE_STATE = {
    "top": UserMode.viewing_top,
    "favorites": UserMode.viewing_favorites,
    "history": UserMode.viewing_history,
}
ANIMAL_KEYWORDS = (
    "кур",
    "индей",
    "говя",
    "свин",
    "бекон",
    "рыб",
    "лосос",
    "тунец",
    "кревет",
    "краб",
    "мяс",
)


def _is_vegetarian(item: RecipeWithRating) -> bool:
    payload = item.recipe.llm_response or {}
    ingredients = payload.get("ingredients") or item.recipe.source_ingredients or []
    normalized = " ".join(str(x).lower() for x in ingredients)
    return not any(keyword in normalized for keyword in ANIMAL_KEYWORDS)


def _apply_filters(
    items: list[RecipeWithRating],
    context: BrowseContext,
    viewer_user_id: int,
    liked_recipe_ids: set[int],
) -> list[RecipeWithRating]:
    filtered: list[RecipeWithRating] = []
    for item in items:
        recipe = item.recipe
        if context.only_my and recipe.user_id != viewer_user_id:
            continue
        if context.only_liked and recipe.id not in liked_recipe_ids:
            continue
        if context.fast and (recipe.time_minutes is None or recipe.time_minutes > 20):
            continue
        if context.vegetarian and not _is_vegetarian(item):
            continue
        filtered.append(item)
    return filtered


def _paginate(items: list[RecipeWithRating], page: int) -> tuple[list[RecipeWithRating], int, int]:
    total_pages = max(1, ceil(len(items) / PAGE_SIZE))
    safe_page = min(max(page, 1), total_pages)
    offset = (safe_page - 1) * PAGE_SIZE
    return items[offset : offset + PAGE_SIZE], safe_page, total_pages


def _active_filters(context: BrowseContext) -> str:
    flags: list[str] = []
    if context.only_my:
        flags.append("мои")
    if context.only_liked:
        flags.append("лайкнутые")
    if context.fast:
        flags.append("до 20 мин")
    if context.vegetarian:
        flags.append("вегетарианские")
    return ", ".join(flags) if flags else "нет"


async def _render_scope(
    *,
    scope: str,
    context: BrowseContext,
    user_id: int,
    username: str | None,
    target_message: Message,
    edit: bool,
) -> None:
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(tg_user_id=user_id, username=username)
        items = await repo.list_recipes_with_rating(scope=scope, viewer_user_id=user.id)
        liked_recipe_ids = await repo.get_user_liked_recipe_ids(user.id)
        filtered = _apply_filters(items=items, context=context, viewer_user_id=user.id, liked_recipe_ids=liked_recipe_ids)
        page_items, safe_page, total_pages = _paginate(filtered, context.page)
        await session.commit()

    safe_context = context.with_page(safe_page)
    rows = [
        (item.recipe.id, item.recipe.title or f"Рецепт #{item.recipe.id}", item.rating)
        for item in page_items
    ]
    list_title = SCOPE_TITLE.get(scope, "Рецепты")
    text = (
        f"{list_title}\n"
        f"Фильтры: {_active_filters(safe_context)}\n"
        f"Найдено: {len(filtered)}"
    )
    if not rows:
        text += "\n\nНичего не найдено по выбранным фильтрам."
    keyboard = browse_keyboard(rows, safe_context, total_pages)

    if edit:
        await target_message.edit_text(text, reply_markup=keyboard)
    else:
        await target_message.answer(text, reply_markup=keyboard)


@router.message(Command("top"))
@router.message(F.text == MENU_TOP)
async def show_top_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.set_state(UserMode.viewing_top)
    context = BrowseContext(scope="top", page=1)
    await _render_scope(
        scope="top",
        context=context,
        user_id=message.from_user.id,
        username=message.from_user.username,
        target_message=message,
        edit=False,
    )


@router.message(Command("favorites"))
@router.message(F.text == MENU_FAVORITES)
async def show_favorites_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.set_state(UserMode.viewing_favorites)
    context = BrowseContext(scope="favorites", page=1)
    await _render_scope(
        scope="favorites",
        context=context,
        user_id=message.from_user.id,
        username=message.from_user.username,
        target_message=message,
        edit=False,
    )


@router.message(Command("history"))
@router.message(F.text == MENU_HISTORY)
async def show_history_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.set_state(UserMode.viewing_history)
    context = BrowseContext(scope="history", page=1)
    await _render_scope(
        scope="history",
        context=context,
        user_id=message.from_user.id,
        username=message.from_user.username,
        target_message=message,
        edit=False,
    )


@router.callback_query(F.data.in_(SCOPE_BY_CALLBACK.keys()))
async def scope_from_inline_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    scope = SCOPE_BY_CALLBACK[callback.data]
    await state.set_state(SCOPE_STATE[scope])
    context = BrowseContext(scope=scope, page=1)
    await _render_scope(
        scope=scope,
        context=context,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        target_message=callback.message,
        edit=True,
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("L:"))
async def list_page_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    _, scope, page, flags = callback.data.split(":")
    context = parse_context(scope, page, flags)
    await state.set_state(SCOPE_STATE.get(scope, UserMode.main_menu))
    await _render_scope(
        scope=scope,
        context=context,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        target_message=callback.message,
        edit=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("F:"))
async def toggle_filter_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    _, scope, page, flags, toggle = callback.data.split(":")
    context = parse_context(scope, page, flags).toggled(toggle)
    await state.set_state(SCOPE_STATE.get(scope, UserMode.main_menu))
    await _render_scope(
        scope=scope,
        context=context,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        target_message=callback.message,
        edit=True,
    )
    await callback.answer("Фильтр обновлен")


@router.callback_query(F.data.startswith("O:"))
async def open_recipe_from_list_handler(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    _, recipe_id_text, scope, page, flags = callback.data.split(":")
    recipe_id = int(recipe_id_text)

    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        item = await repo.get_recipe_with_rating(recipe_id)
        if item is None:
            await callback.answer("Рецепт не найден", show_alert=True)
            return
        favorite_ids = await repo.get_user_favorite_recipe_ids(user.id)
        is_favorite = recipe_id in favorite_ids
        await session.commit()

    payload = item.recipe.llm_response or {}
    details = format_recipe_card(
        title=item.recipe.title,
        time_minutes=item.recipe.time_minutes,
        rating=item.rating,
        recipe_id=item.recipe.id,
    )
    try:
        parsed = RecipeResponse.model_validate(payload)
        details = f"{details}\n\n{format_recipe(parsed)}"
    except Exception:
        pass

    keyboard = recipe_actions_keyboard(recipe_id=recipe_id, is_favorite=is_favorite)
    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="⬅️ К списку",
                callback_data=f"L:{scope}:{page}:{flags}",
            )
        ]
    )
    await callback.message.edit_text(details[:4000], reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("V:"))
async def vote_recipe_handler(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    _, recipe_id_text, vote_text = callback.data.split(":")
    recipe_id = int(recipe_id_text)
    vote = int(vote_text)
    vote_value: Literal[-1, 1] = 1 if vote > 0 else -1

    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        await repo.set_vote(user_id=user.id, recipe_id=recipe_id, vote=vote_value)
        rating = await repo.get_rating(recipe_id)
        await session.commit()

    await callback.answer("Голос сохранен")
    if callback.message:
        await callback.message.answer(f"Рейтинг рецепта #{recipe_id}: {rating:+d}")


@router.callback_query(F.data.startswith("A:"))
async def add_favorite_handler(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    recipe_id = int(callback.data.split(":")[1])

    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        await repo.add_favorite(user_id=user.id, recipe_id=recipe_id)
        await session.commit()

    await callback.answer("Добавлено в избранное")


@router.callback_query(F.data.startswith("R:"))
async def remove_favorite_handler(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    recipe_id = int(callback.data.split(":")[1])

    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        await repo.remove_favorite(user_id=user.id, recipe_id=recipe_id)
        await session.commit()

    await callback.answer("Удалено из избранного")
