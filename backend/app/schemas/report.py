"""Схема протокола (см. ARCHITECTURE.md §6). Полей с баллами и вердиктами нет намеренно."""

from typing import Literal

from pydantic import BaseModel


class Evidence(BaseModel):
    message_id: int
    quote: str


class CriterionCoverage(BaseModel):
    criterion: str
    # Есть ли в ответе ИНФОРМАЦИЯ по критерию. Это не оценка кандидата.
    status: Literal["mentioned", "partially_mentioned", "not_mentioned"]
    evidence: list[Evidence] = []


class ReportItem(BaseModel):
    question_id: str
    question: str
    criteria: list[str]
    answer_summary: str
    criteria_coverage: list[CriterionCoverage]
    followups_asked: int
    needs_manual_check: bool = False


class ReportContent(BaseModel):
    schema_version: str = "1.0"
    application_id: str
    vacancy: str
    generated: dict
    items: list[ReportItem]
    dialog_meta: dict
