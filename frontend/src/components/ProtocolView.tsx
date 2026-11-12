// Протокол в конце сессии: критерии или темы, пункты с цитатами, эталоны (для проверки знаний).
import { Link } from "react-router-dom";

import { ENDED_BY_LABEL, PROBE_MARK } from "../labels";
import type { Protocol } from "../types";

export default function ProtocolView({ protocol }: { protocol: Protocol }) {
  const isKnowledge = protocol.scenario.kind === "knowledge_check";

  function download() {
    const blob = new Blob([JSON.stringify(protocol, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `protocol_${protocol.scenario.id}_${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <section className="protocol">
      <h2>Протокол</h2>
      <p className="muted">
        {isKnowledge
          ? "Итог по темам: раскрыта ли тема в ваших ответах. Это не оценка, а подсказка, что повторить."
          : "Наличие информации по критериям вакансии, с цитатами. Баллов нет — решение принимает рекрутер."}
      </p>

      <h3>{isKnowledge ? "Темы" : "Критерии"}</h3>
      <ul className="criteria">
        {protocol.criteria.map((c) => (
          <li key={c.id} className={`crit crit-${c.status}`}>
            <span className="crit-name">{c.name}</span>
            <span className="crit-label">{c.label}</span>
          </li>
        ))}
      </ul>

      <h3>Ответы по вопросам</h3>
      {protocol.questions
        .filter((q) => q.asked)
        .map((q) => {
          const reference = protocol.references?.[q.id];
          return (
            <details key={q.id} className="q" open={q.completeness !== "complete"}>
              <summary>
                <span className={`q-dot q-${q.completeness}`} />
                <span className="q-text">{q.text}</span>
                <span className="muted small">
                  {ENDED_BY_LABEL[q.ended_by] ?? q.ended_by}
                  {q.followups > 0 && ` · уточнений ${q.followups}`}
                </span>
              </summary>
              <ul className="probes">
                {q.probes.map((p) => (
                  <li key={p.id} className={`probe probe-${p.status}`}>
                    <span className="mark">{PROBE_MARK[p.status]}</span>
                    <div>
                      <div>{p.text}</div>
                      {p.quote && <q>{p.quote}</q>}
                    </div>
                  </li>
                ))}
              </ul>
              {reference && q.completeness !== "complete" && (
                <div className="reference">
                  <b>Эталон для повторения.</b> {reference}
                </div>
              )}
            </details>
          );
        })}

      <p className="muted small">
        Модель {protocol.llm.model}: вызовов {protocol.llm.calls}, в среднем{" "}
        {(protocol.llm.avg_latency_ms / 1000).toFixed(1)} с, максимум{" "}
        {(protocol.llm.max_latency_ms / 1000).toFixed(1)} с, невалидный JSON — {protocol.llm.invalid_json}
      </p>
      <div className="protocol-actions">
        <button className="btn" onClick={download}>Скачать JSON</button>
        <Link className="btn btn-primary" to="/demo">Новая сессия</Link>
      </div>
    </section>
  );
}
