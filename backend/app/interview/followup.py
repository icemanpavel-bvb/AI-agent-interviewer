"""LLM-шаг: короткий уточняющий вопрос по недостающим пунктам (или пояснение вопроса).

В промпт уходит только начало ответа (а не весь ответ) — так шаг быстрый даже после
длинного ответа. Если модель не ответила или реплика не прошла проверку (оценки,
пересказ эталона, слишком длинная) — используется запасная фраза без подсказок.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.interview.guardrails import output_is_safe
from app.llm.base import LLMCall, LLMError, LLMProvider, complete_json
from app.llm.prompts import load_prompt, render
from app.schemas.scenario import Question

PROMPT_VERSION = "v4"
MAX_WORDS = 40
EXCERPT_CHARS = 400

FALLBACK = "Можете дополнить ответ? Раскрыто ещё не всё, о чём спрашивает вопрос."

# Правила для двух режимов (D-010): в проверке знаний нельзя называть недостающий факт —
# это подсказка; в собеседовании «правильного ответа» нет, тему можно назвать прямо.
MODE_RULES = {
    "knowledge": (
        "- Это проверка знаний. НЕ называй недостающий факт, термин или формулу — иначе ты подскажешь "
        "ответ. Спроси, как человек понимает этот аспект темы.\n"
        "  Плохо: «Упомянуто ли в ответе, что кросс-валидация делит данные на k частей?» — подсказка "
        "и третье лицо.\n"
        "  Плохо: «Вы знаете, что итоговая оценка — это произведение двух величин?» — подсказка.\n"
        "  Хорошо: «Как именно при кросс-валидации данные используются для обучения и проверки?»"
    ),
    "interview": (
        "- Это собеседование: можно прямо назвать, о чём рассказать подробнее "
        "(сроки, роль, инструменты, результат).\n"
        "  Плохо: «Упомянуто ли в ответе, какую роль вы играли в проекте?» — третье лицо.\n"
        "  Хорошо: «Расскажите, пожалуйста, что в этом проекте вы делали лично и каким был результат?»"
    ),
}

# Реплика о человеке в третьем лице вместо вопроса к нему.
_THIRD_PERSON = re.compile(r"^\s*(упомянут\w*|указан\w*|есть ли в ответе|в ответе)", re.IGNORECASE)


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
    system = render(
        prompt.system, mode_rules=MODE_RULES["interview" if reveal_topics else "knowledge"]
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
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
    if len(text.split()) > MAX_WORDS or "?" not in text or _THIRD_PERSON.match(text):
        return fallback
    if not output_is_safe(text, question.reference_answer, question.text):
        return fallback
    return text
