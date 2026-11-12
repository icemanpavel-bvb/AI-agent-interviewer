"""Промпты лежат в .md-файлах рядом с кодом и версионируются в имени: analyze_answer.v2.md.

Формат файла: блоки, начинающиеся строками `<<<system>>>` и `<<<user>>>`.
Подстановка — `{{имя}}` (одинарные фигурные скобки в JSON-примерах не трогаются).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PROMPT_DIRS = [APP_DIR / "interview" / "prompts", APP_DIR / "reporting" / "prompts"]


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str

    @property
    def tag(self) -> str:
        return f"{self.name}.{self.version}"


@cache
def load_prompt(name: str, version: str) -> Prompt:
    filename = f"{name}.{version}.md"
    for directory in PROMPT_DIRS:
        path = directory / filename
        if path.exists():
            return _parse(name, version, path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"промпт {filename} не найден в {[str(d) for d in PROMPT_DIRS]}")


def _parse(name: str, version: str, text: str) -> Prompt:
    if "<<<system>>>" not in text or "<<<user>>>" not in text:
        raise ValueError(f"{name}.{version}: нужны блоки <<<system>>> и <<<user>>>")
    _, rest = text.split("<<<system>>>", 1)
    system, user = rest.split("<<<user>>>", 1)
    return Prompt(name, version, system.strip(), user.strip())


def render(template: str, **values: object) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template
