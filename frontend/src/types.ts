// Типы ответов API (backend/app/schemas/interview.py и reporting/protocol.py).

export type Kind = "job_interview" | "knowledge_check";
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
  kind: "greeting" | "base_question" | "followup" | "answer" | "redirect" | "closing";
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
  scenario: { id: string; title: string; kind: Kind; level: string };
  question_number: number;
  total_questions: number;
  finished: boolean;
  stopped: boolean;
  messages: Message[];
  debug: Debug | null;
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
