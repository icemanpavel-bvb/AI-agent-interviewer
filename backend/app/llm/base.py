"""Интерфейс провайдера и фабрика по LLM_PROVIDER."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    async def complete(self, system: str, user: str, *, temperature: float = 0.3) -> str: ...


async def complete_json(
    provider: LLMProvider, system: str, user: str, schema: type[T], retries: int = 2
) -> T:
    """Вызов с JSON-ответом: парсинг + валидация Pydantic, при ошибке — повтор с указанием ошибки.
    Каждый вызов пишется в llm_call (purpose, model, prompt_version, latency, valid_json)."""
    raise NotImplementedError


def get_provider() -> LLMProvider:
    """ollama | gigachat | yandexgpt — по settings.llm_provider."""
    raise NotImplementedError
