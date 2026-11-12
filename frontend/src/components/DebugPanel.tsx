// Отладка для тестирования: как модель разобрала последний ответ (пункты, цитаты, время).
import { COMPLETENESS_LABEL, PROBE_LABEL, PROBE_MARK } from "../labels";
import type { Debug, Probe } from "../types";

const MODEL_STATUS: Record<string, string> = { covered: "раскрыт", partial: "частично", missing: "нет" };

// Что сказала модель до проверки кодом — чтобы видеть, кто ошибся: модель или проверка цитат.
function ModelVerdict({ probe }: { probe: Probe }) {
  if (probe.model_status == null) return <div className="verdict">модель про этот пункт ничего не сказала</div>;
  const said = `модель: ${MODEL_STATUS[probe.model_status] ?? probe.model_status}`;
  if (probe.quote_check === "rejected")
    return (
      <div className="verdict verdict-bad">
        {said}, цитата «{probe.model_quote ?? "—"}» не найдена в ответе → пункт сброшен
      </div>
    );
  if (probe.quote_check === "fuzzy")
    return (
      <div className="verdict">
        {said}, цитата совпала по словам (модель привела «{probe.model_quote}»), показан фрагмент ответа
      </div>
    );
  if (probe.quote_check === "exact") return <div className="verdict">{said}, цитата найдена дословно</div>;
  return <div className="verdict">{said}</div>;
}

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
                  <ModelVerdict probe={p} />
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
        В обычной работе кандидат это не видит. ✓ — пункт раскрыт, ~ — частично, ✗ — нет. Под пунктом — что
        сказала модель и как код проверил её цитату.
      </p>
    </aside>
  );
}
