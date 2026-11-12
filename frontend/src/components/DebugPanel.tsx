// Отладка для тестирования: как модель разобрала последний ответ (пункты, цитаты, время).
import { COMPLETENESS_LABEL, PROBE_LABEL, PROBE_MARK } from "../labels";
import type { Debug } from "../types";

export default function DebugPanel({ debug }: { debug: Debug | null }) {
  return (
    <aside className="debug">
      <h3>Отладка</h3>
      {!debug ? (
        <p className="muted">Ответьте на вопрос — здесь появится разбор: какие пункты модель нашла в ответе.</p>
      ) : (
        <>
          <p className="debug-meta">
            Вопрос {debug.question_number} ({debug.question_id}) · {COMPLETENESS_LABEL[debug.completeness]} ·
            уточнений {debug.followups} из {debug.max_followups}
          </p>
          <ul className="probes">
            {debug.probes.map((p) => (
              <li key={p.id} className={`probe probe-${p.status}`}>
                <span className="mark" title={PROBE_LABEL[p.status]}>{PROBE_MARK[p.status]}</span>
                <div>
                  <div>{p.text}</div>
                  {p.quote && <q>{p.quote}</q>}
                </div>
              </li>
            ))}
          </ul>
          <h4>Вызовы модели</h4>
          <ul className="calls">
            {debug.last_calls.map((c, i) => (
              <li key={i}>
                {c.purpose === "analyze_answer" ? "анализ" : c.purpose === "followup" ? "уточнение" : c.purpose}:{" "}
                <b>{(c.latency_ms / 1000).toFixed(1)} с</b>
                {c.attempts > 1 && `, попыток ${c.attempts}`}
                {!c.valid_json && <span className="error-text"> · невалидный JSON</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="muted small">
        В обычной работе кандидат это не видит. ✓ — пункт раскрыт, ~ — частично, ✗ — нет. Цитаты сверены кодом с ответом.
      </p>
    </aside>
  );
}
