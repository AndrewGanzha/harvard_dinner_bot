from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, PositiveInt, field_validator


def _coerce_to_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized:
                result.append(normalized)
        return result

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []

        lowered = cleaned.lower()
        if lowered in {"нет", "none", "null", "-", "n/a", "не требуется", "не нужно"}:
            return []

        # Common LLM formats: comma/semicolon/newline separated items.
        parts = [p.strip(" \t\r\n•*-") for p in re.split(r"[,\n;]+", cleaned)]
        normalized_parts = [p for p in parts if p]
        if normalized_parts:
            return normalized_parts
        return [cleaned]

    return [str(value).strip()] if str(value).strip() else []


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

    @field_validator(
        "veggies_fruits",
        "whole_grains",
        "proteins",
        "fats",
        "dairy_optional",
        "others",
        mode="before",
    )
    @classmethod
    def _normalize_groups(cls, value: Any) -> list[str]:
        return _coerce_to_list(value)


class RecipeResponse(BaseModel):
    title: str
    ingredients: list[str]
    steps: list[str]
    time_minutes: PositiveInt
    servings: PositiveInt
    plate_map: PlateMap
    nutrition: dict[str, Any] | None = None
    tips: list[str] = Field(default_factory=list)

    @field_validator("ingredients", "steps", "tips", mode="before")
    @classmethod
    def _normalize_lists(cls, value: Any) -> list[str]:
        return _coerce_to_list(value)

    @field_validator("time_minutes", "servings", mode="before")
    @classmethod
    def _normalize_positive_ints(cls, value: Any) -> Any:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            digits = re.search(r"\d+", value)
            if digits:
                return int(digits.group(0))
        return value
