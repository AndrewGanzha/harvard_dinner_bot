from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MENU_INGREDIENTS = "🥗 Ввести ингредиенты"
MENU_READY_DISH = "🍽 Готовое блюдо"
MENU_TOP = "🔥 Топ"
MENU_FAVORITES = "⭐ Избранное"
MENU_HISTORY = "🕘 История"
MENU_SETTINGS = "⚙️ Настройки"

MENU_ITEMS = (
    (MENU_INGREDIENTS, "menu:ingredients"),
    (MENU_READY_DISH, "menu:ready_dish"),
    (MENU_TOP, "menu:top"),
    (MENU_FAVORITES, "menu:favorites"),
    (MENU_HISTORY, "menu:history"),
    (MENU_SETTINGS, "menu:settings"),
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_INGREDIENTS), KeyboardButton(text=MENU_READY_DISH)],
            [KeyboardButton(text=MENU_TOP), KeyboardButton(text=MENU_FAVORITES)],
            [KeyboardButton(text=MENU_HISTORY), KeyboardButton(text=MENU_SETTINGS)],
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
