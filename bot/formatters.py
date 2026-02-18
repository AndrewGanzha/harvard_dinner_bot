from __future__ import annotations

from core.services.plate_service import PlateAnalysis
from schemas import RecipeResponse

SCOPE_TITLE = {
    "top": "🔥 Топ рецептов",
    "favorites": "⭐ Избранное",
    "history": "🕘 История",
}


def format_plate_analysis(analysis: PlateAnalysis) -> str:
    covered = ", ".join(analysis.covered_groups) if analysis.covered_groups else "нет"
    missing = ", ".join(analysis.missing_groups) if analysis.missing_groups else "нет"
    recommendations = ", ".join(analysis.recommendations) if analysis.recommendations else "нет"
    return (
        "Анализ тарелки:\n"
        f"Покрытые группы: {covered}\n"
        f"Недостающие группы: {missing}\n"
        f"Что добавить: {recommendations}"
    )


def format_recipe(recipe: RecipeResponse) -> str:
    ingredients = "\n".join(f"• {item}" for item in recipe.ingredients)
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(recipe.steps, start=1))
    tips = "\n".join(f"• {tip}" for tip in recipe.tips) if recipe.tips else "• Без советов"
    return (
        f"🍽 {recipe.title}\n\n"
        f"⏱ Время: {recipe.time_minutes} мин\n"
        f"🍴 Порции: {recipe.servings}\n\n"
        "Ингредиенты:\n"
        f"{ingredients}\n\n"
        "Шаги:\n"
        f"{steps}\n\n"
        "Советы:\n"
        f"{tips}"
    )


def format_recipe_card(title: str | None, time_minutes: int | None, rating: int, recipe_id: int) -> str:
    safe_title = title or f"Рецепт #{recipe_id}"
    time_part = f"{time_minutes} мин" if time_minutes is not None else "время не указано"
    return (
        f"#{recipe_id} {safe_title}\n"
        f"⏱ {time_part}\n"
        f"Рейтинг: {rating:+d}"
    )
