"""План вопросов на сессию: собеседование — все по порядку, проверка знаний — выборка по темам."""

import json
import random
from pathlib import Path

import pytest

from app.interview.question_plan import plan_questions
from app.schemas.scenario import Scenario

ROOT = Path(__file__).resolve().parents[3] / "scenarios"


def load(name: str) -> Scenario:
    return Scenario.model_validate(json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8")))


def test_job_interview_asks_all_in_order():
    sc = load("ml_junior")
    assert [q.id for q in plan_questions(sc)] == [q.id for q in sc.ordered_questions()]


def test_knowledge_check_covers_all_topics():
    sc = load("student_course")
    topics = {c.id for c in sc.criteria}
    for seed in range(20):
        plan = plan_questions(sc, random.Random(seed))
        assert len(plan) == sc.session.size
        assert len({q.id for q in plan}) == len(plan)
        if sc.session.size >= len(topics):
            assert {q.criteria[0] for q in plan} == topics


def test_knowledge_check_is_random_but_reproducible():
    sc = load("student_course")
    a = [q.id for q in plan_questions(sc, random.Random(1))]
    b = [q.id for q in plan_questions(sc, random.Random(1))]
    c = [q.id for q in plan_questions(sc, random.Random(2))]
    assert a == b
    assert a != c


def test_topic_training_returns_all_topic_questions():
    sc = load("student_course")
    plan = plan_questions(sc, topic="T02")
    assert plan and all("T02" in q.criteria for q in plan)
    assert len(plan) == sum(1 for q in sc.questions if "T02" in q.criteria)


def test_topic_choice_not_allowed_in_job_interview():
    with pytest.raises(ValueError):
        plan_questions(load("ml_junior"), topic="J01")
