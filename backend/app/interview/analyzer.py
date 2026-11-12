"""LLM-шаг анализа ответа по пунктам проверки (D-004).

Модель для каждого пункта говорит covered / partial / missing и даёт цитату.
Дальше всё решает код: цитата сверяется с ответом (не нашлась — пункт missing),
полнота считается по пунктам. Если модель не ответила — ответ считается полным,
интервью идёт дальше, а вопрос помечается для ручной проверки.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from app.llm.base import LLMCall, LLMError, LLMProvider, complete_json
from app.llm.prompts import load_prompt, render
from app.reporting.validators import quote_is_grounded
from app.schemas.scenario import Question

PROMPT_VERSION = "v2"

Intent = Literal["answer", "dont_know", "question", "off_topic", "stop"]
Status = Literal["covered", "partial", "missing"]
Completeness = Literal["complete", "partial", "empty"]

_RANK = {"missing": 0, "partial": 1, "covered": 2}


class ProbeJudgement(BaseModel):
    id: str
    status: Status
    quote: str | None = None


class AnalyzerOutput(BaseModel):
    intent: Intent
    probes: list[ProbeJudgement] = []


@dataclass
class ProbeResult:
    id: str
    text: str
    status: Status = "missing"
    quote: str | None = None
    # Модель заявила раскрытие, но цитата не нашлась в ответе — пункт сброшен в missing.
    quote_rejected: bool = False


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
        answer=answer_text,
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
    except LLMError as e:
        probes = [ProbeResult(p.id, p.text) for p in question.probes]
        return Analysis("answer", probes, "complete", llm_failed=True, notes=[str(e)])

    by_id = {j.id: j for j in out.probes}
    results: list[ProbeResult] = []
    for probe in question.probes:
        judgement = by_id.get(probe.id)
        result = ProbeResult(probe.id, probe.text)
        if judgement and judgement.status != "missing" and out.intent == "answer":
            if judgement.quote and quote_is_grounded(judgement.quote, answer_text):
                result.status, result.quote = judgement.status, judgement.quote
            else:
                result.quote_rejected = True
        results.append(result)
    return Analysis(out.intent, results, completeness_of(results))
