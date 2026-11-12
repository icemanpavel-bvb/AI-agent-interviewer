"""Проверки входа (длина, пустые сообщения, попытки взлома промпта) и выхода модели (тон, оценки, эталон)."""

from __future__ import annotations

import re

from app.reporting.validators import has_forbidden_language, leaks_reference

MAX_INPUT_CHARS = 2000

_INJECTION = re.compile(
    r"(игнорир\w*|забудь\w*)\s+(все\s+)?(предыдущ\w*|инструкц\w*|правил\w*)"
    r"|ignore\s+(all\s+)?previous|system\s*:|ты\s+теперь|you\s+are\s+now|поставь\s+мне",
    re.IGNORECASE,
)


def clean_input(text: str) -> tuple[str, list[str]]:
    """Возвращает очищенный текст и флаги: empty, too_long, injection.

    Угловые скобки заменяются, чтобы ответ не мог «закрыть» тег <answer> в промпте.
    """
    flags: list[str] = []
    text = (text or "").strip()
    if not text:
        return "", ["empty"]
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
        flags.append("too_long")
    if _INJECTION.search(text):
        flags.append("injection")
    text = text.replace("<", "‹").replace(">", "›")
    return text, flags


def output_is_safe(text: str, reference_answer: str = "") -> bool:
    """Реплика модели не содержит оценок и не пересказывает эталонный ответ."""
    if not text.strip() or has_forbidden_language(text):
        return False
    return not (reference_answer and leaks_reference(text, reference_answer))
