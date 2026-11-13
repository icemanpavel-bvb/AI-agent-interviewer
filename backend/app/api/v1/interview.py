"""Чат кандидата по токену: состояние, ответ, досрочное завершение, протокол.

Сейчас сессии берутся из хранилища в памяти (создаёт их демо-страница). На этапе 2 токен
будет приходить из приглашения рекрутера, а состояние — сохраняться в БД; контракт API тот же.

Эндпоинты синхронные: вызов модели блокирующий, FastAPI выполняет их в пуле потоков.
"""

from fastapi import APIRouter, HTTPException

from app.api.deps import RegistryDep, StoreDep
from app.interview.store import SessionEntry, SessionStore
from app.llm.base import LLMUnavailable
from app.llm.registry import ModelRegistry
from app.reporting.protocol import build_protocol
from app.schemas.interview import (
    DebugOut,
    LLMCallOut,
    MessageOut,
    ProbeOut,
    ScenarioBrief,
    SendIn,
    SessionOut,
)

router = APIRouter()


def _entry(
    token: str, sessions: SessionStore, registry: ModelRegistry | None = None
) -> SessionEntry:
    entry = sessions.get(token)
    if entry is None:
        raise HTTPException(
            404,
            "Сессия не найдена: прошло больше 6 часов без активности или данные сервера очищены",
        )
    if registry is not None:
        # Модель берётся по имени при каждом ходе: сессия могла загрузиться с диска,
        # а ключ в llm_keys.json — поменяться. Нет модели — LLMUnavailable (503).
        entry.runner.provider = registry.get(getattr(entry.runner, "model_id", "local"))
    return entry


def session_out(entry: SessionEntry) -> SessionOut:
    r = entry.runner
    numbers = {q.id: i + 1 for i, q in enumerate(r.plan)}
    messages = [
        MessageOut(
            role=t.role,
            kind=t.kind,
            text=t.text,
            question_id=t.question_id,
            question_number=numbers.get(t.question_id) if t.question_id else None,
            at=t.at,
        )
        for t in r.transcript
    ]

    debug = None
    last_answer = next((t for t in reversed(r.transcript) if t.role == "candidate"), None)
    if last_answer and last_answer.question_id in numbers:
        idx = numbers[last_answer.question_id] - 1
        st = r.states[idx]
        debug = DebugOut(
            question_id=st.question.id,
            question_number=idx + 1,
            completeness=st.completeness,
            followups=st.followups,
            max_followups=st.question.max_followups,
            probes=[
                ProbeOut(
                    id=p.id,
                    text=p.text,
                    status=p.status,
                    quote=p.quote,
                    model_status=p.model_status,
                    model_quote=p.model_quote,
                    quote_check=p.quote_check,
                )
                for p in st.probes
            ],
            last_calls=[
                LLMCallOut(
                    purpose=c.purpose,
                    latency_ms=c.latency_ms,
                    valid_json=c.valid_json,
                    attempts=c.attempts,
                )
                for c in r.llm_log[-2:]
            ],
        )

    sc = r.scenario
    return SessionOut(
        token=entry.token,
        model=getattr(r, "model_label", ""),
        model_local=getattr(r, "model_id", "local") == "local",
        scenario=ScenarioBrief(id=sc.id, title=sc.title, kind=sc.kind, level=sc.level),
        question_number=min(r.index + 1, len(r.plan)),
        total_questions=len(r.plan),
        finished=r.finished,
        stopped=r.stopped,
        messages=messages,
        debug=debug,
    )


@router.get("/{token}", response_model=SessionOut)
def get_session(token: str, sessions: StoreDep) -> SessionOut:
    return session_out(_entry(token, sessions))


@router.post("/{token}/messages", response_model=SessionOut)
def send_message(token: str, body: SendIn, sessions: StoreDep, registry: RegistryDep) -> SessionOut:
    try:
        entry = _entry(token, sessions, registry)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e)) from e
    if not entry.lock.acquire(blocking=False):
        raise HTTPException(409, "Предыдущий ответ ещё обрабатывается")
    try:
        if entry.runner.finished:
            raise HTTPException(409, "Сессия уже завершена")
        try:
            entry.runner.handle(body.text)
        except LLMUnavailable as e:
            raise HTTPException(
                503, f"Модель недоступна, ответ не засчитан — отправьте его ещё раз. {e}"
            ) from e
        sessions.save(entry)
        return session_out(entry)
    finally:
        entry.lock.release()


@router.post("/{token}/stop", response_model=SessionOut)
def stop(token: str, sessions: StoreDep) -> SessionOut:
    entry = _entry(token, sessions)
    with entry.lock:
        entry.runner.stop()
        sessions.save(entry)
    return session_out(entry)


@router.get("/{token}/protocol")
def protocol(token: str, sessions: StoreDep) -> dict:
    entry = _entry(token, sessions)
    result = build_protocol(entry.runner)
    sc = entry.runner.scenario
    if sc.kind == "knowledge_check":
        # Эталоны показываем только в проверке знаний — для повторения материала.
        result["references"] = {q.id: q.reference_answer for q in sc.questions}
    return result
