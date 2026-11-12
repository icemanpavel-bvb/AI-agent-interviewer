"""LLM-шаг: короткий уточняющий вопрос по недостающим пунктам.

Если модель не ответила или реплика не прошла проверку (оценки, пересказ эталона,
слишком длинная) — используется нейтральная фраза без подсказок.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.interview.guardrails import output_is_safe
from app.llm.base import LLMCall, LLMError, LLMProvider, complete_json
from app.llm.prompts import load_prompt, render
from app.schemas.scenario import Question

PROMPT_VERSION = "v2"
MAX_WORDS = 40

FALLBACK = "Можете дополнить ответ? Раскрыто ещё не всё, о чём спрашивает вопрос."


class FollowupOutput(BaseModel):
    question: str


def make_followup(
    provider: LLMProvider,
    question: Question,
    answers: list[str],
    missing: list[str],
    *,
    log: list[LLMCall] | None = None,
) -> str:
    prompt = load_prompt("followup", PROMPT_VERSION)
    user = render(
        prompt.user,
        question=question.text,
        answer="\n".join(answers),
        missing="\n".join(f"- {m}" for m in missing),
    )
    messages = [{"role": "system", "content": prompt.system}, {"role": "user", "content": user}]
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
        return FALLBACK
    if len(text.split()) > MAX_WORDS or "?" not in text:
        return FALLBACK
    if not output_is_safe(text, question.reference_answer):
        return FALLBACK
    return text
