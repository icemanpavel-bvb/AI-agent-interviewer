"""Хранилище сессий интервью в памяти процесса — для демо и тестов (D-008).

Сессия живёт, пока работает сервер, и удаляется через ttl после последней активности.
На этапах 1–2 заменится сохранением в PostgreSQL: интерфейс (create / get) останется тем же.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

from app.interview.runner import InterviewRunner


@dataclass
class SessionEntry:
    token: str
    runner: InterviewRunner
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    # Один ход за раз: второй запрос, пока модель думает над первым, получит 409.
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    def __init__(self, ttl_seconds: int = 6 * 3600, max_sessions: int = 200) -> None:
        self.ttl = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, SessionEntry] = {}
        self._lock = threading.Lock()

    def create(self, runner: InterviewRunner) -> SessionEntry:
        with self._lock:
            self._cleanup()
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda e: e.updated_at)
                del self._sessions[oldest.token]
            entry = SessionEntry(secrets.token_urlsafe(16), runner)
            self._sessions[entry.token] = entry
            return entry

    def get(self, token: str) -> SessionEntry | None:
        with self._lock:
            self._cleanup()
            entry = self._sessions.get(token)
            if entry:
                entry.updated_at = time.monotonic()
            return entry

    def __len__(self) -> int:
        return len(self._sessions)

    def _cleanup(self) -> None:
        now = time.monotonic()
        for token in [t for t, e in self._sessions.items() if now - e.updated_at > self.ttl]:
            del self._sessions[token]


store = SessionStore()
