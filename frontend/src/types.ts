// Типы ответов API (backend/app/schemas/interview.py и reporting/protocol.py).

export type Kind = "job_interview" | "knowledge_check";

// Совпадает с MAX_INPUT_CHARS в backend/app/interview/guardrails.py и SendIn в API.
export const MAX_ANSWER_CHARS = 3000;
export type ProbeStatus = "covered" | "partial" | "missing";

export interface Topic {
  id: string;
  name: string;
  questions: number;
}

export interface ScenarioCard {
  id: string;
  title: string;
  kind: Kind;
  level: string;
  status: "draft" | "ready";
  tags: string[];
  description: string;
  questions_total: number;
  session_size: number;
  topics: Topic[];
}

export interface Message {
  role: "assistant" | "candidate";
  kind:
    | "greeting"
    | "base_question"
    | "followup"
    | "clarify"
    | "answer"
    | "redirect"
    | "notice"
    | "closing";
  text: string;
  question_id: string | null;
  question_number: number | null;
  at: string;
}

export interface Probe {
  id: string;
  text: string;
  status: ProbeStatus;
  quote: string | null;
  // Отладка: что сказала модель до проверки цитаты кодом.
  model_status?: string | null;
  model_quote?: string | null;
  quote_check?: "exact" | "fuzzy" | "rejected" | "";
}

export interface LLMCallInfo {
  purpose: string;
  latency_ms: number;
  valid_json: boolean;
  attempts: number;
}

export interface Debug {
  question_id: string;
  question_number: number;
  completeness: "complete" | "partial" | "empty";
  followups: number;
  max_followups: number;
  probes: Probe[];
  last_calls: LLMCallInfo[];
}

export interface Session {
  token: string;
  model: string; // local-модель или имя из llm_keys.json
  model_local: boolean;
  scenario: { id: string; title: string; kind: Kind; level: string };
  question_number: number;
  total_questions: number;
  finished: boolean;
  stopped: boolean;
  messages: Message[];
  debug: Debug | null;
}

// Модель для проверки ответов (D-013): локальная или облачная из llm_keys.json, без ключа.
export interface ModelInfo {
  id: string;
  provider: string;
  model: string;
  local: boolean;
  note: string;
}

export interface Health {
  ok: boolean;
  model: string;
  url: string;
  message: string;
}

export interface ProtocolCriterion {
  id: string;
  name: string;
  status: ProbeStatus | "unknown";
  label: string;
  questions: string[];
}

export interface ProtocolQuestion {
  id: string;
  text: string;
  criteria: string[];
  asked: boolean;
  answers: string[];
  followups: number;
  ended_by: string;
  completeness: string;
  needs_manual_check: boolean;
  flags: string[];
  probes: Probe[];
}

export interface Protocol {
  scenario: { id: string; title: string; kind: Kind; level: string };
  started_at: string;
  finished_at: string | null;
  stopped_early: boolean;
  criteria: ProtocolCriterion[];
  questions: ProtocolQuestion[];
  llm: {
    model: string;
    calls: number;
    invalid_json: number;
    avg_latency_ms: number;
    max_latency_ms: number;
  };
  references?: Record<string, string>;
}
