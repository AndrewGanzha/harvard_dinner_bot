from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SafetyResult:
    is_safe: bool
    category: str | None = None
    matched_terms: tuple[str, ...] = ()


_PROHIBITED_TERMS: dict[str, tuple[str, ...]] = {
    "cannibalism_human_tissue": (
        "человечина",
        "человеческое мясо",
        "мясо человека",
        "человеческая кровь",
        "каннибал",
        "каннибализм",
        "людоед",
        "human meat",
        "human flesh",
        "cannibal",
    ),
    "dangerous_non_food": (
        "ртуть",
        "мышьяк",
        "цианид",
        "антифриз",
        "бензин",
        "керосин",
        "ацетон",
        "отбеливатель",
        "хлорка",
        "пластик",
        "стекло",
        "battery acid",
        "bleach",
        "gasoline",
        "mercury",
        "arsenic",
        "cyanide",
    ),
    "illegal_drugs": (
        "кокаин",
        "героин",
        "метамфетамин",
        "амфетамин",
        "лсд",
        "мдма",
        "спайс",
        "наркотик",
        "cocaine",
        "heroin",
        "methamphetamine",
        "amphetamine",
        "lsd",
        "mdma",
    ),
}

_CATEGORY_LABELS: dict[str, str] = {
    "cannibalism_human_tissue": "человеческие ткани / каннибализм",
    "dangerous_non_food": "опасные или несъедобные вещества",
    "illegal_drugs": "нелегальные или наркотические вещества",
}

_SAFE_ALTERNATIVES: dict[str, tuple[str, ...]] = {
    "cannibalism_human_tissue": ("куриная грудка", "тофу", "нут", "шампиньоны"),
    "dangerous_non_food": ("цветная капуста", "нут", "гречка", "оливковое масло"),
    "illegal_drugs": ("какао", "ваниль", "мята", "лимонная цедра"),
}


def normalize_text(value: str) -> str:
    normalized = value.lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _collect_matches(text: str) -> tuple[str | None, tuple[str, ...]]:
    if not text:
        return None, ()

    matches: list[str] = []
    for category, terms in _PROHIBITED_TERMS.items():
        category_matches = [term for term in terms if normalize_text(term) in text]
        if category_matches:
            matches.extend(category_matches)
            deduped = tuple(dict.fromkeys(matches))
            return category, deduped
    return None, ()


def check_user_input(items: list[str] | str) -> SafetyResult:
    if isinstance(items, str):
        values = [items]
    else:
        values = items
    joined = " ".join(value for value in values if value).strip()
    category, terms = _collect_matches(normalize_text(joined))
    if category is None:
        return SafetyResult(is_safe=True)
    return SafetyResult(is_safe=False, category=category, matched_terms=terms)


def check_recipe_output(recipe_title: str, ingredients: list[str], steps: list[str]) -> SafetyResult:
    text = " ".join([recipe_title, *ingredients, *steps]).strip()
    category, terms = _collect_matches(normalize_text(text))
    if category is None:
        return SafetyResult(is_safe=True)
    return SafetyResult(is_safe=False, category=category, matched_terms=terms)


def build_block_message(result: SafetyResult) -> str:
    if result.is_safe:
        return "Запрос безопасен."

    category = result.category or "unknown"
    category_label = _CATEGORY_LABELS.get(category, "небезопасные ингредиенты")
    alternatives = ", ".join(_SAFE_ALTERNATIVES.get(category, ("куриная грудка", "тофу", "овощи")))
    matched = ", ".join(result.matched_terms) if result.matched_terms else "не указано"

    return (
        "Не могу помочь с этим запросом, потому что в нем есть запрещенные или опасные ингредиенты.\n"
        f"Категория: {category_label}.\n"
        f"Что обнаружено: {matched}.\n"
        f"Попробуйте безопасные альтернативы: {alternatives}."
    )

