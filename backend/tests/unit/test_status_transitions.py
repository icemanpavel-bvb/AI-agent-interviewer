"""Таблица переходов статусов."""

import pytest

from app.models.enums import ApplicationStatus as S
from app.services.application_service import InvalidTransition, check_transition


def test_system_cannot_skip_review():
    with pytest.raises(InvalidTransition):
        check_transition(S.REPORT_READY, S.APPROVED)
