from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.services.recipe_match_service import find_best_recipe_match
from db.models import Recipe
from db.repo import RecipeWithRating


def _item(
    recipe_id: int,
    *,
    source_ingredients: list[str],
    rating: int,
    created_at: datetime,
) -> RecipeWithRating:
    recipe = Recipe(
        id=recipe_id,
        user_id=1,
        request_type="ingredients",
        title=f"Recipe {recipe_id}",
        time_minutes=20,
        servings=2,
        source_ingredients=source_ingredients,
        supplemented_ingredients=[],
        plate_map={},
        llm_response={"ingredients": source_ingredients},
        created_at=created_at,
    )
    return RecipeWithRating(recipe=recipe, rating=rating)


class RecipeMatchServiceTests(unittest.TestCase):
    def test_exact_match_ignores_order_and_case(self) -> None:
        now = datetime.now(timezone.utc)
        candidates = [
            _item(1, source_ingredients=["рис", "брокколи", "курица"], rating=3, created_at=now),
        ]
        result = find_best_recipe_match(["Курица", "Рис", "Брокколи"], candidates)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.match_type, "exact")
        self.assertEqual(result.similarity, 1.0)
        self.assertEqual(result.item.recipe.id, 1)

    def test_similar_match_uses_jaccard_threshold(self) -> None:
        now = datetime.now(timezone.utc)
        candidates = [
            _item(
                2,
                source_ingredients=["курица", "рис", "брокколи", "помидор", "масло"],
                rating=1,
                created_at=now,
            ),
        ]
        result = find_best_recipe_match(["курица", "рис", "брокколи", "помидор"], candidates)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.match_type, "similar")
        self.assertGreaterEqual(result.similarity, 0.8)

    def test_ranking_prefers_rating_then_recency(self) -> None:
        now = datetime.now(timezone.utc)
        candidates = [
            _item(
                10,
                source_ingredients=["курица", "рис", "брокколи"],
                rating=5,
                created_at=now - timedelta(hours=2),
            ),
            _item(
                11,
                source_ingredients=["курица", "рис", "брокколи"],
                rating=7,
                created_at=now - timedelta(days=1),
            ),
            _item(
                12,
                source_ingredients=["курица", "рис", "брокколи"],
                rating=7,
                created_at=now,
            ),
        ]
        result = find_best_recipe_match(["рис", "курица", "брокколи"], candidates)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.item.recipe.id, 12)


if __name__ == "__main__":
    unittest.main()

