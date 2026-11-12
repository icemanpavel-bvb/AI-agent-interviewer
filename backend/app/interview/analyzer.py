"""LLM-шаг анализа ответа по пунктам проверки (D-004).

Модель для каждого пункта говорит covered / partial / missing и даёт цитату.
Дальше всё решает код: цитата сверяется с ответом (exact — дословно, fuzzy — по словам
с учётом окончаний, тогда в протокол идёт дословный фрагмент ответа; не нашлась —
пункт missing), полнота считается по пунктам. Если модель вернула мусор — ответ
считается полным, интервью идёт дальше, а вопрос помечается для ручной проверки.
Если модель недоступна (LLMUnavailable) — исключение пробрасывается: ход не засчитывается.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.llm.base import LLMCall, LLMError, LLMProvider, LLMUnavailable, complete_json
from app.llm.prompts import load_prompt, render
from app.reporting.validators import best_fragment, quote_match
from app.schemas.scenario import Question

PROMPT_VERSION = "v4"
# Сколько символов ответов на один вопрос уходит в модель: контекст 4096 токенов,
# из них ~1800 занимают служебный блок, инструкция, вопрос и пункты, ~400 — ответ модели.
MAX_ANSWER_CHARS_FOR_MODEL = 5000
# Длина цитаты: ограничение уходит в JSON-схему (Ollama не даст модели написать длиннее),
# иначе модель копирует абзацы целиком и упирается в num_predict — JSON обрывается (D-011).
MAX_QUOTE_CHARS = 160
# Сообщение длиннее стольких слов — развёрнутый ответ, а не вопрос/просьба пояснить (D-011).
LONG_ANSWER_WORDS = 40

Intent = Literal["answer", "clarify", "dont_know", "question", "off_topic", "stop"]
Status = Literal["covered", "partial", "missing"]
Completeness = Literal["complete", "partial", "empty"]

_RANK = {"missing": 0, "partial": 1, "covered": 2}


class ProbeJudgement(BaseModel):
    id: str
    status: Status
    # maxLength уходит в JSON-схему на ветку string; длинное (если схема не сработала) — обрезаем.
    quote: Annotated[str, Field(max_length=MAX_QUOTE_CHARS)] | None = None

    @field_validator("quote", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        return v[:MAX_QUOTE_CHARS] if isinstance(v, str) else v


class AnalyzerOutput(BaseModel):
    intent: Intent
    probes: list[ProbeJudgement] = []


@dataclass
class ProbeResult:
    id: str
    text: str
    status: Status = "missing"
    quote: str | None = None  # всегда дословный фрагмент ответа человека
    # Что сказала модель до проверки кодом — для отладки.
    model_status: str | None = None
    model_quote: str | None = None
    # exact / fuzzy — как подтвердилась цитата; rejected — не нашлась, пункт сброшен в missing.
    quote_check: str = ""


@dataclass
class Analysis:
    intent: Intent
    probes: list[ProbeResult]
    completeness: Completeness
    llm_failed: bool = False
    notes: list[str] = field(default_factory=list)


def completeness_of(probes: list[ProbeResult]) -> Completeness:
    if probes and all(p.status == "covered" for p in probes):
        return "complete"
    if any(p.status != "missing" for p in probes):
        return "partial"
    return "empty"


def merge_best(previous: list[ProbeResult], current: list[ProbeResult]) -> list[ProbeResult]:
    """Пункт, раскрытый в прошлом ответе на этот же вопрос, не теряется при следующем анализе."""
    prev = {p.id: p for p in previous}
    merged = []
    for cur in current:
        old = prev.get(cur.id)
        merged.append(old if old and _RANK[old.status] > _RANK[cur.status] else cur)
    return merged


def fit_answers(answers: list[str], limit: int = MAX_ANSWER_CHARS_FOR_MODEL) -> str:
    """Склеивает ответы на вопрос; если длинно — укорачивает первый (самый длинный) ответ с конца."""
    if sum(len(a) for a in answers) + len(answers) <= limit or not answers:
        return "\n".join(answers)
    rest = "\n".join(answers[1:])
    marker = " […]"
    room = max(limit - len(rest) - 1 - len(marker), 1000)
    first = answers[0][:room].rstrip() + marker
    return "\n".join([first, rest]) if rest else first


def analyze_answer(
    provider: LLMProvider,
    question: Question,
    answers: list[str],
    *,
    log: list[LLMCall] | None = None,
) -> Analysis:
    prompt = load_prompt("analyze_answer", PROMPT_VERSION)
    answer_text = "\n".join(answers)
    user = render(
        prompt.user,
        question=question.text,
        probes="\n".join(f"- {p.id}: {p.text}" for p in question.probes),
        reference=question.reference_answer or "—",
        answer=fit_answers(answers),
        last_message=(answers[-1][:300] if answers else ""),
    )
    messages = [{"role": "system", "content": prompt.system}, {"role": "user", "content": user}]
    try:
        out = complete_json(
            provider,
            messages,
            AnalyzerOutput,
            purpose="analyze_answer",
            prompt_version=prompt.tag,
            log=log,
        )
    except LLMUnavailable:
        raise  # модель недоступна: ход не засчитываем, его нужно повторить
    except LLMError as e:
        probes = [ProbeResult(p.id, p.text) for p in question.probes]
        return Analysis("answer", probes, "complete", llm_failed=True, notes=[str(e)])

    intent = out.intent
    if intent != "answer" and answers and len(answers[-1].split()) >= LONG_ANSWER_WORDS:
        intent = "answer"  # длинный текст по теме модель иногда принимает за вопрос

    by_id = {j.id: j for j in out.probes}
    results: list[ProbeResult] = []
    for probe in question.probes:
        judgement = by_id.get(probe.id)
        result = ProbeResult(probe.id, probe.text)
        if judgement:
            result.model_status, result.model_quote = judgement.status, judgement.quote
        if judgement and judgement.status != "missing" and intent == "answer":
            check = quote_match(judgement.quote, answer_text) if judgement.quote else None
            if check:
                result.status = judgement.status
                result.quote_check = check
                result.quote = (
                    judgement.quote
                    if check == "exact"
                    else best_fragment(judgement.quote, answer_text)
                )
            else:
                result.quote_check = "rejected"
        results.append(result)
    return Analysis(intent, results, completeness_of(results))
