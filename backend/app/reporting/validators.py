"""Проверки кодом, а не моделью (D-004): цитаты действительно есть в ответе; нет баллов и оценок."""

import re
from difflib import SequenceMatcher

FORBIDDEN = re.compile(
    r"\b(балл\w*|\d+\s*/\s*10|рейтинг\w*|рекомендую|не рекомендую|"
    r"подходит|не подходит|сильный кандидат|слабый кандидат|оценка кандидата)\b",
    re.IGNORECASE,
)

_NON_WORD = re.compile(r"[^\w\s]")


def normalize(text: str) -> str:
    """Нижний регистр, ё→е, без пунктуации, одиночные пробелы."""
    text = text.lower().replace("ё", "е")
    return " ".join(_NON_WORD.sub(" ", text).split())


def quote_is_grounded(
    quote: str, text: str, *, min_chars: int = 3, tolerance: float = 0.85
) -> bool:
    """Цитата есть в тексте: точное вхождение после нормализации или совпадение ≥ 85 % длины
    (модель иногда меняет окончание или пропускает слово)."""
    q, t = normalize(quote), normalize(text)
    if len(q) < min_chars or not t:
        return False
    if q in t:
        return True
    match = SequenceMatcher(None, q, t, autojunk=False).find_longest_match(0, len(q), 0, len(t))
    return match.size >= tolerance * len(q)


def has_forbidden_language(text: str) -> bool:
    return bool(FORBIDDEN.search(text))


def leaks_reference(text: str, reference: str, n: int = 4) -> bool:
    """Есть ли в тексте подряд n слов из эталонного ответа (не подсказывает ли уточнение ответ)."""
    words, ref = normalize(text).split(), normalize(reference).split()
    if len(words) < n or len(ref) < n:
        return False
    ref_shingles = {tuple(ref[i : i + n]) for i in range(len(ref) - n + 1)}
    return any(tuple(words[i : i + n]) in ref_shingles for i in range(len(words) - n + 1))
