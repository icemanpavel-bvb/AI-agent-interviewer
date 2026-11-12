"""Переходы статусов заявки, решения рекрутера, «Отложить на N дней», аудит."""

from app.models.enums import ApplicationStatus as S

# Единственная таблица допустимых переходов (см. docs/diagrams/03_application_status.svg).
# Переходы в APPROVED / REJECTED / POSTPONED / RESUME_REJECTED выполняются только по действию рекрутера.
ALLOWED: dict[S, set[S]] = {
    S.NEW: {S.INVITED, S.RESUME_REJECTED},
    S.INVITED: {S.IN_PROGRESS, S.CONSENT_DECLINED, S.EXPIRED},
    S.IN_PROGRESS: {S.REPORT_READY, S.EXPIRED},
    S.REPORT_READY: {S.UNDER_REVIEW},
    S.UNDER_REVIEW: {S.APPROVED, S.REJECTED, S.POSTPONED},
    S.POSTPONED: {S.UNDER_REVIEW},
}


class InvalidTransition(Exception):
    pass


def check_transition(current: S, new: S) -> None:
    if new not in ALLOWED.get(current, set()):
        raise InvalidTransition(f"{current} -> {new} запрещён")
