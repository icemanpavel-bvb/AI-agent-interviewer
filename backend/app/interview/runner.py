"""Ядро диалога без БД и без HTTP: одна сессия интервью в памяти.

Используется консольным прототипом (app/cli) и позже — Interview Engine в API,
который будет сохранять состояние в БД после каждого хода. Решения о переходах
принимает код (policy), модель только анализирует ответы и формулирует уточнения.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.interview.analyzer import (
    Analysis,
    ProbeResult,
    analyze_answer,
    completeness_of,
    merge_best,
)
from app.interview.followup import make_followup
from app.interview.guardrails import MAX_INPUT_CHARS, clean_input
from app.interview.policy import NextStep, PolicyInput, decide
from app.interview.question_plan import plan_questions
from app.llm.base import LLMCall, LLMProvider
from app.schemas.scenario import Question, Scenario

MAX_OFF_TOPIC = 2  # после стольких ответов не по теме переходим к следующему вопросу
MAX_CLARIFY = 2  # пояснений вопроса (не тратят лимит уточнений); дальше — просим ответить как есть


def plural_questions(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} вопрос"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} вопроса"
    return f"{n} вопросов"


@dataclass
class Turn:
    role: str  # assistant | candidate
    # greeting | base_question | followup | clarify | answer | redirect | notice | closing
    kind: str
    text: str
    question_id: str | None = None
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


@dataclass
class QuestionState:
    question: Question
    answers: list[str] = field(default_factory=list)
    followups: int = 0
    off_topic: int = 0
    clarifications: int = 0
    probes: list[ProbeResult] = field(default_factory=list)
    completeness: str = "empty"
    ended_by: str = ""  # complete | followup_limit | dont_know | off_topic | stopped | llm_failed
    llm_failed: bool = False
    flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.probes:
            self.probes = [ProbeResult(p.id, p.text) for p in self.question.probes]


@dataclass
class Reply:
    text: str
    finished: bool
    question_number: int
    total_questions: int


class InterviewRunner:
    def __init__(
        self,
        scenario: Scenario,
        provider: LLMProvider,
        *,
        plan: list[Question] | None = None,
        rng: random.Random | None = None,
        topic: str | None = None,
    ) -> None:
        self.scenario = scenario
        self.provider = provider
        self.plan = plan or plan_questions(scenario, rng, topic)
        self.states = [QuestionState(q) for q in self.plan]
        self.index = 0
        self.transcript: list[Turn] = []
        self.llm_log: list[LLMCall] = []
        self.finished = False
        self.stopped = False
        self.started_at = datetime.now(UTC).isoformat(timespec="seconds")
        self.finished_at: str | None = None

    # ---------- сохранение (демо-сессии на диске) ----------

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        state["provider"] = None  # модель не сохраняем: при загрузке подставляется текущая
        return state

    # ---------- публичный интерфейс ----------

    @property
    def current(self) -> QuestionState:
        return self.states[self.index]

    def start(self) -> Reply:
        if self.scenario.kind == "knowledge_check":
            greeting = (
                f"Здравствуйте! Это проверка знаний: «{self.scenario.title}». "
                f"Будет {plural_questions(len(self.plan))}, на неполные ответы я задам уточнения. "
                "Отвечайте своими словами, формулы не обязательны. Если не знаете ответа — так и напишите."
            )
        else:
            greeting = (
                f"Здравствуйте! Я AI-ассистент первичного интервью на вакансию «{self.scenario.title}». "
                f"Задам {plural_questions(len(self.plan))}, иногда — уточняющие. Решение о следующем этапе "
                "принимает рекрутер, я только помогаю собрать информацию."
            )
        self._say("greeting", greeting)
        return self._ask_current(prefix=greeting + "\n\n")

    def handle(self, text: str) -> Reply:
        if self.finished:
            raise RuntimeError("сессия уже завершена")
        state = self.current
        cleaned, flags = clean_input(text)
        if "empty" in flags:
            return self._reply("Похоже, сообщение пустое. " + self._question_line(state))
        # Сначала анализ: если модель недоступна (LLMUnavailable), состояние не меняется
        # и тот же ответ можно отправить ещё раз.
        analysis = analyze_answer(
            self.provider, state.question, [*state.answers, cleaned], log=self.llm_log
        )
        state.flags.extend(f for f in flags if f not in state.flags)
        self.transcript.append(Turn("candidate", "answer", cleaned, state.question.id))
        notice = ""
        if "too_long" in flags:
            notice = f"Ответ длиннее {MAX_INPUT_CHARS} символов — учтены первые {MAX_INPUT_CHARS}."
            self._say("notice", notice, state.question.id)
        reply = self._dispatch(state, cleaned, analysis)
        if notice:
            reply.text = f"{notice}\n\n{reply.text}"
        return reply

    def _dispatch(self, state: QuestionState, cleaned: str, analysis: Analysis) -> Reply:

        if analysis.intent == "stop":
            state.ended_by = "stopped"
            self.stopped = True
            return self._finish("Хорошо, завершаем. Спасибо за уделённое время!")

        if analysis.intent == "clarify":
            state.clarifications += 1
            if state.clarifications > MAX_CLARIFY:
                return self._reply(
                    "Ответьте, пожалуйста, как вы понимаете вопрос — даже неполный ответ подойдёт. "
                    + self._question_line(state),
                    kind="redirect",
                )
            missing = [p.text for p in state.probes if p.status != "covered"] or [
                p.text for p in state.question.probes
            ]
            text = make_followup(
                self.provider,
                state.question,
                state.answers,
                missing,
                reveal_topics=self.scenario.kind == "job_interview",
                log=self.llm_log,
            )
            self._say("clarify", text, state.question.id)
            return self._reply(text, record=False)

        if analysis.intent in ("question", "off_topic"):
            state.off_topic += 1
            if state.off_topic >= MAX_OFF_TOPIC:
                state.ended_by = "off_topic"
                return self._advance("Перейдём к следующему вопросу.")
            if analysis.intent == "question":
                lead = (
                    "Этот вопрос лучше задать рекрутеру на следующем этапе."
                    if self.scenario.kind == "job_interview"
                    else "Сейчас я только задаю вопросы, ответы будут в итоге сессии."
                )
            else:
                lead = "Давайте вернёмся к вопросу."
            return self._reply(f"{lead} {self._question_line(state)}", kind="redirect")

        state.answers.append(cleaned)

        if analysis.intent == "dont_know":
            state.completeness = completeness_of(state.probes)
            state.ended_by = "dont_know"
            return self._advance("Хорошо, идём дальше.")

        if analysis.llm_failed:
            state.llm_failed = True
            state.ended_by = "llm_failed"
            return self._advance("Спасибо!")

        state.probes = merge_best(state.probes, analysis.probes)
        state.completeness = completeness_of(state.probes)
        step = decide(
            PolicyInput(
                completeness=state.completeness,
                followups_used=state.followups,
                max_followups=state.question.max_followups,
                question_index=self.index,
                total_questions=len(self.plan),
            )
        )
        if step == NextStep.FOLLOWUP:
            missing = [p.text for p in state.probes if p.status != "covered"]
            text = make_followup(
                self.provider,
                state.question,
                state.answers,
                missing,
                reveal_topics=self.scenario.kind == "job_interview",
                log=self.llm_log,
            )
            state.followups += 1
            self._say("followup", text, state.question.id)
            return self._reply(text, record=False)

        state.ended_by = "complete" if state.completeness == "complete" else "followup_limit"
        return self._advance("Спасибо!")

    def stop(self) -> Reply:
        """Прерывание извне (Ctrl+C в консоли, закрытие сессии)."""
        if not self.finished:
            self.current.ended_by = self.current.ended_by or "stopped"
            self.stopped = True
            return self._finish("Сессия прервана.")
        return self._reply("Сессия уже завершена.", record=False)

    # ---------- внутреннее ----------

    def _question_line(self, state: QuestionState) -> str:
        return f"Вопрос {self.index + 1} из {len(self.plan)}: {state.question.text}"

    def _ask_current(self, prefix: str = "") -> Reply:
        state = self.current
        line = self._question_line(state)
        self._say("base_question", state.question.text, state.question.id)
        return self._reply(prefix + line, record=False)

    def _advance(self, lead: str) -> Reply:
        if self.index + 1 >= len(self.plan):
            return self._finish(lead)
        self.index += 1
        return self._ask_current(prefix=lead + "\n\n")

    def _finish(self, lead: str) -> Reply:
        closing = (
            "Сессия завершена. Итог по темам — в протоколе."
            if self.scenario.kind == "knowledge_check"
            else "Интервью завершено, спасибо за ответы! Рекрутер изучит протокол и свяжется с вами."
        )
        self.finished = True
        self.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
        self._say("closing", closing)
        return Reply(f"{lead}\n\n{closing}", True, self.index + 1, len(self.plan))

    def _say(self, kind: str, text: str, question_id: str | None = None) -> None:
        self.transcript.append(Turn("assistant", kind, text, question_id))

    def _reply(self, text: str, *, kind: str = "redirect", record: bool = True) -> Reply:
        if record:
            self._say(kind, text, self.current.question.id)
        return Reply(text, False, self.index + 1, len(self.plan))
