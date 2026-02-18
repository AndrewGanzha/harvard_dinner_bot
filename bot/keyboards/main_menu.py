from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MENU_ITEMS = (
    ("🥗 Ввести ингредиенты", "menu:ingredients"),
    ("🍽 Готовое блюдо", "menu:ready_dish"),
    ("🔥 Топ", "menu:top"),
    ("⭐ Избранное", "menu:favorites"),
    ("⚙️ Настройки", "menu:settings"),
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🥗 Ввести ингредиенты"), KeyboardButton(text="🍽 Готовое блюдо")],
            [KeyboardButton(text="🔥 Топ"), KeyboardButton(text="⭐ Избранное")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def main_menu_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=callback_data)]
            for text, callback_data in MENU_ITEMS
        ]
    )
