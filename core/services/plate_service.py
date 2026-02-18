from __future__ import annotations

import re
from dataclasses import dataclass

GROUP_VEGGIES_FRUITS = "veggies_fruits"
GROUP_WHOLE_GRAINS = "whole_grains"
GROUP_PROTEINS = "proteins"
GROUP_FATS = "fats"
GROUP_DAIRY_OPTIONAL = "dairy(optional)"
GROUP_OTHERS = "others"

GROUP_ORDER = (
    GROUP_VEGGIES_FRUITS,
    GROUP_WHOLE_GRAINS,
    GROUP_PROTEINS,
    GROUP_FATS,
    GROUP_DAIRY_OPTIONAL,
    GROUP_OTHERS,
)

REQUIRED_GROUPS = (
    GROUP_VEGGIES_FRUITS,
    GROUP_PROTEINS,
    GROUP_WHOLE_GRAINS,
)

GROUP_KEYWORDS: dict[str, tuple[str, ...]] = {
    GROUP_VEGGIES_FRUITS: (
        "брокколи",
        "помидор",
        "томат",
        "огурец",
        "шпинат",
        "салат",
        "морковь",
        "перец",
        "лук",
        "яблок",
        "банан",
        "груш",
        "ягод",
        "капуст",
        "кабач",
    ),
    GROUP_WHOLE_GRAINS: (
        "гречк",
        "рис",
        "овсян",
        "киноа",
        "булгур",
        "перлов",
        "цельнозерн",
        "макарон",
        "хлеб",
        "паста",
    ),
    GROUP_PROTEINS: (
        "куриц",
        "курин",
        "индейк",
        "говядин",
        "рыб",
        "лосос",
        "тунец",
        "яйц",
        "нут",
        "фасол",
        "чечевиц",
        "тофу",
        "кревет",
    ),
    GROUP_FATS: (
        "авокадо",
        "масл",
        "оливк",
        "орех",
        "миндал",
        "семечк",
        "кунжут",
        "арахис",
    ),
    GROUP_DAIRY_OPTIONAL: (
        "йогурт",
        "кефир",
        "молок",
        "сыр",
        "творог",
        "ряженк",
    ),
}

RECOMMENDATION_POOL: dict[str, tuple[str, ...]] = {
    GROUP_VEGGIES_FRUITS: ("брокколи", "шпинат", "помидоры"),
    GROUP_WHOLE_GRAINS: ("гречка", "киноа", "овсянка"),
    GROUP_PROTEINS: ("куриная грудка", "яйца", "нут"),
    GROUP_FATS: ("авокадо", "оливковое масло", "грецкие орехи"),
    GROUP_DAIRY_OPTIONAL: ("греческий йогурт", "творог", "кефир"),
}


@dataclass(slots=True)
class PlateAnalysis:
    covered_groups: list[str]
    missing_groups: list[str]
    recommendations: list[str]
    classified_ingredients: dict[str, list[str]]


class PlateService:
    @staticmethod
    def _normalize(ingredient: str) -> str:
        return re.sub(r"[^a-zа-я0-9 ]+", "", ingredient.lower()).strip()

    def classify_ingredients(self, ingredients: list[str]) -> dict[str, list[str]]:
        classified = {group: [] for group in GROUP_ORDER}

        for ingredient in ingredients:
            normalized = self._normalize(ingredient)
            matched_group = None

            for group, keywords in GROUP_KEYWORDS.items():
                if any(keyword in normalized for keyword in keywords):
                    matched_group = group
                    break

            target_group = matched_group or GROUP_OTHERS
            classified[target_group].append(ingredient)

        return classified

    @staticmethod
    def get_missing_groups(classified: dict[str, list[str]]) -> list[str]:
        return [group for group in REQUIRED_GROUPS if not classified.get(group)]

    @staticmethod
    def build_recommendations(missing_groups: list[str], limit: int = 3) -> list[str]:
        recommendations: list[str] = []
        for group in missing_groups:
            candidates = RECOMMENDATION_POOL.get(group, ())
            for ingredient in candidates:
                if ingredient not in recommendations:
                    recommendations.append(ingredient)
                    break
            if len(recommendations) >= limit:
                break
        return recommendations

    def analyze(self, ingredients: list[str]) -> PlateAnalysis:
        classified = self.classify_ingredients(ingredients)
        covered_groups = [group for group in GROUP_ORDER if classified.get(group)]
        missing_groups = self.get_missing_groups(classified)
        recommendations = self.build_recommendations(missing_groups)
        return PlateAnalysis(
            covered_groups=covered_groups,
            missing_groups=missing_groups,
            recommendations=recommendations,
            classified_ingredients=classified,
        )
