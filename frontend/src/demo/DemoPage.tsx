// Демо-страница /demo (D-005): проверка модели, карточки сценариев, старт сессии.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { KIND_LABEL, LEVEL_LABEL, questionsWord } from "../labels";
import type { Health, ScenarioCard } from "../types";

export default function DemoPage() {
  const [cards, setCards] = useState<ScenarioCard[] | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.scenarios().then(setCards).catch((e: ApiError) => setError(e.message));
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">TEAM-12 · демо-режим</p>
          <h1>AI-интервьюер</h1>
          <p className="lead">
            Выберите сценарий и пройдите интервью или проверку знаний. Ассистент задаёт вопросы,
            уточняет неполные ответы и в конце показывает протокол с цитатами — без баллов.
          </p>
        </div>
        <HealthBadge health={health} />
      </header>

      {error && <div className="banner banner-error">{error}</div>}
      {health && !health.ok && (
        <div className="banner banner-warn">
          {health.message}. Чат откроется, но ответы не будут обработаны, пока модель недоступна.
        </div>
      )}

      {!cards && !error && <p className="muted">Загружаю сценарии…</p>}
      <div className="cards">
        {cards?.map((c) => <ScenarioCardView key={c.id} card={c} />)}
      </div>

      <footer className="page-foot muted">
        Демо: ответы хранятся только в памяти сервера и исчезают после его перезапуска.
      </footer>
    </div>
  );
}

function HealthBadge({ health }: { health: Health | null }) {
  if (!health) return <span className="pill pill-muted">модель: проверяю…</span>;
  return (
    <span className={`pill ${health.ok ? "pill-ok" : "pill-bad"}`} title={health.url}>
      {health.ok ? "●" : "○"} {health.model}
      {health.ok ? "" : " недоступна"}
    </span>
  );
}

function ScenarioCardView({ card }: { card: ScenarioCard }) {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isKnowledge = card.kind === "knowledge_check";
  const needConsent = card.kind === "job_interview";
  const selectedTopic = card.topics.find((t) => t.id === topic);
  const count = selectedTopic ? selectedTopic.questions : card.session_size;

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const s = await api.start({ scenario_id: card.id, topic: topic || undefined });
      navigate(`/i/${s.token}`);
    } catch (e) {
      setError((e as ApiError).message);
      setBusy(false);
    }
  }

  return (
    <article className="card">
      <div className="card-tags">
        <span className={`tag ${isKnowledge ? "tag-study" : "tag-job"}`}>{KIND_LABEL[card.kind]}</span>
        <span className="tag">{LEVEL_LABEL[card.level] ?? card.level}</span>
        {card.status === "draft" && <span className="tag tag-draft">черновик</span>}
      </div>
      <h2>{card.title}</h2>
      <p className="card-desc">{card.description}</p>
      <p className="card-meta">
        {isKnowledge && !selectedTopic
          ? `${questionsWord(count)} из банка в ${card.questions_total}, каждый раз разные`
          : questionsWord(count)}
        {" · до 2 уточнений на вопрос"}
      </p>

      {card.topics.length > 0 && (
        <label className="field">
          <span>Темы</span>
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">Все темы — случайные {card.session_size}</option>
            {card.topics.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({questionsWord(t.questions)})
              </option>
            ))}
          </select>
        </label>
      )}

      {needConsent && (
        <label className="check">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>Согласен на обработку ответов в рамках интервью</span>
        </label>
      )}

      {error && <p className="error-text">{error}</p>}
      <button className="btn btn-primary" disabled={busy || (needConsent && !consent)} onClick={start}>
        {busy ? "Запускаю…" : isKnowledge ? "Начать проверку" : "Начать интервью"}
      </button>
    </article>
  );
}
