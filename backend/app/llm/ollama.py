"""Провайдер Ollama (по умолчанию, D-001): POST {url}/api/chat, ответ по JSON-схеме через `format`.

Только стандартная библиотека. Параметры по замерам на ноутбуке без GPU:
temperature 0, num_ctx 4096, keep_alive 30m (кэш служебного блока шаблона GigaChat).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from app.llm.base import ChatResult, LLMUnavailable


class OllamaProvider:
    def __init__(
        self,
        model: str | None = None,
        url: str | None = None,
        *,
        temperature: float = 0.0,
        num_ctx: int = 4096,
        num_predict: int = 600,
        keep_alive: str = "30m",
        timeout: float = 180.0,
    ) -> None:
        self.model = model or os.getenv("LLM_MODEL", "gigachat-lightning")
        self.url = (url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.options = {"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict}
        self.keep_alive = keep_alive
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict | None = None,
        options: dict | None = None,
    ) -> ChatResult:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {**self.options, **(options or {})},
        }
        if json_schema is not None:
            body["format"] = json_schema
        request = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise LLMUnavailable(f"Ollama вернула ошибку {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise LLMUnavailable(f"Ollama недоступна по адресу {self.url}: {e}") from e
        return ChatResult(
            text=data.get("message", {}).get("content", ""),
            prompt_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )

    def ping(self) -> tuple[bool, str]:
        """Быстрая проверка без генерации: Ollama отвечает и модель скачана."""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as response:
                names = {m.get("name", "") for m in json.loads(response.read()).get("models", [])}
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            return False, f"Ollama недоступна по адресу {self.url}: {e}"
        if self.model not in names and f"{self.model}:latest" not in names:
            return False, f"Модель {self.model} не найдена в Ollama (ollama list)"
        return True, "ok"

    def warmup(self) -> None:
        """Прогрев: загружает модель и кэширует служебный блок шаблона (~30 с при холодном старте)."""
        self.chat([{"role": "user", "content": "Привет"}], options={"num_predict": 1})
