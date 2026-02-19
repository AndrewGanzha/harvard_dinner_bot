from __future__ import annotations

import unittest

from core.services.safety_service import (
    build_block_message,
    check_recipe_output,
    check_user_input,
)


class SafetyServiceTests(unittest.TestCase):
    def test_blocks_cannibalism_in_user_input(self) -> None:
        result = check_user_input(["картофель", "человечина"])
        self.assertFalse(result.is_safe)
        self.assertEqual(result.category, "cannibalism_human_tissue")

    def test_blocks_dangerous_non_food(self) -> None:
        result = check_user_input("салат с бензином и укропом")
        self.assertFalse(result.is_safe)
        self.assertEqual(result.category, "dangerous_non_food")

    def test_allows_normal_food(self) -> None:
        result = check_user_input(["курица", "рис", "огурец"])
        self.assertTrue(result.is_safe)
        self.assertIsNone(result.category)

    def test_blocks_unsafe_recipe_output(self) -> None:
        result = check_recipe_output(
            recipe_title="Паста",
            ingredients=["спагетти", "соус"],
            steps=["Добавьте отбеливатель в кастрюлю"],
        )
        self.assertFalse(result.is_safe)
        self.assertEqual(result.category, "dangerous_non_food")

    def test_block_message_contains_alternatives(self) -> None:
        result = check_user_input("героин")
        text = build_block_message(result)
        self.assertIn("запрещенные", text)
        self.assertIn("альтернативы", text)


if __name__ == "__main__":
    unittest.main()

