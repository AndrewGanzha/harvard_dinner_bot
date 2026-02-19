from __future__ import annotations

import re
from dataclasses import dataclass

from db.repo import RecipeWithRating


@dataclass(slots=True, frozen=True)
class RecipeMatch:
    item: RecipeWithRating
    similarity: float
    match_type: str


def _normalize_ingredient(value: str) -> str:
    normalized = value.lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _canonical_set(values: list[str]) -> set[str]:
    return {item for raw in values if raw and (item := _normalize_ingredient(raw))}


def _ingredients_from_recipe(item: RecipeWithRating) -> list[str]:
    source = list(item.recipe.source_ingredients or [])
    if source:
        return source
    payload = item.recipe.llm_response or {}
    raw = payload.get("ingredients")
    if isinstance(raw, list):
        return [str(value) for value in raw if str(value).strip()]
    return []


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def find_best_recipe_match(
    source_ingredients: list[str],
    candidates: list[RecipeWithRating],
    *,
    min_jaccard: float = 0.8,
    min_intersection: int = 3,
) -> RecipeMatch | None:
    source_set = _canonical_set(source_ingredients)
    if not source_set:
        return None

    exact_matches: list[RecipeMatch] = []
    similar_matches: list[RecipeMatch] = []

    for candidate in candidates:
        candidate_set = _canonical_set(_ingredients_from_recipe(candidate))
        if not candidate_set:
            continue

        if candidate_set == source_set:
            exact_matches.append(RecipeMatch(item=candidate, similarity=1.0, match_type="exact"))
            continue

        intersection_size = len(source_set & candidate_set)
        jaccard = _jaccard(source_set, candidate_set)
        if jaccard >= min_jaccard and intersection_size >= min_intersection:
            similar_matches.append(RecipeMatch(item=candidate, similarity=jaccard, match_type="similar"))

    ranked = exact_matches or similar_matches
    if not ranked:
        return None

    ranked.sort(
        key=lambda match: (
            match.similarity,
            match.item.rating,
            match.item.recipe.created_at,
        ),
        reverse=True,
    )
    return ranked[0]

