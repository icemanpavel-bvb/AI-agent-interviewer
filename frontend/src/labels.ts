// Подписи для статусов на русском.
import type { Kind, ProbeStatus } from "./types";

export const KIND_LABEL: Record<Kind, string> = {
  job_interview: "Собеседование",
  knowledge_check: "Проверка знаний",
};

export const LEVEL_LABEL: Record<string, string> = {
  junior: "Junior",
  middle: "Middle",
  senior: "Senior",
  student: "Студент",
  any: "Любой уровень",
};

export const PROBE_MARK: Record<ProbeStatus, string> = { covered: "✓", partial: "~", missing: "✗" };

export const PROBE_LABEL: Record<ProbeStatus, string> = {
  covered: "раскрыт",
  partial: "частично",
  missing: "нет",
};

export const COMPLETENESS_LABEL: Record<string, string> = {
  complete: "ответ полный",
  partial: "ответ неполный",
  empty: "по пунктам ничего",
};

export const ENDED_BY_LABEL: Record<string, string> = {
  complete: "ответ полный",
  followup_limit: "исчерпан лимит уточнений",
  dont_know: "не знает",
  off_topic: "ответы не по теме",
  stopped: "сессия прервана",
  llm_failed: "модель не ответила — проверить вручную",
  not_asked: "не задан",
};

export function questionsWord(n: number): string {
  const d = n % 10;
  const h = n % 100;
  if (d === 1 && h !== 11) return `${n} вопрос`;
  if (d >= 2 && d <= 4 && (h < 12 || h > 14)) return `${n} вопроса`;
  return `${n} вопросов`;
}
