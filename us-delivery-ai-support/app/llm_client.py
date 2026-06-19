"""LLM client abstraction with structured JSON output and deterministic defaults.

All LLM access is funneled through a single :class:`LLMClient`. The client:

* defaults to ``temperature=0`` and ``seed=42`` for deterministic output,
* never crashes at construction when ``OPENAI_API_KEY`` is absent (only calls do),
* parses JSON responses robustly (fence stripping + object extraction),
* and never logs raw prompts or unredacted content.
"""

from __future__ import annotations

import json
import logging
import re

from app.config import Settings, get_settings

logger = logging.getLogger("app.llm_client")


# Exceptions -----------------------------------------------------------------


class LLMClientError(Exception):
    """Base class for all LLM client errors."""


class MissingLLMConfigurationError(LLMClientError):
    """Raised when an LLM call is attempted without an API key configured."""


class LLMResponseError(LLMClientError):
    """Raised when the model returns an empty or obviously invalid response."""


class LLMJSONParseError(LLMClientError):
    """Raised when a response cannot be parsed into a JSON object."""


# Pure parsing helpers -------------------------------------------------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def strip_json_fences(text: str) -> str:
    """Strip a leading/trailing Markdown code fence (```json ... ```)."""
    stripped = (text or "").strip()
    stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def extract_json_object(text: str) -> str:
    """Extract the outermost ``{...}`` JSON object from surrounding text.

    Raises:
        LLMJSONParseError: if no balanced JSON object can be found.
    """
    cleaned = strip_json_fences(text)
    start = cleaned.find("{")
    if start == -1:
        raise LLMJSONParseError("No JSON object found in model response")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1]

    raise LLMJSONParseError("Unbalanced JSON object in model response")


def validate_model_response_text(text: str) -> str:
    """Return *text* if it is a usable response, else raise ``LLMResponseError``."""
    if text is None or not str(text).strip():
        raise LLMResponseError("Model returned an empty response")
    return str(text)


# Client ---------------------------------------------------------------------


class LLMClient:
    """OpenAI-compatible client behind one controlled, deterministic interface."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0,
        seed: int | None = 42,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        # ``api_key`` may be passed explicitly; fall back to settings only when
        # the argument is omitted (None) rather than an explicit empty value.
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.openai_model
        # Optional base URL for OpenAI-compatible providers (e.g. Groq).
        self.base_url = settings.openai_base_url
        self.temperature = temperature
        self.seed = seed
        self._client = None  # Lazily created OpenAI-compatible client.

    def is_configured(self) -> bool:
        """Return True if an API key is present."""
        return bool(self.api_key)

    # -- internal ------------------------------------------------------------

    def _require_config(self) -> None:
        if not self.is_configured():
            raise MissingLLMConfigurationError(
                "OPENAI_API_KEY is not configured. LLM-dependent features "
                "require an API key; set it in your environment or .env file."
            )

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # Imported lazily to keep startup light.

            kwargs: dict = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def _create_completion(self, messages: list[dict], *, json_mode: bool):
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.seed is not None:
            kwargs["seed"] = self.seed
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        client = self._get_client()
        return client.chat.completions.create(**kwargs)

    @staticmethod
    def _build_messages(prompt: str, system_message: str | None) -> list[dict]:
        messages: list[dict] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        return messages

    # -- public API ----------------------------------------------------------

    def complete_text(self, prompt: str, *, system_message: str | None = None) -> str:
        """Return free-text completion. Raises if no API key is configured."""
        self._require_config()
        messages = self._build_messages(prompt, system_message)
        try:
            response = self._create_completion(messages, json_mode=False)
            content = response.choices[0].message.content
        except LLMClientError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrap SDK/transport errors cleanly
            logger.error("LLM text completion failed: %s", type(exc).__name__)
            raise LLMResponseError(
                f"LLM request failed: {type(exc).__name__}"
            ) from exc
        return validate_model_response_text(content)

    def complete_json(self, prompt: str, *, system_message: str | None = None) -> dict:
        """Return a parsed JSON object. Raises on missing config or bad JSON.

        Tries native JSON mode (``response_format={"type": "json_object"}``)
        first. Some OpenAI-compatible providers/models reject that parameter, so
        on a request failure we retry once without it and rely on robust parsing
        (fence stripping + object extraction) instead of crashing.
        """
        self._require_config()
        messages = self._build_messages(prompt, system_message)
        try:
            response = self._create_completion(messages, json_mode=True)
            content = response.choices[0].message.content
        except LLMClientError:
            raise
        except Exception as exc:  # noqa: BLE001 - retry without JSON mode
            logger.info(
                "JSON-mode completion failed (%s); retrying without response_format",
                type(exc).__name__,
            )
            try:
                response = self._create_completion(messages, json_mode=False)
                content = response.choices[0].message.content
            except Exception as exc2:  # noqa: BLE001 - wrap SDK/transport errors
                logger.error("LLM JSON completion failed: %s", type(exc2).__name__)
                raise LLMResponseError(
                    f"LLM request failed: {type(exc2).__name__}"
                ) from exc2

        text = validate_model_response_text(content)
        return self.parse_json_response(text)

    @staticmethod
    def parse_json_response(text: str) -> dict:
        """Parse model text into a JSON object, tolerating fences/extra text."""
        candidate = strip_json_fences(text)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            parsed = json.loads(extract_json_object(text))
        if not isinstance(parsed, dict):
            raise LLMJSONParseError("Model JSON response was not an object")
        return parsed
