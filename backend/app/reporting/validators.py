"""Проверки кодом, а не моделью (D-004): цитаты действительно есть в ответе; нет баллов и оценок."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Literal

FORBIDDEN = re.compile(
    r"\b(балл\w*|\d+\s*/\s*10|рейтинг\w*|рекомендую|не рекомендую|"
    r"подходит|не подходит|сильный кандидат|слабый кандидат|оценка кандидата)\b",
    re.IGNORECASE,
)

_NON_WORD = re.compile(r"[^\w\s]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;…])\s+|\n+")

QuoteCheck = Literal["exact", "fuzzy"]


def normalize(text: str) -> str:
    """Нижний регистр, ё→е, без пунктуации, одиночные пробелы."""
    text = text.lower().replace("ё", "е")
    return " ".join(_NON_WORD.sub(" ", text).split())


def _stem(word: str) -> str:
    """Грубая основа слова: первые 5 букв — хватает, чтобы «классификация» и «классификации» совпали."""
    return word[:5]


def _content_words(text: str, min_len: int = 3) -> list[str]:
    return [w for w in normalize(text).split() if len(w) >= min_len]


def quote_match(
    quote: str, text: str, *, tolerance: float = 0.85, word_share: float = 0.5, min_hits: int = 2
) -> QuoteCheck | None:
    """Есть ли цитата в тексте.

    exact — точное вхождение после нормализации или совпадение ≥ 85 % длины подряд
            (модель поменяла окончание или пропустила слово);
    fuzzy — не меньше половины значимых слов цитаты (от 4 букв, минимум 2 слова) есть
            в тексте с учётом окончаний: модель пересказала фрагмент или процитировала
            формулировку пункта, но по сути опирается на ответ. Порог подобран на первом
            тесте с GigaChat (D-009) — уточнить на бенчмарке;
    None  — цитаты в тексте нет (выдумана).
    """
    q, t = normalize(quote), normalize(text)
    if len(q) < 3 or not t:
        return None
    if q in t:
        return "exact"
    match = SequenceMatcher(None, q, t, autojunk=False).find_longest_match(0, len(q), 0, len(t))
    if match.size >= tolerance * len(q):
        return "exact"
    words = _content_words(quote, min_len=4)
    if len(words) < min_hits:
        return None
    text_stems = {_stem(w) for w in _content_words(text, min_len=4)}
    hits = sum(_stem(w) in text_stems for w in words)
    return "fuzzy" if hits >= min_hits and hits / len(words) >= word_share else None


def quote_is_grounded(quote: str, text: str, **kwargs) -> bool:
    return quote_match(quote, text, **kwargs) is not None


def best_fragment(quote: str, text: str, max_chars: int = 220) -> str:
    """Дословный фрагмент ответа (предложение), лучше всего совпадающий с цитатой модели.

    Нужен для fuzzy-совпадений: в протокол попадают только слова самого человека.
    """
    stems = {_stem(w) for w in _content_words(quote)}
    best, best_score = "", -1.0
    for sentence in (s.strip() for s in _SENTENCE_SPLIT.split(text)):
        words = _content_words(sentence)
        if not words:
            continue
        score = len(stems & {_stem(w) for w in words}) / max(len(stems), 1)
        if score > best_score:
            best, best_score = sentence, score
    best = best.strip(" *#-—•")
    return best if len(best) <= max_chars else best[: max_chars - 1].rstrip() + "…"


def has_forbidden_language(text: str) -> bool:
    return bool(FORBIDDEN.search(text))


def leaks_reference(text: str, reference: str, question: str = "", n: int = 4) -> bool:
    """Есть ли в тексте подряд n слов из эталонного ответа (не подсказывает ли уточнение ответ).

    Сочетания, которые есть в самом вопросе, подсказкой не считаются: уточнение
    естественно повторяет формулировку вопроса.
    """
    words, ref = normalize(text).split(), normalize(reference).split()
    if len(words) < n or len(ref) < n:
        return False

    def shingles(seq: list[str]) -> set[tuple[str, ...]]:
        return {tuple(seq[i : i + n]) for i in range(len(seq) - n + 1)}

    leaked = shingles(ref) - shingles(normalize(question).split())
    return any(s in leaked for s in shingles(words))
