"""Загрузка сценариев вакансий из scenarios/*.json (корень репозитория)."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.scenario import Scenario

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "scenarios"


def load_scenario(scenario_id: str, directory: Path | None = None) -> Scenario:
    path = (directory or DEFAULT_DIR) / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"сценарий {scenario_id} не найден: {path}")
    return Scenario.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_scenarios(directory: Path | None = None) -> list[Scenario]:
    return [
        load_scenario(p.stem, directory) for p in sorted((directory or DEFAULT_DIR).glob("*.json"))
    ]
