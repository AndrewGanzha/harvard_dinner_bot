from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog
from gigachat import GigaChat
from gigachat import exceptions as gigachat_exceptions
from pydantic import ValidationError

from core.config import settings
from core.services.prompt_templates import (
    INGREDIENTS_PROMPT_TEMPLATE,
    READY_DISH_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from core.services.safety_service import check_recipe_output
from schemas import RecipeResponse

logger = structlog.get_logger(__name__)


class _MissingSDKException(Exception):
    pass


AuthenticationError = getattr(gigachat_exceptions, "AuthenticationError", _MissingSDKException)
ForbiddenError = getattr(
    gigachat_exceptions,
    "ForbiddenError",
    getattr(gigachat_exceptions, "PermissionDeniedError", _MissingSDKException),
)
BadRequestError = getattr(gigachat_exceptions, "BadRequestError", _MissingSDKException)
ResponseError = getattr(gigachat_exceptions, "ResponseError", _MissingSDKException)


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

    def _build_gigachat_kwargs(self) -> dict[str, Any]:
        if not self.auth_key:
            raise GigaChatError("GIGACHAT_AUTH_KEY is empty")

        kwargs: dict[str, Any] = {
            "credentials": self.auth_key,
            "scope": self.scope,
            "base_url": self.api_url,
            "auth_url": self.oauth_url,
            "model": self.model,
            "timeout": self.timeout_seconds,
            "verify_ssl_certs": self.ssl_verify,
        }
        if self.ca_bundle:
            kwargs["ca_bundle_file"] = self.ca_bundle
        return kwargs

    @staticmethod
    async def _sdk_chat(client: Any, request_payload: dict[str, Any]) -> Any:
        achat = getattr(client, "achat", None)
        if callable(achat):
            return await achat(request_payload)

        chat = getattr(client, "chat", None)
        if callable(chat):
            return await asyncio.to_thread(chat, request_payload)

        raise GigaChatError("GigaChat SDK client doesn't provide chat/achat methods")

    @staticmethod
    def _extract_response_content(response: Any) -> str:
        if isinstance(response, dict):
            return str(response.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()

        choices = getattr(response, "choices", None)
        if choices:
            first = choices[0]
            message = getattr(first, "message", None)
            if message is not None:
                return str(getattr(message, "content", "")).strip()

        model_dump = getattr(response, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, dict):
                return str(dumped.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
        return ""

    @staticmethod
    def _status_code_from_exception(exc: Exception) -> int | None:
        for attr_name in ("status_code", "status", "code"):
            value = getattr(exc, attr_name, None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value

        for arg in getattr(exc, "args", ()):
            if isinstance(arg, int) and 100 <= arg <= 599:
                return arg

        match = re.search(r"\b([45]\d{2})\b", str(exc))
        if match:
            return int(match.group(1))
        return None

    @classmethod
    def _map_response_error(cls, exc: Exception) -> GigaChatError:
        status_code = cls._status_code_from_exception(exc)
        details = str(exc)
        details_upper = details.upper()

        if status_code == 401:
            return GigaChatError(f"HTTP 401: {details}")
        if status_code == 403:
            return GigaChatError(f"HTTP 403: {details}")
        if status_code == 400:
            return GigaChatError(f"HTTP 400: {details}")
        if status_code is not None:
            return GigaChatError(f"HTTP {status_code}: {details}")
        if "SSL" in details_upper or "TLS" in details_upper or "CERT" in details_upper:
            return GigaChatError(f"SSL/TLS/CERT: {details}")
        return GigaChatError(details or exc.__class__.__name__)

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
            "max_tokens": 900,
            "repetition_penalty": 1,
            "update_interval": 0,
            "temperature": 0.3,
        }

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                client = GigaChat(**self._build_gigachat_kwargs())
                if hasattr(client, "__aenter__") and hasattr(client, "__aexit__"):
                    async with client as sdk_client:
                        response = await self._sdk_chat(sdk_client, request_payload)
                elif hasattr(client, "__enter__") and hasattr(client, "__exit__"):
                    with client as sdk_client:
                        response = await self._sdk_chat(sdk_client, request_payload)
                else:
                    response = await self._sdk_chat(client, request_payload)

                llm_text = self._extract_response_content(response)
                if not llm_text:
                    raise GigaChatError("LLM returned empty response")

                parsed = self._extract_json(llm_text)
                validated = RecipeResponse.model_validate(parsed)
                safety_result = check_recipe_output(
                    recipe_title=validated.title,
                    ingredients=validated.ingredients,
                    steps=validated.steps,
                )
                if not safety_result.is_safe:
                    logger.warning(
                        "gigachat_recipe_blocked_by_safety",
                        scenario=scenario,
                        category=safety_result.category,
                        matched_terms=list(safety_result.matched_terms),
                    )
                    raise GigaChatError(
                        "UNSAFE_RECIPE: "
                        f"category={safety_result.category}; terms={','.join(safety_result.matched_terms)}"
                    )
                logger.info("gigachat_recipe_validated", attempt=attempt, scenario=scenario)
                return validated
            except AuthenticationError as exc:
                raise GigaChatError(f"HTTP 401: {exc}") from exc
            except ForbiddenError as exc:
                raise GigaChatError(f"HTTP 403: {exc}") from exc
            except BadRequestError as exc:
                raise GigaChatError(f"HTTP 400: {exc}") from exc
            except ResponseError as exc:
                last_error = self._map_response_error(exc)
                logger.warning(
                    "gigachat_attempt_failed",
                    scenario=scenario,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(last_error),
                )
            except (json.JSONDecodeError, ValidationError, GigaChatError) as exc:
                last_error = exc
                logger.warning(
                    "gigachat_attempt_failed",
                    scenario=scenario,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(exc),
                )
            except Exception as exc:
                last_error = self._map_response_error(exc)
                logger.warning(
                    "gigachat_attempt_failed",
                    scenario=scenario,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(last_error),
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
