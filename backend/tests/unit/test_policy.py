"""Policy: лимит уточнений и порядок вопросов."""

from app.interview.policy import NextStep, PolicyInput, decide


def test_followup_when_partial_and_limit_not_reached():
    assert decide(PolicyInput("partial", 0, 2, 0, 5)) == NextStep.FOLLOWUP


def test_no_more_than_two_followups():
    assert decide(PolicyInput("partial", 2, 2, 0, 5)) == NextStep.NEXT_QUESTION


def test_finalize_after_last_question():
    assert decide(PolicyInput("complete", 0, 2, 4, 5)) == NextStep.FINALIZE
