"""Протокол сессии из проверенных результатов анализа (без LLM).

Для каждого вопроса — пункты со статусами и цитатами; для каждого критерия (темы) — сводка.
Баллов нет: статус означает наличие информации в ответах, а не оценку человека.
Критерии с requires_practice всегда unknown: рассказ в чате не заменяет практику.
"""

from __future__ import annotations

from dataclasses import asdict

from app.interview.runner import InterviewRunner

LABELS = {
    "knowledge_check": {
        "covered": "тема раскрыта",
        "partial": "раскрыта частично",
        "missing": "не раскрыта",
    },
    "job_interview": {
        "covered": "подтверждено ответами",
        "partial": "частично",
        "missing": "нет информации",
        "unknown": "нужна практическая проверка",
    },
}


def build_protocol(runner: InterviewRunner) -> dict:
    sc = runner.scenario
    questions = []
    for i, st in enumerate(runner.states):
        asked = i < runner.index or (i == runner.index and bool(st.answers or st.ended_by))
        questions.append(
            {
                "id": st.question.id,
                "text": st.question.text,
                "criteria": st.question.criteria,
                "asked": asked,
                "answers": st.answers,
                "followups": st.followups,
                "ended_by": st.ended_by or ("not_asked" if not asked else ""),
                "completeness": st.completeness,
                "needs_manual_check": st.llm_failed,
                "flags": st.flags,
                "probes": [
                    {
                        "id": p.id,
                        "text": p.text,
                        "status": p.status,
                        "quote": p.quote,
                        "quote_check": p.quote_check,
                    }
                    for p in st.probes
                ],
            }
        )

    criteria = []
    for c in sc.criteria:
        related = [q for q in questions if c.id in q["criteria"] and q["asked"]]
        if not related:
            continue
        if c.requires_practice:
            status = "unknown"
        else:
            statuses = [p["status"] for q in related for p in q["probes"]]
            if statuses and all(s == "covered" for s in statuses):
                status = "covered"
            elif any(s != "missing" for s in statuses):
                status = "partial"
            else:
                status = "missing"
        criteria.append(
            {
                "id": c.id,
                "name": c.name,
                "status": status,
                "label": LABELS[sc.kind].get(status, status),
                "questions": [q["id"] for q in related],
            }
        )

    calls = runner.llm_log
    return {
        "scenario": {"id": sc.id, "title": sc.title, "kind": sc.kind, "level": sc.level},
        "started_at": runner.started_at,
        "finished_at": runner.finished_at,
        "stopped_early": runner.stopped,
        "criteria": criteria,
        "questions": questions,
        "transcript": [asdict(t) for t in runner.transcript],
        "llm": {
            "model": getattr(runner.provider, "model", "?"),
            "calls": len(calls),
            "invalid_json": sum(1 for c in calls if not c.valid_json),
            "avg_latency_ms": int(sum(c.latency_ms for c in calls) / len(calls)) if calls else 0,
            "max_latency_ms": max((c.latency_ms for c in calls), default=0),
            "log": [asdict(c) for c in calls],
        },
    }
