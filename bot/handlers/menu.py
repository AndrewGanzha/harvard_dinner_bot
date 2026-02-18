from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

from bot.states import UserMode

router = Router()

MENU_TRANSITIONS: dict[str, tuple[State, str, str]] = {
    "🥗 Ввести ингредиенты": (
        UserMode.entering_ingredients,
        "menu:ingredients",
        "Режим ввода ингредиентов активирован. Отправьте список продуктов текстом.",
    ),
    "🍽 Готовое блюдо": (
        UserMode.choosing_ready_dish,
        "menu:ready_dish",
        "Режим готовых блюд активирован. Скоро добавим фильтры выбора.",
    ),
    "🔥 Топ": (
        UserMode.viewing_top,
        "menu:top",
        "Режим просмотра топа активирован. Скоро покажу рейтинг рецептов.",
    ),
    "⭐ Избранное": (
        UserMode.viewing_favorites,
        "menu:favorites",
        "Режим избранного активирован. Скоро покажу сохраненные рецепты.",
    ),
    "⚙️ Настройки": (
        UserMode.editing_settings,
        "menu:settings",
        "Режим настроек активирован. Скоро добавим персонализацию.",
    ),
}

CALLBACK_TO_TEXT = {callback: text for text, (_, callback, _) in MENU_TRANSITIONS.items()}


async def _activate_mode(state: FSMContext, mode: State, reply: str, target: Message) -> None:
    await state.set_state(mode)
    await target.answer(reply)


@router.message(F.text.in_(MENU_TRANSITIONS.keys()))
async def menu_message_handler(message: Message, state: FSMContext) -> None:
    mode, _, reply = MENU_TRANSITIONS[message.text]
    await _activate_mode(state, mode, reply, message)


@router.callback_query(F.data.in_(CALLBACK_TO_TEXT.keys()))
async def menu_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    text = CALLBACK_TO_TEXT[callback.data]
    mode, _, reply = MENU_TRANSITIONS[text]
    await state.set_state(mode)
    if callback.message:
        await callback.message.answer(reply)
    await callback.answer("Режим переключен")
