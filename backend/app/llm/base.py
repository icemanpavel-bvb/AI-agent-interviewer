"""LLM Gateway: единый интерфейс к моделям и вызов с ответом строго по JSON-схеме.

Код синхронный: так проще в CLI и тестах; в FastAPI вызывается из обычных (def) эндпоинтов
или через run_in_threadpool. Внешних зависимостей нет — только pydantic.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Модель так и не вернула корректный ответ."""


class LLMUnavailable(LLMError):
    """Модель недоступна (Ollama не запущена, нет модели, таймаут): ход нужно повторить позже."""


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class LLMCall:
    """Запись журнала вызовов (без текста — в нём могут быть ПДн)."""

    purpose: str
    model: str
    prompt_version: str
    latency_ms: int
    valid_json: bool
    attempts: int
    prompt_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    model: str

    def chat(
        self, messages: list[dict[str, str]], *, json_schema: dict | None = None
    ) -> ChatResult:
        """Один запрос к модели. json_schema — ограничить ответ этой схемой."""
        ...


def extract_json(text: str) -> str:
    """Вырезает JSON-объект из ответа (модели иногда оборачивают его в ```json ... ```)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("в ответе нет JSON-объекта")
    return text[start : end + 1]


def complete_json(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    schema: type[T],
    *,
    purpose: str,
    prompt_version: str,
    log: list[LLMCall] | None = None,
    retries: int = 2,
) -> T:
    """Вызов модели с ответом по схеме: разбор, проверка Pydantic, повтор с текстом ошибки."""
    started = time.monotonic()
    attempt_messages = list(messages)
    prompt_tokens = output_tokens = None
    error = ""
    for attempt in range(1, retries + 2):
        result = provider.chat(attempt_messages, json_schema=schema.model_json_schema())
        prompt_tokens, output_tokens = result.prompt_tokens, result.output_tokens
        try:
            parsed = schema.model_validate_json(extract_json(result.text))
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            error = str(e)[:300]
            attempt_messages = [
                *messages,
                {"role": "assistant", "content": result.text},
                {
                    "role": "user",
                    "content": f"Ответ не соответствует схеме: {error}. Верни только корректный JSON.",
                },
            ]
            continue
        _log(
            log,
            purpose,
            provider,
            prompt_version,
            started,
            True,
            attempt,
            prompt_tokens,
            output_tokens,
        )
        return parsed
    _log(
        log,
        purpose,
        provider,
        prompt_version,
        started,
        False,
        retries + 1,
        prompt_tokens,
        output_tokens,
    )
    raise LLMError(f"{purpose}: модель не вернула корректный JSON ({error})")


def _log(log, purpose, provider, version, started, ok, attempts, p_tokens, o_tokens) -> None:
    if log is None:
        return
    log.append(
        LLMCall(
            purpose=purpose,
            model=getattr(provider, "model", "?"),
            prompt_version=version,
            latency_ms=int((time.monotonic() - started) * 1000),
            valid_json=ok,
            attempts=attempts,
            prompt_tokens=p_tokens,
            output_tokens=o_tokens,
        )
    )
