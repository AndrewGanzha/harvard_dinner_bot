from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

import httpx
import structlog
from pydantic import ValidationError

from core.config import settings
from core.services.prompt_templates import (
    INGREDIENTS_PROMPT_TEMPLATE,
    READY_DISH_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from schemas import RecipeResponse

logger = structlog.get_logger(__name__)


class GigaChatError(RuntimeError):
    pass


class GigaChatClient:
    def __init__(
        self,
        token: str | None = None,
        auth_key: str | None = None,
        oauth_url: str | None = None,
        scope: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.auth_key = (
            auth_key
            if auth_key is not None
            else (token if token is not None else (settings.gigachat_authorization_key or settings.gigachat_token))
        )
        self.oauth_url = (oauth_url if oauth_url is not None else settings.gigachat_oauth_url).rstrip("/")
        self.scope = scope if scope is not None else settings.gigachat_scope
        self.api_url = (api_url if api_url is not None else settings.gigachat_api_url).rstrip("/")
        self.model = model if model is not None else settings.gigachat_model
        self.ssl_verify = settings.gigachat_ssl_verify
        self.ca_bundle = settings.gigachat_ca_bundle.strip()
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.gigachat_timeout_seconds
        )
        self.max_retries = max_retries if max_retries is not None else settings.gigachat_max_retries

        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0

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

    def _has_valid_access_token(self) -> bool:
        return bool(self._access_token) and time.time() < (self._access_token_expires_at - 30)

    @property
    def _httpx_verify(self) -> bool | str:
        return self.ca_bundle or self.ssl_verify

    @staticmethod
    def _auth_header_value(auth_key: str) -> str:
        value = auth_key.strip()
        if value.lower().startswith("basic "):
            return value
        return f"Basic {value}"

    async def _fetch_access_token(self, client: httpx.AsyncClient) -> str:
        if not self.auth_key:
            raise GigaChatError("GIGACHAT_AUTH_KEY is empty")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": self._auth_header_value(self.auth_key),
        }
        response = await client.post(
            self.oauth_url,
            data={"scope": self.scope},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

        access_token = str(payload.get("access_token", "")).strip()
        if not access_token:
            raise GigaChatError("OAuth response does not contain access_token")

        expires_at_raw = payload.get("expires_at")
        expires_in_raw = payload.get("expires_in")
        now = time.time()
        expires_at = 0.0

        if expires_at_raw is not None:
            try:
                expires_at = float(expires_at_raw)
                if expires_at > 1_000_000_000_000:
                    expires_at /= 1000.0
            except (TypeError, ValueError):
                expires_at = 0.0
        elif expires_in_raw is not None:
            try:
                expires_at = now + float(expires_in_raw)
            except (TypeError, ValueError):
                expires_at = 0.0

        if expires_at <= now:
            expires_at = now + 1800

        self._access_token = access_token
        self._access_token_expires_at = expires_at
        return access_token

    async def _get_access_token(
        self,
        client: httpx.AsyncClient,
        *,
        force_refresh: bool = False,
    ) -> str:
        if not force_refresh and self._has_valid_access_token():
            return self._access_token or ""
        return await self._fetch_access_token(client)

    def _build_messages_for_ingredients(
        self,
        ingredients: list[str],
        missing_groups: list[str],
        user_preferences: str | None = None,
    ) -> list[dict[str, str]]:
        user_prompt = INGREDIENTS_PROMPT_TEMPLATE.format(
            ingredients=self._format_list(ingredients),
            missing_groups=self._format_list(missing_groups),
            user_preferences=user_preferences or "нет",
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt.strip()},
        ]

    def _build_messages_for_ready_dish(
        self,
        dish_request: str,
        user_preferences: str | None = None,
    ) -> list[dict[str, str]]:
        user_prompt = READY_DISH_PROMPT_TEMPLATE.format(
            dish_request=dish_request.strip(),
            user_preferences=user_preferences or "нет",
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt.strip()},
        ]

    async def _request_recipe(self, messages: list[dict[str, str]], scenario: str) -> RecipeResponse:
        request_payload = {
            "model": self.model,
            "messages": messages,
            "n": 1,
            "stream": False,
            "max_tokens": 512,
            "repetition_penalty": 1,
            "update_interval": 0,
            "temperature": 0.3,
        }

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds, verify=self._httpx_verify) as client:
                    access_token = await self._get_access_token(client)
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}",
                    }
                    response = await client.post(
                        f"{self.api_url}/chat/completions",
                        json=request_payload,
                        headers=headers,
                    )
                    if response.status_code == 401:
                        access_token = await self._get_access_token(client, force_refresh=True)
                        headers["Authorization"] = f"Bearer {access_token}"
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
                logger.info("gigachat_recipe_validated", attempt=attempt, scenario=scenario)
                return validated
            except httpx.HTTPStatusError as exc:
                last_error = GigaChatError(
                    f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
                )
                logger.warning(
                    "gigachat_attempt_failed",
                    scenario=scenario,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(last_error),
                )
            except (httpx.RequestError, json.JSONDecodeError, ValidationError, GigaChatError) as exc:
                last_error = exc
                logger.warning(
                    "gigachat_attempt_failed",
                    scenario=scenario,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(exc),
                )

        raise GigaChatError(f"Failed to get valid recipe after {self.max_retries} attempts: {last_error}")

    async def generate_recipe(
        self,
        ingredients: list[str],
        missing_groups: list[str],
        user_preferences: str | None = None,
    ) -> RecipeResponse:
        return await self.generate_recipe_from_ingredients(
            ingredients=ingredients,
            missing_groups=missing_groups,
            user_preferences=user_preferences,
        )

    async def generate_recipe_from_ingredients(
        self,
        ingredients: list[str],
        missing_groups: list[str],
        user_preferences: str | None = None,
    ) -> RecipeResponse:
        messages = self._build_messages_for_ingredients(
            ingredients=ingredients,
            missing_groups=missing_groups,
            user_preferences=user_preferences,
        )
        return await self._request_recipe(messages=messages, scenario="ingredients")

    async def generate_ready_dish(
        self,
        dish_request: str,
        user_preferences: str | None = None,
    ) -> RecipeResponse:
        normalized_request = dish_request.strip()
        if not normalized_request:
            raise GigaChatError("Dish request is empty")

        messages = self._build_messages_for_ready_dish(
            dish_request=normalized_request,
            user_preferences=user_preferences,
        )
        return await self._request_recipe(messages=messages, scenario="ready_dish")
