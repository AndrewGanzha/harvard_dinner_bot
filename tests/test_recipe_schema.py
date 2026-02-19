from __future__ import annotations

import unittest

from pydantic import ValidationError

from schemas import RecipeResponse


def _valid_payload() -> dict:
    return {
        "title": "Теплый боул с курицей",
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
            "Отдельно бланшируйте брокколи 3 минуты и охладите в холодной воде.",
            "Соберите боул, полейте маслом и подавайте сразу теплым.",
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
        "tips": ["Добавьте лимонный сок перед подачей."],
    }


class RecipeSchemaTests(unittest.TestCase):
    def test_rejects_too_short_ingredients(self) -> None:
        payload = _valid_payload()
        payload["ingredients"] = ["я", "в", "к", "м"]
        with self.assertRaises(ValidationError):
            RecipeResponse.model_validate(payload)

    def test_rejects_not_detailed_steps(self) -> None:
        payload = _valid_payload()
        payload["steps"] = ["мешай", "жарь", "вари", "ешь", "готово"]
        with self.assertRaises(ValidationError):
            RecipeResponse.model_validate(payload)

    def test_accepts_detailed_payload(self) -> None:
        recipe = RecipeResponse.model_validate(_valid_payload())
        self.assertEqual(recipe.title, "Теплый боул с курицей")
        self.assertEqual(len(recipe.ingredients), 4)
        self.assertEqual(len(recipe.steps), 5)


if __name__ == "__main__":
    unittest.main()

