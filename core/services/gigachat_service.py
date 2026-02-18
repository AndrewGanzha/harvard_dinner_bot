from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog
from pydantic import ValidationError

from core.config import settings
from core.services.prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from schemas import RecipeResponse

logger = structlog.get_logger(__name__)


class GigaChatError(RuntimeError):
    pass


class GigaChatClient:
    def __init__(
        self,
        token: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.token = token if token is not None else settings.gigachat_token
        self.api_url = (api_url if api_url is not None else settings.gigachat_api_url).rstrip("/")
        self.model = model if model is not None else settings.gigachat_model
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.gigachat_timeout_seconds
        )
        self.max_retries = max_retries if max_retries is not None else settings.gigachat_max_retries

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        payload = text.strip()
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", payload, flags=re.DOTALL)
        if not match:
            raise GigaChatError("LLM returned response without JSON object")
        return json.loads(match.group(0))

    @staticmethod
    def _format_list(items: list[str]) -> str:
        return ", ".join(items) if items else "нет"

    def _build_messages(
        self,
        ingredients: list[str],
        missing_groups: list[str],
        user_preferences: str | None = None,
    ) -> list[dict[str, str]]:
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ingredients=self._format_list(ingredients),
            missing_groups=self._format_list(missing_groups),
            user_preferences=user_preferences or "нет",
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt.strip()},
        ]

    async def generate_recipe(
        self,
        ingredients: list[str],
        missing_groups: list[str],
        user_preferences: str | None = None,
    ) -> RecipeResponse:
        if not self.token:
            raise GigaChatError("GIGACHAT_TOKEN is empty")

        request_payload = {
            "model": self.model,
            "messages": self._build_messages(ingredients, missing_groups, user_preferences),
            "temperature": 0.3,
        }
        headers = {"Authorization": f"Bearer {self.token}"}

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.api_url}/chat/completions",
                        json=request_payload,
                        headers=headers,
                    )
                    response.raise_for_status()

                response_json = response.json()
                llm_text = (
                    response_json.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if not llm_text:
                    raise GigaChatError("LLM returned empty response")

                parsed = self._extract_json(llm_text)
                validated = RecipeResponse.model_validate(parsed)
                logger.info("gigachat_recipe_validated", attempt=attempt)
                return validated
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError, GigaChatError) as exc:
                last_error = exc
                logger.warning(
                    "gigachat_attempt_failed",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(exc),
                )

        raise GigaChatError(f"Failed to get valid recipe after {self.max_retries} attempts: {last_error}")
