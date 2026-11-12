"""Сценарии вакансий: все файлы валидны, recruiter_only не попадает в модель."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.scenario import Scenario

SCENARIOS = sorted((Path(__file__).resolve().parents[3] / "scenarios").glob("*.json"))


def _load(path: Path) -> Scenario:
    return Scenario.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_is_valid(path):
    _load(path)


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_llm_view_has_no_recruiter_only(path):
    view = json.dumps(_load(path).llm_view(), ensure_ascii=False)
    assert "recruiter_only" not in view
    assert "rubric" not in view


def test_ready_scenarios_weights_sum_to_100():
    for path in SCENARIOS:
        sc = _load(path)
        if sc.status == "ready" and sc.kind == "job_interview":
            assert sum(c.weight for c in sc.criteria) == 100, path.name


def test_too_many_followups_rejected():
    data = json.loads(SCENARIOS[0].read_text(encoding="utf-8"))
    data["questions"][0]["max_followups"] = 3
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)


def test_unknown_criterion_rejected():
    data = json.loads(SCENARIOS[0].read_text(encoding="utf-8"))
    data["questions"][1]["criteria"] = ["NO_SUCH"]
    with pytest.raises(ValidationError):
        Scenario.model_validate(data)
