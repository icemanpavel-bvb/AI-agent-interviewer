"""Перечисления домена: статусы заявки и сессии, типы сообщений, действия рекрутера."""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    NEW = "NEW"
    RESUME_REJECTED = "RESUME_REJECTED"
    INVITED = "INVITED"
    CONSENT_DECLINED = "CONSENT_DECLINED"
    IN_PROGRESS = "IN_PROGRESS"
    EXPIRED = "EXPIRED"
    REPORT_READY = "REPORT_READY"
    UNDER_REVIEW = "UNDER_REVIEW"
    POSTPONED = "POSTPONED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SessionState(StrEnum):
    AWAIT_CONSENT = "AWAIT_CONSENT"
    AWAIT_ANSWER = "AWAIT_ANSWER"
    FINISHED = "FINISHED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class MessageRole(StrEnum):
    ASSISTANT = "assistant"
    CANDIDATE = "candidate"
    SYSTEM = "system"


class MessageKind(StrEnum):
    CONSENT = "consent"
    BASE_QUESTION = "base_question"
    FOLLOWUP = "followup"
    ANSWER = "answer"
    CANDIDATE_QUESTION = "candidate_question"
    SYSTEM = "system"


class DecisionAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    POSTPONE = "postpone"
