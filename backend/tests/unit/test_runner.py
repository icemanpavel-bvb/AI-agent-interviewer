"""Диалог целиком на фейковой модели: уточнения, лимиты, «не знаю», стоп, протокол."""

import json

from app.interview.runner import InterviewRunner, plural_questions
from app.llm.fake import FakeLLM
from app.reporting.protocol import build_protocol
from app.scenarios import load_scenario


def answer_text(messages):
    user = messages[-1]["content"] if messages[-1]["role"] == "user" else messages[1]["content"]
    return user.split("<answer>")[1].split("</answer>")[0].strip()


def analysis(intent="answer", covered=(), partial=()):
    """Фейковый анализ: цитата — первые слова последнего ответа (она точно есть в тексте)."""

    def respond(messages):
        words = answer_text(messages).split("\n")[-1].split()
        quote = " ".join(words[:3])
        probes = [{"id": p, "status": "covered", "quote": quote} for p in covered]
        probes += [{"id": p, "status": "partial", "quote": quote} for p in partial]
        return {"intent": intent, "probes": probes}

    return respond


FOLLOWUP = {"question": "Уточните, пожалуйста, подробнее?"}


def runner_for(scenario_id, responses, **kw):
    sc = load_scenario(scenario_id)
    return InterviewRunner(sc, FakeLLM(responses), **kw), sc


def test_followup_then_next_question():
    r, _ = runner_for(
        "ml_junior",
        [
            analysis(covered=["p1"], partial=["p2"]),  # Q00 неполный
            FOLLOWUP,
            analysis(covered=["p1", "p2", "p3", "p4", "p5"]),  # после уточнения — полный
        ],
    )
    assert "Вопрос 1 из 8" in r.start().text
    reply = r.handle("Учусь в магистратуре, был на стажировке")
    assert reply.text == FOLLOWUP["question"] and r.index == 0
    reply = r.handle("Есть два пет-проекта, готов на 30 часов, выйду через неделю")
    assert r.index == 1 and "Вопрос 2 из 8" in reply.text
    st = r.states[0]
    assert st.followups == 1 and st.completeness == "complete" and st.ended_by == "complete"


def test_followup_limit_is_respected():
    # Q00 в ml_junior: max_followups = 1 → после одного уточнения идём дальше
    r, _ = runner_for("ml_junior", [analysis(partial=["p1"]), FOLLOWUP, analysis(partial=["p1"])])
    r.start()
    r.handle("что-то")
    r.handle("ещё что-то")
    assert r.index == 1 and r.states[0].ended_by == "followup_limit"


def test_dont_know_moves_on_and_stop_finishes():
    r, _ = runner_for("student_course", [analysis(intent="dont_know"), analysis(intent="stop")])
    r.start()
    r.handle("не знаю")
    assert r.index == 1 and r.states[0].ended_by == "dont_know"
    reply = r.handle("давайте закончим")
    assert reply.finished and r.stopped


def test_off_topic_twice_moves_on_without_answer():
    r, _ = runner_for("ml_junior", [analysis(intent="off_topic"), analysis(intent="question")])
    r.start()
    assert "вернёмся" in r.handle("какая погода?").text.lower()
    r.handle("а какая зарплата?")
    assert r.index == 1 and r.states[0].answers == [] and r.states[0].ended_by == "off_topic"


def test_full_session_protocol():
    sc = load_scenario("ml_junior")
    covered_all = {q.id: [p.id for p in q.probes] for q in sc.questions}
    responses = [analysis(covered=covered_all[q.id]) for q in sc.ordered_questions()]
    r = InterviewRunner(sc, FakeLLM(responses))
    r.start()
    for _ in sc.questions:
        reply = r.handle("Подробный ответ на вопрос с примерами")
    assert reply.finished
    protocol = build_protocol(r)
    statuses = {c["id"]: c["status"] for c in protocol["criteria"]}
    assert statuses["J04"] == "unknown"  # требует практики — в чате не закрывается
    assert statuses["J01"] == "covered"
    assert protocol["llm"]["calls"] == len(sc.questions)
    json.dumps(protocol, ensure_ascii=False)  # сериализуется для сохранения


def test_knowledge_check_uses_session_plan():
    sc = load_scenario("student_course")
    r = InterviewRunner(sc, FakeLLM(default=analysis(intent="dont_know")))
    assert len(r.plan) == sc.session.size
    r.start()
    while not r.finished:
        r.handle("не знаю")
    protocol = build_protocol(r)
    assert all(c["status"] == "missing" for c in protocol["criteria"])


def test_plural_questions():
    assert [plural_questions(n) for n in (1, 3, 5, 11, 21, 22)] == [
        "1 вопрос",
        "3 вопроса",
        "5 вопросов",
        "11 вопросов",
        "21 вопрос",
        "22 вопроса",
    ]
