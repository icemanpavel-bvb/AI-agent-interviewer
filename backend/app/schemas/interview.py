"""Схемы API чата и демо-страницы."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopicOut(BaseModel):
    id: str
    name: str
    questions: int


class ScenarioCard(BaseModel):
    id: str
    title: str
    kind: str
    level: str
    status: str
    tags: list[str]
    description: str
    questions_total: int
    session_size: int  # сколько вопросов будет в одной сессии
    topics: list[TopicOut]  # непусто, если можно выбрать тему (тренировка)


class StartDemoIn(BaseModel):
    scenario_id: str
    model: str | None = None  # local или имя из llm_keys.json; None — локальная
    topic: str | None = None
    size: int | None = Field(default=None, ge=1, le=20)
    seed: int | None = None


class ScenarioBrief(BaseModel):
    id: str
    title: str
    kind: str
    level: str


class MessageOut(BaseModel):
    role: str  # assistant | candidate
    kind: str  # greeting | base_question | followup | answer | redirect | closing
    text: str
    question_id: str | None = None
    question_number: int | None = None
    at: str


class ProbeOut(BaseModel):
    id: str
    text: str
    status: str
    quote: str | None = None
    # Отладка: что сказала модель до проверки цитаты кодом.
    model_status: str | None = None
    model_quote: str | None = None
    quote_check: str = ""  # exact | fuzzy | rejected | ""


class LLMCallOut(BaseModel):
    purpose: str
    latency_ms: int
    valid_json: bool
    attempts: int


class DebugOut(BaseModel):
    """Отладка для тестирования: как модель разобрала последний ответ."""

    question_id: str
    question_number: int
    completeness: str
    followups: int
    max_followups: int
    probes: list[ProbeOut]
    last_calls: list[LLMCallOut]


class SessionOut(BaseModel):
    token: str
    scenario: ScenarioBrief
    model: str = ""
    model_local: bool = True
    question_number: int
    total_questions: int
    finished: bool
    stopped: bool
    messages: list[MessageOut]
    debug: DebugOut | None = None


class SendIn(BaseModel):
    text: str = Field(max_length=3000)  # = MAX_INPUT_CHARS в guardrails и лимит поля ввода


class ModelOut(BaseModel):
    id: str
    provider: str
    model: str
    local: bool
    note: str = ""


class HealthOut(BaseModel):
    ok: bool
    model: str
    url: str
    message: str
