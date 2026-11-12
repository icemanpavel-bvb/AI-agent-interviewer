"""Проверки протокола кодом: цитаты есть в сообщениях кандидата; нет баллов и оценочной лексики."""

import re

FORBIDDEN = re.compile(
    r"\b(балл\w*|\d+\s*/\s*10|\d+\s*%|рейтинг\w*|рекомендую|не рекомендую|"
    r"подходит|не подходит|сильный кандидат|слабый кандидат|оценка кандидата)\b",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def quote_is_grounded(quote: str, message_text: str) -> bool:
    return _norm(quote) in _norm(message_text)


def has_forbidden_language(text: str) -> bool:
    return bool(FORBIDDEN.search(text))
