"""LLM-шаг: короткий уточняющий вопрос по недостающим пунктам (или пояснение вопроса).

В промпт уходит только начало ответа (а не весь ответ) — так шаг быстрый даже после
длинного ответа. Если модель не ответила или реплика не прошла проверку (оценки,
пересказ эталона, слишком длинная) — используется запасная фраза без подсказок.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.interview.guardrails import output_is_safe
from app.llm.base import LLMCall, LLMError, LLMProvider, complete_json
from app.llm.prompts import load_prompt, render
from app.schemas.scenario import Question

PROMPT_VERSION = "v3"
MAX_WORDS = 40
EXCERPT_CHARS = 400

FALLBACK = "Можете дополнить ответ? Раскрыто ещё не всё, о чём спрашивает вопрос."


def fallback_text(missing: list[str], *, reveal_topics: bool) -> str:
    """Запасное уточнение. В собеседовании можно назвать, о чём рассказать (это не подсказка ответа);
    в проверке знаний темы пунктов не называем — они часто содержат сам ответ."""
    if reveal_topics and missing:
        topics = " и ".join(m.split(";")[0].strip() for m in missing[:2])
        return f"Уточните, пожалуйста: {topics}?"
    if missing:
        n = len(missing)
        word = "аспект" if n == 1 else "аспекта" if n < 5 else "аспектов"
        return f"Можете дополнить ответ? Пока не раскрыт{'о' if n > 1 else ''} ещё {n} {word} вопроса — перечитайте его формулировку."
    return FALLBACK


class FollowupOutput(BaseModel):
    question: str


def make_followup(
    provider: LLMProvider,
    question: Question,
    answers: list[str],
    missing: list[str],
    *,
    reveal_topics: bool = False,
    log: list[LLMCall] | None = None,
) -> str:
    prompt = load_prompt("followup", PROMPT_VERSION)
    excerpt = " ".join("\n".join(answers).split())[:EXCERPT_CHARS]
    user = render(
        prompt.user,
        question=question.text,
        answer_excerpt=excerpt or "—",
        missing="\n".join(f"- {m}" for m in missing),
    )
    messages = [{"role": "system", "content": prompt.system}, {"role": "user", "content": user}]
    fallback = fallback_text(missing, reveal_topics=reveal_topics)
    try:
        text = complete_json(
            provider,
            messages,
            FollowupOutput,
            purpose="followup",
            prompt_version=prompt.tag,
            log=log,
        ).question.strip()
    except LLMError:
        return fallback
    if len(text.split()) > MAX_WORDS or "?" not in text:
        return fallback
    if not output_is_safe(text, question.reference_answer, question.text):
        return fallback
    return text
