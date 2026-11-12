"""Интервью в терминале с локальной моделью через Ollama.

Примеры (из папки backend):
    python -m app.cli --list
    python -m app.cli student_course                  # 10 случайных вопросов по NLP
    python -m app.cli student_course --topic T03      # тренировка по теме Word2Vec
    python -m app.cli ml_junior --verbose             # собеседование + время каждого вызова модели

Протокол сохраняется в storage/cli_sessions/*.json (папка в .gitignore) — пригодится для бенчмарка.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from app.interview.runner import InterviewRunner
from app.llm.base import LLMError
from app.llm.ollama import OllamaProvider
from app.reporting.protocol import build_protocol
from app.scenarios import DEFAULT_DIR, list_scenarios, load_scenario

with contextlib.suppress(ImportError):
    import readline  # noqa: F401  — стрелки и редактирование строки в input()

ROOT = Path(__file__).resolve().parents[3]
MARK = {"covered": "✓", "partial": "~", "missing": "✗", "unknown": "?"}
DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    if args.list or not args.scenario:
        _print_list(args.scenarios_dir)
        return 0

    scenario = load_scenario(args.scenario, args.scenarios_dir)
    if args.size and scenario.session:
        scenario.session.size = args.size
    provider = OllamaProvider(args.model, args.url)

    print(f"{DIM}Модель {provider.model} на {provider.url}: прогрев...{RESET}", flush=True)
    t0 = time.monotonic()
    try:
        provider.warmup()
    except LLMError as e:
        print(f"Не удалось обратиться к модели: {e}\nПроверьте, что Ollama запущена: ollama list")
        return 1
    print(f"{DIM}готово за {time.monotonic() - t0:.1f} с{RESET}\n")

    rng = random.Random(args.seed) if args.seed is not None else None
    runner = InterviewRunner(scenario, provider, rng=rng, topic=args.topic)
    _assistant(runner.start().text)

    while not runner.finished:
        try:
            text = input(f"\n{BOLD}Вы:{RESET} ")
        except (EOFError, KeyboardInterrupt):
            print()
            _assistant(runner.stop().text)
            break
        calls_before = len(runner.llm_log)
        t0 = time.monotonic()
        reply = runner.handle(text)
        if args.verbose:
            calls = runner.llm_log[calls_before:]
            detail = ", ".join(
                f"{c.purpose} {c.latency_ms / 1000:.1f} с" + ("" if c.valid_json else " ✗json")
                for c in calls
            )
            print(f"{DIM}[{time.monotonic() - t0:.1f} с: {detail or 'без модели'}]{RESET}")
        _assistant(reply.text)

    protocol = build_protocol(runner)
    _print_protocol(protocol, scenario, show_reference=not args.no_reference)
    path = _save(protocol, args.out_dir)
    print(f"\n{DIM}Протокол сохранён: {path}{RESET}")
    return 0


def _parse(argv):
    p = argparse.ArgumentParser(prog="python -m app.cli", description="Интервью в терминале")
    p.add_argument("scenario", nargs="?", help="id сценария (python -m app.cli --list)")
    p.add_argument("--list", action="store_true", help="показать сценарии")
    p.add_argument("--topic", help="тренировка по одной теме (id критерия, например T03)")
    p.add_argument("--size", type=int, help="сколько вопросов в сессии (проверка знаний)")
    p.add_argument("--seed", type=int, help="зафиксировать случайный выбор вопросов")
    p.add_argument("--model", help="модель Ollama (по умолчанию LLM_MODEL или gigachat-lightning)")
    p.add_argument("--url", help="адрес Ollama (по умолчанию OLLAMA_URL или localhost:11434)")
    p.add_argument("--verbose", action="store_true", help="время каждого вызова модели")
    p.add_argument("--no-reference", action="store_true", help="не показывать эталоны в конце")
    p.add_argument("--scenarios-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--out-dir", type=Path, default=ROOT / "storage" / "cli_sessions")
    return p.parse_args(argv)


def _assistant(text: str) -> None:
    print(f"\n{BOLD}Ассистент:{RESET} {text}")


def _print_list(directory: Path) -> None:
    print("Сценарии:\n")
    for sc in list_scenarios(directory):
        kind = "проверка знаний" if sc.kind == "knowledge_check" else "собеседование"
        size = (
            f", в сессии {sc.session.size}" if sc.session and sc.kind == "knowledge_check" else ""
        )
        print(
            f"  {sc.id:16} {sc.title}\n  {'':16} {kind}, вопросов {len(sc.questions)}{size}, {sc.status}"
        )
        if sc.session and sc.session.allow_topic_choice:
            topics = ", ".join(f"{c.id} {c.name}" for c in sc.criteria)
            print(f"  {'':16} темы для --topic: {topics}")
        print()


def _print_protocol(protocol: dict, scenario, *, show_reference: bool) -> None:
    print(f"\n{BOLD}{'=' * 20} Протокол {'=' * 20}{RESET}")
    print(f"\n{BOLD}По {'темам' if scenario.kind == 'knowledge_check' else 'критериям'}:{RESET}")
    for c in protocol["criteria"]:
        print(f"  {MARK.get(c['status'], '?')} {c['id']} {c['name']} — {c['label']}")

    print(f"\n{BOLD}По вопросам:{RESET}")
    references = {q.id: q.reference_answer for q in scenario.questions}
    for q in protocol["questions"]:
        if not q["asked"]:
            continue
        extra = f", уточнений {q['followups']}" if q["followups"] else ""
        flag = " ⚠ проверить вручную (модель не ответила)" if q["needs_manual_check"] else ""
        print(f"\n  {q['id']}. {q['text']}\n  {DIM}[{q['ended_by']}{extra}]{RESET}{flag}")
        for p in q["probes"]:
            quote = f" — «{p['quote']}»" if p["quote"] else ""
            print(f"    {MARK[p['status']]} {p['text']}{DIM}{quote}{RESET}")
        if (
            show_reference
            and scenario.kind == "knowledge_check"
            and q["completeness"] != "complete"
            and references.get(q["id"])
        ):
            print(f"    {DIM}Эталон для повторения: {references[q['id']]}{RESET}")

    llm = protocol["llm"]
    print(
        f"\n{DIM}Модель: вызовов {llm['calls']}, среднее {llm['avg_latency_ms'] / 1000:.1f} с, "
        f"максимум {llm['max_latency_ms'] / 1000:.1f} с, невалидный JSON {llm['invalid_json']}{RESET}"
    )


def _save(protocol: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{stamp}_{protocol['scenario']['id']}.json"
    path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.exit(main())
