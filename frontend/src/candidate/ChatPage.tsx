// Чат интервью /i/:token: история, ввод ответа, прогресс, отладка, протокол в конце.
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import DebugPanel from "../components/DebugPanel";
import ProtocolView from "../components/ProtocolView";
import type { Message, Protocol, Session } from "../types";

export default function ChatPage() {
  const { token = "" } = useParams();
  const [session, setSession] = useState<Session | null>(null);
  const [protocol, setProtocol] = useState<Protocol | null>(null);
  const [text, setText] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [debug, setDebug] = useState(() => localStorage.getItem("debug") === "1");
  const endRef = useRef<HTMLDivElement>(null);
  const protocolRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.session(token).then(setSession).catch((e: ApiError) => setFatal(e.message));
  }, [token]);

  useEffect(() => {
    if (session?.finished && !protocol) api.protocol(token).then(setProtocol).catch(() => {});
  }, [session?.finished, protocol, token]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [session?.messages.length, pending]);

  useEffect(() => {
    if (protocol) protocolRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [protocol]);

  useEffect(() => {
    if (pending === null) return;
    setElapsed(0);
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [pending]);

  function toggleDebug() {
    const next = !debug;
    setDebug(next);
    try {
      localStorage.setItem("debug", next ? "1" : "0");
    } catch {
      /* приватный режим браузера — не страшно */
    }
  }

  async function send() {
    const value = text.trim();
    if (!value || pending !== null || !session || session.finished) return;
    setPending(value);
    setText("");
    setError(null);
    try {
      setSession(await api.send(token, value));
    } catch (e) {
      setText(value); // ответ не засчитан — возвращаем его в поле ввода
      setError((e as ApiError).message);
    } finally {
      setPending(null);
      inputRef.current?.focus();
    }
  }

  async function stop() {
    if (!session || session.finished) return;
    if (!window.confirm("Завершить сессию досрочно? Протокол будет по тем ответам, что уже есть.")) return;
    try {
      setSession(await api.stop(token));
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  if (fatal) {
    return (
      <div className="page narrow">
        <div className="banner banner-error">{fatal}</div>
        <Link to="/demo" className="btn">← К выбору сценария</Link>
      </div>
    );
  }
  if (!session) return <div className="page narrow muted">Загружаю сессию…</div>;

  const progress = session.finished
    ? 100
    : Math.round(((session.question_number - 1) / session.total_questions) * 100);

  return (
    <div className={`chat-layout ${debug ? "with-debug" : ""}`}>
      <div className="chat">
        <header className="chat-head">
          <Link to="/demo" className="back" title="К выбору сценария">←</Link>
          <div className="chat-title">
            <strong>{session.scenario.title}</strong>
            <span className="muted">
              {session.finished
                ? session.stopped ? "Сессия прервана" : "Сессия завершена"
                : `Вопрос ${session.question_number} из ${session.total_questions}`}
            </span>
          </div>
          <button className={`btn btn-small ${debug ? "btn-on" : ""}`} onClick={toggleDebug}>
            Отладка
          </button>
          {!session.finished && (
            <button className="btn btn-small" onClick={stop}>Завершить</button>
          )}
        </header>
        <div className="progress"><div style={{ width: `${progress}%` }} /></div>

        <main className="messages">
          {session.messages.map((m, i) => (
            <Bubble key={i} m={m} total={session.total_questions} />
          ))}
          {pending !== null && (
            <>
              <div className="bubble bubble-me pending">{pending}</div>
              <div className="typing">
                <span className="dots"><i /><i /><i /></span>
                Ассистент анализирует ответ… {elapsed} с
                {elapsed >= 20 && <span className="muted"> (первый ответ после запуска модели бывает долгим)</span>}
              </div>
            </>
          )}
          {protocol && (
            <div ref={protocolRef}>
              <ProtocolView protocol={protocol} />
            </div>
          )}
          {session.finished && !protocol && <p className="muted center">Собираю протокол…</p>}
          <div ref={endRef} />
        </main>

        {!session.finished && (
          <footer className="composer">
            {error && <div className="banner banner-error">{error}</div>}
            <div className="composer-row">
              <textarea
                ref={inputRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKey}
                placeholder="Ваш ответ… (Enter — отправить, Shift+Enter — новая строка)"
                rows={3}
                maxLength={4000}
                disabled={pending !== null}
                autoFocus
              />
              <button className="btn btn-primary" onClick={send} disabled={pending !== null || !text.trim()}>
                Отправить
              </button>
            </div>
          </footer>
        )}
      </div>
      {debug && <DebugPanel debug={session.debug} />}
    </div>
  );
}

function Bubble({ m, total }: { m: Message; total: number }) {
  if (m.role === "candidate") return <div className="bubble bubble-me">{m.text}</div>;
  const label =
    m.kind === "base_question" && m.question_number
      ? `Вопрос ${m.question_number} из ${total}`
      : m.kind === "followup"
        ? "Уточнение"
        : null;
  return (
    <div className={`bubble bubble-bot kind-${m.kind}`}>
      {label && <span className="bubble-label">{label}</span>}
      {m.text}
    </div>
  );
}
