"""Демо-режим для тестов и защиты: список сценариев и запуск сессии без рекрутера (D-005).

Работает только при DEMO_MODE=true. Сессии хранятся в памяти (app/interview/store.py).
"""

import random

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import RegistryDep, StoreDep, require_demo
from app.api.v1.interview import session_out
from app.interview.runner import InterviewRunner
from app.llm.base import LLMUnavailable
from app.scenarios import list_scenarios, load_scenario
from app.schemas.interview import (
    HealthOut,
    ModelOut,
    ScenarioCard,
    SessionOut,
    StartDemoIn,
    TopicOut,
)

router = APIRouter(dependencies=[Depends(require_demo)])


@router.get("/models", response_model=list[ModelOut])
def models(registry: RegistryDep) -> list[ModelOut]:
    """Локальная модель и облачные из llm_keys.json — только имена, без ключей (D-013)."""
    return [ModelOut(**m.__dict__) for m in registry.list()]


@router.get("/health", response_model=HealthOut)
def health(registry: RegistryDep, model: str | None = None) -> HealthOut:
    try:
        provider = registry.get(model)
    except LLMUnavailable as e:
        return HealthOut(ok=False, model=model or "", url="", message=str(e))
    ping = getattr(provider, "ping", None)
    ok, message = ping() if ping else (True, "ok")
    name = model if model and model != "local" else provider.model
    return HealthOut(ok=ok, model=name, url=getattr(provider, "url", ""), message=message)


@router.get("/scenarios", response_model=list[ScenarioCard])
def scenarios() -> list[ScenarioCard]:
    cards = []
    for sc in list_scenarios():
        is_bank = sc.kind == "knowledge_check" and sc.session is not None
        topics = []
        if sc.session and sc.session.allow_topic_choice:
            topics = [
                TopicOut(
                    id=c.id, name=c.name, questions=sum(c.id in q.criteria for q in sc.questions)
                )
                for c in sc.criteria
            ]
        cards.append(
            ScenarioCard(
                id=sc.id,
                title=sc.title,
                kind=sc.kind,
                level=sc.level,
                status=sc.status,
                tags=sc.tags,
                description=sc.description,
                questions_total=len(sc.questions),
                session_size=min(sc.session.size, len(sc.questions))
                if is_bank
                else len(sc.questions),
                topics=topics,
            )
        )
    return cards


@router.post("/start", response_model=SessionOut, status_code=201)
def start(
    body: StartDemoIn,
    registry: RegistryDep,
    sessions: StoreDep,
) -> SessionOut:
    if not registry.has(body.model):
        raise HTTPException(400, f"Модель «{body.model}» не найдена в llm_keys.json")
    model_id = body.model or "local"
    try:
        provider = registry.get(model_id)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e)) from e
    try:
        scenario = load_scenario(body.scenario_id)
    except FileNotFoundError as e:
        raise HTTPException(404, f"Сценарий {body.scenario_id} не найден") from e
    if body.size and scenario.session and scenario.kind == "knowledge_check":
        scenario = scenario.model_copy(deep=True)
        scenario.session.size = body.size
    rng = random.Random(body.seed) if body.seed is not None else None
    try:
        runner = InterviewRunner(scenario, provider, rng=rng, topic=body.topic, model_id=model_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    runner.start()
    return session_out(sessions.create(runner))
