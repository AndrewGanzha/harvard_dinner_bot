from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, PositiveInt


class PlateMap(BaseModel):
    veggies_fruits: list[str] = Field(default_factory=list)
    whole_grains: list[str] = Field(default_factory=list)
    proteins: list[str] = Field(default_factory=list)
    fats: list[str] = Field(default_factory=list)
    dairy_optional: list[str] = Field(default_factory=list, alias="dairy(optional)")
    others: list[str] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
    }


class RecipeResponse(BaseModel):
    title: str
    ingredients: list[str]
    steps: list[str]
    time_minutes: PositiveInt
    servings: PositiveInt
    plate_map: PlateMap
    nutrition: dict[str, Any] | None = None
    tips: list[str] = Field(default_factory=list)
