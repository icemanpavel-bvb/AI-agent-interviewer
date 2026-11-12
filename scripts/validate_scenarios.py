"""Проверка всех сценариев в scenarios/*.json по схеме backend/app/schemas/scenario.py.

Запуск из корня репозитория:
    python scripts/validate_scenarios.py            # все сценарии
    python scripts/validate_scenarios.py ml_junior  # один

Код выхода 1, если хотя бы один сценарий не прошёл проверку (удобно для CI).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from pydantic import ValidationError  # noqa: E402

from app.schemas.scenario import Scenario  # noqa: E402


def main(names: list[str]) -> int:
    files = sorted((ROOT / "scenarios").glob("*.json"))
    if names:
        files = [f for f in files if f.stem in names]
    failed = 0
    for path in files:
        try:
            sc = Scenario.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as e:
            failed += 1
            print(f"✗ {path.name}\n{e}\n")
            continue
        q = sc.ordered_questions()
        probes = sum(len(x.probes) for x in q)
        practice = [c.id for c in sc.criteria if c.requires_practice]
        todo = "  ⚠ есть «ЗАПОЛНИТЬ»" if "ЗАПОЛНИТЬ" in path.read_text(encoding="utf-8") else ""
        print(
            f"✓ {path.name:22} {sc.status:5} {sc.kind:15} {sc.level:7} "
            f"вопросов {len(q):2}, критериев {len(sc.criteria)}, пунктов {probes:2}, "
            f"практика {practice or '—'}{todo}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
