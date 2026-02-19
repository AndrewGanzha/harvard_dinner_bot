from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from bot.handlers import ingredients as ingredients_handler
from bot.states import UserMode
from db.models import Recipe
from db.repo import RecipeWithRating
from schemas import RecipeResponse


def _valid_recipe_payload() -> dict:
    return {
        "title": "Боул с курицей",
        "ingredients": [
            "Куриная грудка 250 г",
            "Рис бурый 120 г",
            "Брокколи 200 г",
            "Оливковое масло 1 ст.л.",
        ],
        "steps": [
            "Подготовьте продукты: промойте рис и разделите брокколи на соцветия.",
            "Варите рис 25 минут на слабом огне до мягкости, затем дайте постоять 5 минут.",
            "Обжарьте курицу на среднем огне 8-10 минут до внутренней температуры 74C.",
            "Бланшируйте брокколи 3 минуты и сразу охладите для сохранения текстуры.",
            "Соберите боул, добавьте масло и подавайте сразу теплым.",
        ],
        "time_minutes": 35,
        "servings": 2,
        "plate_map": {
            "veggies_fruits": ["брокколи"],
            "whole_grains": ["рис бурый"],
            "proteins": ["куриная грудка"],
            "fats": ["оливковое масло"],
            "dairy(optional)": [],
            "others": [],
        },
        "nutrition": None,
        "tips": ["Можно добавить лимонный сок перед подачей."],
    }


class _FakeSession:
    async def commit(self) -> None:
        return None


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.session = _FakeSession()

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeState:
    def __init__(self) -> None:
        self.states: list = []

    async def set_state(self, value) -> None:
        self.states.append(value)


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=111, username="tester")
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


def _candidate_item(recipe_id: int = 42) -> RecipeWithRating:
    payload = _valid_recipe_payload()
    recipe = Recipe(
        id=recipe_id,
        user_id=1,
        request_type="ingredients",
        title=payload["title"],
        time_minutes=payload["time_minutes"],
        servings=payload["servings"],
        source_ingredients=["курица", "рис", "брокколи"],
        supplemented_ingredients=[],
        plate_map=payload["plate_map"],
        llm_response=payload,
        created_at=datetime.now(timezone.utc),
    )
    return RecipeWithRating(recipe=recipe, rating=5)


class IngredientsHandlerFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsafe_input_is_blocked_before_llm(self) -> None:
        message = _FakeMessage("картофель, человечина")
        state = _FakeState()

        class _FailingClient:
            async def generate_recipe_from_ingredients(self, *args, **kwargs):
                raise AssertionError("LLM should not be called for unsafe input")

        with patch.object(ingredients_handler, "GigaChatClient", _FailingClient):
            await ingredients_handler.ingredients_input_handler(message, state)

        self.assertTrue(any("запрещенные" in text.lower() for text, _ in message.answers))
        self.assertIn(UserMode.main_menu, state.states)

    async def test_reuses_existing_recipe_without_llm(self) -> None:
        message = _FakeMessage("курица, рис, брокколи")
        state = _FakeState()
        candidate = _candidate_item()

        class _Repo:
            def __init__(self, session) -> None:
                self.session = session

            async def ensure_user(self, tg_user_id: int, username: str | None = None):
                return SimpleNamespace(id=1)

            async def get_user_settings(self, user_id: int):
                return SimpleNamespace(prompt_text=lambda: "нет")

            async def list_recent_recipes_with_rating_for_user(self, user_id: int, limit: int):
                return [candidate]

            async def list_recent_recipes_with_rating_global(self, limit: int, exclude_user_id: int | None = None):
                return []

            async def get_user_favorite_recipe_ids(self, user_id: int):
                return set()

            async def save_recipe(self, **kwargs):
                raise AssertionError("save_recipe must not be called when recipe is reused")

        class _FailingClient:
            async def generate_recipe_from_ingredients(self, *args, **kwargs):
                raise AssertionError("LLM should not be called when recipe is reused")

        with (
            patch.object(ingredients_handler, "SessionFactory", _FakeSessionFactory()),
            patch.object(ingredients_handler, "RecipeRepository", _Repo),
            patch.object(ingredients_handler, "GigaChatClient", _FailingClient),
        ):
            await ingredients_handler.ingredients_input_handler(message, state)

        self.assertTrue(any("найден похожий рецепт" in text.lower() for text, _ in message.answers))
        self.assertIn(UserMode.main_menu, state.states)

    async def test_calls_llm_and_saves_when_no_match(self) -> None:
        message = _FakeMessage("курица, рис, брокколи")
        state = _FakeState()
        payload = _valid_recipe_payload()
        generated = RecipeResponse.model_validate(payload)
        calls = {"llm": 0, "save": 0}

        class _Repo:
            def __init__(self, session) -> None:
                self.session = session

            async def ensure_user(self, tg_user_id: int, username: str | None = None):
                return SimpleNamespace(id=1)

            async def get_user_settings(self, user_id: int):
                return SimpleNamespace(prompt_text=lambda: "нет")

            async def list_recent_recipes_with_rating_for_user(self, user_id: int, limit: int):
                return []

            async def list_recent_recipes_with_rating_global(self, limit: int, exclude_user_id: int | None = None):
                return []

            async def get_user_favorite_recipe_ids(self, user_id: int):
                return set()

            async def save_recipe(self, **kwargs):
                calls["save"] += 1
                recipe = Recipe(
                    id=77,
                    user_id=1,
                    request_type="ingredients",
                    title=payload["title"],
                    time_minutes=payload["time_minutes"],
                    servings=payload["servings"],
                    source_ingredients=kwargs["source_ingredients"],
                    supplemented_ingredients=[],
                    plate_map=payload["plate_map"],
                    llm_response=payload,
                    created_at=datetime.now(timezone.utc),
                )
                return recipe

            async def get_rating(self, recipe_id: int):
                return 0

        class _Client:
            async def generate_recipe_from_ingredients(self, *args, **kwargs):
                calls["llm"] += 1
                return generated

        with (
            patch.object(ingredients_handler, "SessionFactory", _FakeSessionFactory()),
            patch.object(ingredients_handler, "RecipeRepository", _Repo),
            patch.object(ingredients_handler, "GigaChatClient", _Client),
        ):
            await ingredients_handler.ingredients_input_handler(message, state)

        self.assertEqual(calls["llm"], 1)
        self.assertEqual(calls["save"], 1)
        self.assertTrue(any("сохранен" in text.lower() for text, _ in message.answers))
        self.assertIn(UserMode.main_menu, state.states)


if __name__ == "__main__":
    unittest.main()

