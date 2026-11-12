"""Детерминированные правила диалога. LLM только сообщает о полноте ответа, решение принимает этот модуль."""

from dataclasses import dataclass
from enum import StrEnum


class NextStep(StrEnum):
    FOLLOWUP = "followup"
    NEXT_QUESTION = "next_question"
    FINALIZE = "finalize"


@dataclass
class PolicyInput:
    completeness: str  # complete | partial | empty
    followups_used: int  # уточнений по текущему вопросу
    max_followups: int  # из вопроса, не больше 2
    question_index: int  # 0-based
    total_questions: int


def decide(p: PolicyInput) -> NextStep:
    if p.completeness != "complete" and p.followups_used < min(p.max_followups, 2):
        return NextStep.FOLLOWUP
    if p.question_index + 1 < p.total_questions:
        return NextStep.NEXT_QUESTION
    return NextStep.FINALIZE
