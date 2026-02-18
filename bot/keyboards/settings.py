from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

GOAL_LABELS = {
    "lose": "Похудение",
    "maintain": "Поддержание",
    "gain": "Набор",
}


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Похудение", callback_data="S:goal:lose"),
                InlineKeyboardButton(text="⚖️ Поддержание", callback_data="S:goal:maintain"),
            ],
            [InlineKeyboardButton(text="💪 Набор", callback_data="S:goal:gain")],
            [
                InlineKeyboardButton(text="🧹 Очистить аллергии", callback_data="S:clear:allergies"),
                InlineKeyboardButton(text="🧹 Очистить исключения", callback_data="S:clear:excluded"),
            ],
            [InlineKeyboardButton(text="🧾 Показать настройки", callback_data="S:show")],
        ]
    )
