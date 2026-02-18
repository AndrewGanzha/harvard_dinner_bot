from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main_menu import MENU_SETTINGS
from bot.keyboards.settings import GOAL_LABELS, settings_keyboard
from bot.states import UserMode
from db.repo import RecipeRepository, UserSettings
from db.session import SessionFactory

router = Router()


def _split_list(value: str) -> list[str]:
    normalized = value.replace("\n", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip() and item.strip() != "-"]


def _parse_optional_text(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned or cleaned in {"-", "нет", "none"}:
        return None
    return cleaned


def _parse_limit(value: str) -> int | None:
    cleaned = value.strip()
    if not cleaned or cleaned in {"-", "нет", "none"}:
        return None
    if not cleaned.isdigit():
        raise ValueError("Лимит должен быть числом минут или '-'")
    return int(cleaned)


def _format_settings(settings: UserSettings) -> str:
    goal = GOAL_LABELS.get(settings.goal or "", "не выбрана")
    allergies = ", ".join(settings.allergies or []) or "нет"
    excluded = ", ".join(settings.excluded_products or []) or "нет"
    cuisine = settings.preferred_cuisine or "не указана"
    complexity = settings.preferred_complexity or "не указана"
    limit = f"{settings.time_limit_minutes} мин" if settings.time_limit_minutes else "не указан"
    return (
        "⚙️ Текущие настройки:\n"
        f"Цель: {goal}\n"
        f"Аллергии: {allergies}\n"
        f"Исключаемые продукты: {excluded}\n"
        f"Кухня: {cuisine}\n"
        f"Сложность: {complexity}\n"
        f"Лимит времени: {limit}\n\n"
        "Как изменить:\n"
        "• аллергии: арахис, молоко\n"
        "• исключить: сахар, хлеб\n"
        "• кухня: средиземноморская\n"
        "• сложность: простая\n"
        "• лимит: 25\n"
        "• предпочтения: кухня=азиатская; сложность=простая; лимит=20"
    )


async def _load_settings_text(user_id: int, username: str | None) -> tuple[int, str]:
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(tg_user_id=user_id, username=username)
        settings = await repo.get_user_settings(user.id)
        await session.commit()
        return user.id, _format_settings(settings)


@router.message(Command("settings"))
@router.message(F.text == MENU_SETTINGS)
async def show_settings_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    _, text = await _load_settings_text(
        user_id=message.from_user.id,
        username=message.from_user.username,
    )
    await state.set_state(UserMode.editing_settings)
    await message.answer(text, reply_markup=settings_keyboard())


@router.callback_query(F.data == "menu:settings")
async def show_settings_from_inline_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    _, text = await _load_settings_text(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )
    await state.set_state(UserMode.editing_settings)
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("S:"))
async def settings_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    _, action, value = (callback.data.split(":", 2) + [""])[:3]
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        if action == "goal" and value in GOAL_LABELS:
            await repo.update_user_settings(user.id, goal=value)
        elif action == "clear" and value == "allergies":
            await repo.update_user_settings(user.id, allergies=[])
        elif action == "clear" and value == "excluded":
            await repo.update_user_settings(user.id, excluded_products=[])
        settings = await repo.get_user_settings(user.id)
        await session.commit()

    await state.set_state(UserMode.editing_settings)
    await callback.message.edit_text(_format_settings(settings), reply_markup=settings_keyboard())
    await callback.answer("Настройки обновлены")


@router.message(
    UserMode.editing_settings,
    F.text.regexp(r"(?i)^(аллергии:|исключить:|кухня:|сложность:|лимит:|предпочтения:|показать$|настройки$|/settings$)"),
)
async def settings_text_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").strip()
    lowered = text.lower()
    async with SessionFactory() as session:
        repo = RecipeRepository(session)
        user = await repo.ensure_user(
            tg_user_id=message.from_user.id,
            username=message.from_user.username,
        )
        try:
            if lowered.startswith("аллергии:"):
                await repo.update_user_settings(user.id, allergies=_split_list(text.split(":", 1)[1]))
            elif lowered.startswith("исключить:"):
                await repo.update_user_settings(
                    user.id,
                    excluded_products=_split_list(text.split(":", 1)[1]),
                )
            elif lowered.startswith("кухня:"):
                await repo.update_user_settings(
                    user.id,
                    preferred_cuisine=_parse_optional_text(text.split(":", 1)[1]),
                )
            elif lowered.startswith("сложность:"):
                await repo.update_user_settings(
                    user.id,
                    preferred_complexity=_parse_optional_text(text.split(":", 1)[1]),
                )
            elif lowered.startswith("лимит:"):
                await repo.update_user_settings(
                    user.id,
                    time_limit_minutes=_parse_limit(text.split(":", 1)[1]),
                )
            elif lowered.startswith("предпочтения:"):
                payload = text.split(":", 1)[1]
                parts = [p.strip() for p in payload.split(";") if p.strip()]
                updates: dict[str, object] = {}
                for part in parts:
                    if "=" not in part:
                        continue
                    key, value = [x.strip().lower() for x in part.split("=", 1)]
                    if key == "кухня":
                        updates["preferred_cuisine"] = _parse_optional_text(value)
                    elif key == "сложность":
                        updates["preferred_complexity"] = _parse_optional_text(value)
                    elif key == "лимит":
                        updates["time_limit_minutes"] = _parse_limit(value)
                await repo.update_user_settings(user.id, **updates)
            elif lowered in {"показать", "настройки", "/settings"}:
                pass
        except ValueError as exc:
            await message.answer(str(exc))
            return

        settings = await repo.get_user_settings(user.id)
        await session.commit()

    await state.set_state(UserMode.editing_settings)
    await message.answer(_format_settings(settings), reply_markup=settings_keyboard())
