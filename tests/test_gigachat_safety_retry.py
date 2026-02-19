from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.services.gigachat_service import GigaChatClient, GigaChatError


def _unsafe_payload_json() -> str:
    payload = {
        "title": "Паста",
        "ingredients": [
            "Спагетти 200 г",
            "Соус 150 мл",
            "Человечина 100 г",
            "Масло 1 ст.л.",
        ],
        "steps": [
            "Подготовьте продукты и вскипятите воду.",
            "Сварите спагетти 8-10 минут до состояния al dente.",
            "Разогрейте соус и добавьте ингредиенты, постоянно помешивая.",
            "Протомите смесь 5 минут на слабом огне до равномерной текстуры.",
            "Смешайте пасту с соусом и подавайте горячей.",
        ],
        "time_minutes": 25,
        "servings": 2,
        "plate_map": {
            "veggies_fruits": [],
            "whole_grains": ["спагетти"],
            "proteins": ["человечина"],
            "fats": ["масло"],
            "dairy(optional)": [],
            "others": [],
        },
        "nutrition": None,
        "tips": [],
    }
    return json.dumps(payload, ensure_ascii=False)


class _FakeUnsafeGigaChat:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def chat(self, request_payload):
        content = _unsafe_payload_json()
        return {"choices": [{"message": {"content": content}}]}


class GigaChatSafetyRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsafe_recipe_triggers_retries_and_final_error(self) -> None:
        client = GigaChatClient(auth_key="test", max_retries=2, timeout_seconds=1.0)
        with patch("core.services.gigachat_service.GigaChat", _FakeUnsafeGigaChat):
            with self.assertRaises(GigaChatError) as ctx:
                await client._request_recipe(
                    messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}],
                    scenario="ingredients",
                )
        self.assertIn("UNSAFE_RECIPE", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
