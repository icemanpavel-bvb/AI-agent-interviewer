"""Реестр моделей (D-013): локальная модель из .env плюс облачные из файла llm_keys.json.

Файл лежит в корне репозитория, в .gitignore; образец — llm_keys.example.json.
Ключ словаря — имя модели в интерфейсе, значение — ключ API. Короткая запись:

    "groq/llama-3.3-70b-versatile": "gsk_..."

до первой «/» — сервис (по нему выбирается адрес API), дальше — имя модели у сервиса.
Полная запись — когда нужен свой адрес или параметры:

    "моя-модель": {"provider": "custom", "base_url": "https://.../v1",
                   "model": "имя-у-сервиса", "api_key": "...", "json_mode": false}

Файл перечитывается при изменении — перезапускать сервер после правки ключей не нужно.
Наружу (в API и в браузер) отдаются только имена моделей, ключи — никогда.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from app.llm.base import LLMProvider, LLMUnavailable
from app.llm.openai_compat import OpenAICompatProvider

log = logging.getLogger("app.llm")

LOCAL_ID = "local"

# Адреса OpenAI-совместимых API. train — бесплатный тариф может использовать запросы
# для обучения моделей (по условиям сервиса на ноябрь 2026, проверяйте сами).
PRESETS: dict[str, dict] = {
    "groq": {"base_url": "https://api.groq.com/openai/v1"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1"},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "train": True,
    },
    "mistral": {"base_url": "https://api.mistral.ai/v1", "train": True},
    "cerebras": {"base_url": "https://api.cerebras.ai/v1"},
    "github": {"base_url": "https://models.github.ai/inference"},
    "openai": {"base_url": "https://api.openai.com/v1"},
    "gigachat": {"base_url": "https://api.giga.chat/v1"},
}


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    model: str
    local: bool
    note: str = ""


class ModelRegistry:
    def __init__(self, local: LLMProvider, keys_file: Path, *, max_tokens: int = 600) -> None:
        self.local = local
        self.keys_file = keys_file
        self.max_tokens = max_tokens
        self._mtime: float | None = None
        self._specs: dict[str, dict] = {}
        self._providers: dict[str, LLMProvider] = {}
        self._lock = threading.Lock()

    # ---------- публичный интерфейс ----------

    def list(self) -> list[ModelInfo]:
        self._reload()
        local = ModelInfo(
            LOCAL_ID, "ollama", getattr(self.local, "model", "?"), True, "на этом компьютере"
        )
        cloud = [
            ModelInfo(
                name,
                spec["provider"],
                spec["model"],
                False,
                "бесплатный тариф может использовать запросы для обучения"
                if PRESETS.get(spec["provider"], {}).get("train")
                else "",
            )
            for name, spec in self._specs.items()
        ]
        return [local, *cloud]

    def get(self, model_id: str | None) -> LLMProvider:
        if not model_id or model_id == LOCAL_ID:
            return self.local
        self._reload()
        with self._lock:
            if model_id in self._providers:
                return self._providers[model_id]
            spec = self._specs.get(model_id)
            if spec is None:
                raise LLMUnavailable(
                    f"Модель «{model_id}» не найдена в llm_keys.json — выберите другую на странице /demo"
                )
            provider = OpenAICompatProvider(
                spec["model"],
                spec["base_url"],
                spec["api_key"],
                provider=spec["provider"],
                max_tokens=self.max_tokens,
                json_mode=spec.get("json_mode", True),
                ca_file=spec.get("ca_file"),
            )
            self._providers[model_id] = provider
            return provider

    def has(self, model_id: str | None) -> bool:
        return not model_id or model_id == LOCAL_ID or model_id in {m.id for m in self.list()}

    # ---------- чтение файла ----------

    def _reload(self) -> None:
        try:
            mtime = self.keys_file.stat().st_mtime
        except FileNotFoundError:
            mtime = None
        with self._lock:
            if mtime == self._mtime:
                return
            self._mtime = mtime
            self._providers.clear()
            self._specs = parse_keys(self.keys_file) if mtime is not None else {}


def parse_keys(path: Path) -> dict[str, dict]:
    """Читает llm_keys.json; ошибочные записи пропускает с предупреждением в журнале."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("не удалось прочитать %s: %s", path.name, e)
        return {}
    if not isinstance(raw, dict):
        log.warning("%s: ожидается словарь {имя модели: ключ}", path.name)
        return {}
    specs: dict[str, dict] = {}
    for name, value in raw.items():
        if name.startswith("_") or name == LOCAL_ID:
            continue  # «_comment» и т. п.
        try:
            specs[name] = _spec(name, value)
        except ValueError as e:
            log.warning("%s: запись «%s» пропущена: %s", path.name, name, e)
    return specs


def _spec(name: str, value: str | dict) -> dict:
    if isinstance(value, str):
        provider, _, model = name.partition("/")
        spec = {"provider": provider, "model": model, "api_key": value}
    elif isinstance(value, dict):
        spec = dict(value)
        spec.setdefault("provider", "custom")
    else:
        raise ValueError("значение — строка с ключом или объект")
    provider = spec["provider"]
    spec.setdefault("base_url", PRESETS.get(provider, {}).get("base_url"))
    if not spec.get("base_url"):
        raise ValueError(f"неизвестный сервис «{provider}» — укажите base_url")
    if not spec.get("model"):
        raise ValueError("не указано имя модели (в короткой записи: сервис/модель)")
    key = str(spec.get("api_key") or "")
    if not key or "..." in key or key.startswith("<"):
        raise ValueError("ключ не заполнен")
    return spec
