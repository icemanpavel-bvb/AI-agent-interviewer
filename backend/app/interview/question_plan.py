"""План вопросов на одну сессию (D-006).

Собеседование: все вопросы по порядку — как требуют БТ.
Проверка знаний: из банка вопросов выбирается session.size штук, по возможности
по одному из каждой темы (критерия), остальные — случайно. Порядок внутри сессии
следует порядку в сценарии, чтобы темы шли логично. Выбранные id сохраняются
в interview_session.question_plan, поэтому при возврате кандидата план не меняется.
"""

from __future__ import annotations

import random
from collections import OrderedDict

from app.schemas.scenario import Question, Scenario


def plan_questions(
    scenario: Scenario,
    rng: random.Random | None = None,
    topic: str | None = None,
) -> list[Question]:
    questions = scenario.ordered_questions()

    if topic is not None:
        if not (scenario.session and scenario.session.allow_topic_choice):
            raise ValueError("в этом сценарии нельзя выбрать тему")
        picked = [q for q in questions if topic in q.criteria]
        if not picked:
            raise ValueError(f"нет вопросов по теме {topic}")
        return picked  # тренировка по теме: все её вопросы по порядку

    plan = scenario.session
    if scenario.kind == "job_interview" or plan is None or plan.strategy == "in_order":
        return questions

    rng = rng or random.Random()
    size = min(plan.size, len(questions))

    # Группы по первой теме вопроса, внутри группы — случайный порядок.
    groups: OrderedDict[str, list[Question]] = OrderedDict()
    for q in questions:
        groups.setdefault(q.criteria[0] if q.criteria else "_", []).append(q)
    for g in groups.values():
        rng.shuffle(g)

    # По кругу: сначала по одному из каждой темы (в случайном порядке тем), затем ещё круг и т.д.
    topic_order = list(groups)
    rng.shuffle(topic_order)
    chosen: list[Question] = []
    while len(chosen) < size:
        for t in topic_order:
            if groups[t] and len(chosen) < size:
                chosen.append(groups[t].pop())
    return sorted(chosen, key=lambda q: q.order)
