"""Обработка одного хода кандидата: загрузка сессии с блокировкой → guardrails → классификация → анализ → policy → реплика."""

from dataclasses import dataclass


@dataclass
class TurnResult:
    reply: str
    question_index: int  # номер текущего базового вопроса (с 1)
    total_questions: int
    finished: bool


class InterviewEngine:
    """Переходы между шагами задаёт этот класс (код), LLM используется только внутри шагов."""

    async def start(self, session_id) -> TurnResult:
        """Первое открытие ссылки: приветствие + текст согласия."""
        raise NotImplementedError

    async def accept_consent(self, session_id, accepted: bool) -> TurnResult:
        """Согласие → первый базовый вопрос; отказ → DECLINED."""
        raise NotImplementedError

    async def handle_turn(self, session_id, text: str) -> TurnResult:
        """1) SELECT ... FOR UPDATE; 2) guardrails.check_input; 3) сохранить ответ;
        4) analyzer.classify_and_analyze; 5) policy.decide; 6) сформировать реплику;
        7) guardrails.check_output; 8) сохранить; 9) если FINALIZE — фоновая задача build_report."""
        raise NotImplementedError
