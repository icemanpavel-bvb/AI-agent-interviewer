"""Схема JSON-файла сценария вакансии (scenarios/*.json). См. docs/decisions.md, D-003 и D-004.

Сценарий — это данные, а не код: вопросы, критерии с весами, пункты проверки (probes)
и эталонные ответы-примеры. Файл проверяется этой схемой перед загрузкой в БД.

Важно: всё, что лежит в `recruiter_only` (шкалы 1–4, заметки, ключи кейсов), НИКОГДА
не передаётся в модель интервью. Для промптов используйте `Scenario.llm_view()`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

MAX_BASE_QUESTIONS = 10  # собеседование: все вопросы задаются, не больше 10 (БТ)
MAX_BANK_QUESTIONS = 60  # проверка знаний: банк вопросов, из него выборка на сессию (D-006)
MAX_SESSION_QUESTIONS_KNOWLEDGE = 20
MAX_FOLLOWUPS = 2
MAX_PROBES = 6

ScenarioKind = Literal["job_interview", "knowledge_check"]
ScenarioLevel = Literal["junior", "middle", "senior", "student", "any"]
ScenarioStatus = Literal["draft", "ready"]
QuestionType = Literal["conditions", "experience", "situational", "knowledge"]


class RecruiterOnly(BaseModel):
    """Данные только для рекрутера: в модель не передаются."""

    rubric: dict[str, str] = Field(
        default_factory=dict, description="Шкала: уровень → наблюдаемый признак"
    )
    notes: str = ""


class Criterion(BaseModel):
    id: str
    name: str
    description: str = ""
    weight: int = Field(ge=0, le=100, description="Вес в процентах; 0 — критерий без веса")
    must_have: bool = False
    # Самоотчёт в чате не закрывает такой критерий: в протоколе он всегда unknown.
    requires_practice: bool = False
    recruiter_only: RecruiterOnly | None = None


class Probe(BaseModel):
    """Пункт проверки: что должно прозвучать в ответе (D-004)."""

    id: str
    text: str


class Question(BaseModel):
    id: str
    order: int = Field(ge=1)
    type: QuestionType
    text: str = Field(min_length=10)
    criteria: list[str] = Field(default_factory=list)
    probes: list[Probe] = Field(min_length=1, max_length=MAX_PROBES)
    # Пример сильного ответа: помогает модели понять, что считать раскрытым пунктом.
    # Это не образец для сравнения на похожесть.
    reference_answer: str = ""
    # Подсказка, какие доказательства искать (из методики); видна модели.
    evidence_hint: str = ""
    max_followups: int = Field(default=2, ge=0, le=MAX_FOLLOWUPS)
    required: bool = True
    recruiter_only: RecruiterOnly | None = None

    @model_validator(mode="after")
    def _check(self) -> Question:
        ids = [p.id for p in self.probes]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: id пунктов проверки повторяются")
        if not self.criteria and self.type != "conditions":
            raise ValueError(f"{self.id}: без критериев может быть только вопрос типа conditions")
        return self


class Screening(BaseModel):
    """Правила для вопроса об опыте и условиях (Q00)."""

    # Порог стажа: ниже — пометка для рекрутера, не отказ. None — порога нет.
    min_experience_years: float | None = None
    # Стаж считает код по периодам без двойного счёта параллельных работ.
    count_parallel_once: bool = True
    recruiter_flags: list[str] = Field(
        default_factory=list, description="Когда поставить пометку рекрутеру"
    )


class SessionPlan(BaseModel):
    """Сколько и каких вопросов задавать за одну сессию (D-006).

    in_order        — все вопросы по порядку (собеседования; size игнорируется).
    balanced_random — случайная выборка size вопросов, по возможности из каждой темы
                      (проверка знаний: каждый заход — новые вопросы).
    """

    size: int = Field(default=10, ge=1, le=MAX_SESSION_QUESTIONS_KNOWLEDGE)
    strategy: Literal["in_order", "balanced_random"] = "in_order"
    # Можно выбрать одну тему (критерий) и пройти все её вопросы — режим тренировки.
    allow_topic_choice: bool = False


class Scenario(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    kind: ScenarioKind
    level: ScenarioLevel
    status: ScenarioStatus = "draft"
    source: str = ""
    tags: list[str] = Field(default_factory=list)
    # Описание вакансии: по нему агент отвечает на вопросы кандидата.
    description: str
    # Правила поведения агента для этого сценария (видны модели).
    agent_rules: list[str] = Field(default_factory=list)
    screening: Screening | None = None
    session: SessionPlan | None = None
    criteria: list[Criterion] = Field(default_factory=list)
    questions: list[Question] = Field(min_length=1, max_length=MAX_BANK_QUESTIONS)

    @model_validator(mode="after")
    def _check(self) -> Scenario:
        if self.kind == "job_interview":
            if len(self.questions) > MAX_BASE_QUESTIONS:
                raise ValueError(
                    f"в собеседовании не больше {MAX_BASE_QUESTIONS} вопросов, сейчас {len(self.questions)}"
                )
            if self.session and self.session.strategy != "in_order":
                raise ValueError(
                    "в собеседовании вопросы задаются все и по порядку (strategy: in_order)"
                )
        crit_ids = [c.id for c in self.criteria]
        if len(crit_ids) != len(set(crit_ids)):
            raise ValueError("id критериев повторяются")
        q_ids = [q.id for q in self.questions]
        if len(q_ids) != len(set(q_ids)):
            raise ValueError("id вопросов повторяются")
        orders = sorted(q.order for q in self.questions)
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError(f"order вопросов должен идти подряд с 1, сейчас {orders}")

        known = set(crit_ids)
        used: set[str] = set()
        for q in self.questions:
            unknown = set(q.criteria) - known
            if unknown:
                raise ValueError(f"{q.id}: неизвестные критерии {sorted(unknown)}")
            used |= set(q.criteria)

        weighted = [c for c in self.criteria if c.weight > 0]
        if weighted and self.status == "ready":
            total = sum(c.weight for c in weighted)
            if total != 100:
                raise ValueError(f"сумма весов критериев {total}, должна быть 100")
        uncovered = [c.id for c in weighted if c.id not in used]
        if uncovered:
            raise ValueError(f"критерии без вопросов: {uncovered}")
        return self

    def llm_view(self) -> dict:
        """Сценарий без recruiter_only — только это можно передавать в модель."""
        return self.model_dump(
            exclude={
                "criteria": {"__all__": {"recruiter_only"}},
                "questions": {"__all__": {"recruiter_only"}},
            }
        )

    def ordered_questions(self) -> list[Question]:
        return sorted(self.questions, key=lambda q: q.order)
