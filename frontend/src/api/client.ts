// Все запросы к бэкенду в одном месте. Базовый путь /api/v1 (в разработке — прокси Vite на :8000).
import type { Health, Protocol, ScenarioCard, Session } from "../types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "Нет связи с сервером");
  }
  if (!res.ok) {
    let message = res.status >= 500 && res.status !== 503
      ? "Бэкенд не отвечает. Запущен ли uvicorn (см. README)?"
      : res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* ответ не JSON — оставляем сообщение по умолчанию */
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

const post = (body?: unknown): RequestInit => ({
  method: "POST",
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/demo/health"),
  scenarios: () => request<ScenarioCard[]>("/demo/scenarios"),
  start: (body: { scenario_id: string; topic?: string; size?: number }) =>
    request<Session>("/demo/start", post(body)),
  session: (token: string) => request<Session>(`/interview/${token}`),
  send: (token: string, text: string) =>
    request<Session>(`/interview/${token}/messages`, post({ text })),
  stop: (token: string) => request<Session>(`/interview/${token}/stop`, post()),
  protocol: (token: string) => request<Protocol>(`/interview/${token}/protocol`),
};
