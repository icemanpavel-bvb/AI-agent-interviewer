"""Облачные модели через OpenAI-совместимый API (D-013): Groq, OpenRouter, Gemini, Mistral,
Cerebras, GitHub Models, OpenAI и GigaChat API.

POST {base_url}/chat/completions с ключом в заголовке Authorization. Только стандартная
библиотека. Прокси берётся из переменных окружения (HTTPS_PROXY), как и у urllib в целом.

JSON: сначала просим response_format {"type": "json_object"}; если сервис или модель его
не поддерживает (ошибка 400 про response_format), запоминаем и дальше полагаемся на промпт
(«Верни только JSON») и разбор в complete_json.

GigaChat API: ключ из личного кабинета — это «ключ авторизации», по нему раз в 30 минут
получаем токен доступа (OAuth, scope GIGACHAT_API_PERS для физлиц).

Ключи никогда не попадают в ответы API, журналы и сообщения об ошибках.
"""

from __future__ import annotations

import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from app.llm.base import ChatResult, LLMUnavailable

GIGACHAT_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"


class OpenAICompatProvider:
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        *,
        provider: str = "openai",
        temperature: float = 0.0,
        max_tokens: int = 600,
        timeout: float = 60.0,
        json_mode: bool = True,
        ca_file: str | None = None,
        gigachat_scope: str = "GIGACHAT_API_PERS",
    ) -> None:
        self.model = model
        self.url = base_url.rstrip("/")
        self.provider = provider
        self._api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.json_mode = json_mode
        self.gigachat_scope = gigachat_scope
        self._ssl = ssl.create_default_context(cafile=ca_file) if ca_file else None
        self._token: str | None = None
        self._token_expires = 0.0
        self._token_lock = threading.Lock()

    def __repr__(self) -> str:  # без ключа
        return f"OpenAICompatProvider({self.provider}, {self.model})"

    # ---------- запросы ----------

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
            "temperature": self.temperature,
            "max_tokens": (options or {}).get("num_predict", self.max_tokens),
            "stream": False,
        }
        if json_schema is not None and self.json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            data = self._post("/chat/completions", body)
        except _BadRequest as e:
            if "response_format" in body and "response_format" in e.detail.lower():
                self.json_mode = False  # модель не умеет json_object — дальше без него
                body.pop("response_format")
                data = self._post("/chat/completions", body)
            else:
                raise LLMUnavailable(f"{self._name}: запрос отклонён (400): {e.detail}") from None
        choices = data.get("choices") or [{}]
        usage = data.get("usage") or {}
        return ChatResult(
            text=(choices[0].get("message") or {}).get("content") or "",
            prompt_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    def ping(self) -> tuple[bool, str]:
        """Проверка ключа без генерации: GET /models."""
        try:
            self._request("GET", "/models", None, timeout=10)
        except _BadRequest as e:
            return False, f"{self._name}: {e.detail}"
        except LLMUnavailable as e:
            return False, str(e)
        return True, "ok"

    # ---------- внутреннее ----------

    @property
    def _name(self) -> str:
        return f"{self.provider} ({self.model})"

    def _post(self, path: str, body: dict) -> dict:
        return self._request("POST", path, body)

    def _request(self, method: str, path: str, body: dict | None, timeout: float | None = None):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._bearer()}",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=timeout or self.timeout, context=self._ssl
            ) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = self._hide(e.read().decode("utf-8", "replace")[:300])
            if e.code == 400:
                raise _BadRequest(detail) from None
            if e.code == 401 and self.provider == "gigachat":
                self._token = None  # токен истёк раньше срока — получим новый при следующем ходе
            raise LLMUnavailable(self._explain(e.code, detail)) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as e:
            raise LLMUnavailable(f"{self._name}: нет связи с {self.url}: {e}") from None
        except json.JSONDecodeError as e:
            raise LLMUnavailable(f"{self._name}: ответ сервиса не JSON") from e

    def _explain(self, code: int, detail: str) -> str:
        if code in (401, 403):
            hint = (
                "ключ не принят или сервис недоступен из вашего региона"
                if code == 403
                else "ключ не принят — проверьте llm_keys.json"
            )
        elif code == 404:
            hint = "модель не найдена — проверьте её имя в llm_keys.json"
        elif code == 429:
            hint = "лимит бесплатного тарифа исчерпан — подождите минуту или выберите другую модель"
        else:
            hint = "сервис временно недоступен"
        return f"{self._name}: {hint} (HTTP {code}). {detail}".strip()

    def _hide(self, text: str) -> str:
        return text.replace(self._api_key, "***") if self._api_key else text

    def _bearer(self) -> str:
        if self.provider != "gigachat":
            return self._api_key
        with self._token_lock:
            if self._token and time.time() < self._token_expires - 60:
                return self._token
            self._token, self._token_expires = self._gigachat_token()
            return self._token

    def _gigachat_token(self) -> tuple[str, float]:
        request = urllib.request.Request(
            GIGACHAT_OAUTH_URL,
            data=urllib.parse.urlencode({"scope": self.gigachat_scope}).encode(),
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {self._api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15, context=self._ssl) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as e:
            raise LLMUnavailable(
                f"GigaChat: ключ авторизации не принят (HTTP {e.code}) — проверьте llm_keys.json"
            ) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as e:
            raise LLMUnavailable(
                f"GigaChat: не удалось получить токен: {e}. Если ошибка сертификата — "
                "укажите ca_file с корневым сертификатом Минцифры (см. README)"
            ) from None
        expires = float(data.get("expires_at", 0))
        if expires > 1e12:  # миллисекунды
            expires /= 1000
        return data["access_token"], expires or time.time() + 1500


class _BadRequest(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
