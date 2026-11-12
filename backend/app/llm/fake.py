"""Фейковая модель для тестов: отдаёт заранее заданные ответы по очереди.

Ответ может быть строкой, словарём (будет превращён в JSON) или функцией messages -> str | dict.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable
from typing import Any

from app.llm.base import ChatResult, LLMError

Response = str | dict | Callable[[list[dict[str, str]]], Any]


class FakeLLM:
    model = "fake"

    def __init__(self, responses: list[Response] | None = None, default: Response | None = None):
        self.responses: deque[Response] = deque(responses or [])
        self.default = default
        self.requests: list[list[dict[str, str]]] = []

    def chat(self, messages, *, json_schema=None, options=None) -> ChatResult:
        self.requests.append(messages)
        if self.responses:
            response = self.responses.popleft()
        elif self.default is not None:
            response = self.default
        else:
            raise LLMError("FakeLLM: ответы закончились")
        if callable(response):
            response = response(messages)
        if isinstance(response, dict):
            response = json.dumps(response, ensure_ascii=False)
        return ChatResult(text=response)
