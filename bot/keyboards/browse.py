from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass(slots=True, frozen=True)
class BrowseContext:
    scope: str
    page: int = 1
    only_my: bool = False
    only_liked: bool = False
    fast: bool = False
    vegetarian: bool = False

    @property
    def flags(self) -> str:
        return "".join(
            "1" if flag else "0"
            for flag in (self.only_my, self.only_liked, self.fast, self.vegetarian)
        )

    def with_page(self, page: int) -> "BrowseContext":
        return BrowseContext(
            scope=self.scope,
            page=max(page, 1),
            only_my=self.only_my,
            only_liked=self.only_liked,
            fast=self.fast,
            vegetarian=self.vegetarian,
        )

    def toggled(self, key: str) -> "BrowseContext":
        return BrowseContext(
            scope=self.scope,
            page=1,
            only_my=not self.only_my if key == "m" else self.only_my,
            only_liked=not self.only_liked if key == "l" else self.only_liked,
            fast=not self.fast if key == "f" else self.fast,
            vegetarian=not self.vegetarian if key == "v" else self.vegetarian,
        )


def parse_context(scope: str, page: str, flags: str) -> BrowseContext:
    padded = (flags or "0000").ljust(4, "0")
    return BrowseContext(
        scope=scope,
        page=max(int(page), 1),
        only_my=padded[0] == "1",
        only_liked=padded[1] == "1",
        fast=padded[2] == "1",
        vegetarian=padded[3] == "1",
    )


def browse_keyboard(
    recipes: list[tuple[int, str, int]],
    context: BrowseContext,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for recipe_id, title, rating in recipes:
        text = f"#{recipe_id} {title[:28]} · {rating:+d}"
        callback_data = f"O:{recipe_id}:{context.scope}:{context.page}:{context.flags}"
        rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    nav_row: list[InlineKeyboardButton] = []
    if context.page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"L:{context.scope}:{context.page - 1}:{context.flags}",
            )
        )
    nav_row.append(
        InlineKeyboardButton(text=f"{context.page}/{max(total_pages, 1)}", callback_data="noop")
    )
    if context.page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"L:{context.scope}:{context.page + 1}:{context.flags}",
            )
        )
    rows.append(nav_row)

    rows.append(
        [
            InlineKeyboardButton(
                text=f"{'✅' if context.only_my else '▫️'} Мои",
                callback_data=f"F:{context.scope}:{context.page}:{context.flags}:m",
            ),
            InlineKeyboardButton(
                text=f"{'✅' if context.only_liked else '▫️'} Лайк",
                callback_data=f"F:{context.scope}:{context.page}:{context.flags}:l",
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"{'✅' if context.fast else '▫️'} До 20 мин",
                callback_data=f"F:{context.scope}:{context.page}:{context.flags}:f",
            ),
            InlineKeyboardButton(
                text=f"{'✅' if context.vegetarian else '▫️'} Вегетарианские",
                callback_data=f"F:{context.scope}:{context.page}:{context.flags}:v",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def recipe_actions_keyboard(recipe_id: int, is_favorite: bool) -> InlineKeyboardMarkup:
    favorite_text = "⭐ Убрать из избранного" if is_favorite else "⭐ В избранное"
    favorite_callback = f"R:{recipe_id}" if is_favorite else f"A:{recipe_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Лайк", callback_data=f"V:{recipe_id}:1"),
                InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"V:{recipe_id}:-1"),
            ],
            [InlineKeyboardButton(text=favorite_text, callback_data=favorite_callback)],
        ]
    )
