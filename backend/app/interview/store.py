"""Хранилище демо-сессий: в памяти процесса и копия на диске (D-008, D-009).

Копия в storage/demo_sessions/ нужна, чтобы перезапуск сервера (в том числе
`uvicorn --reload` при правке кода) не обрывал начатые сессии. Сессия удаляется
через ttl после последней активности. На этапе 2 хранилище заменится PostgreSQL:
интерфейс (create / get / save) останется тем же.

Файлы — pickle состояния InterviewRunner без модели (её подставляет API при загрузке).
Их пишет и читает только этот сервер; папка storage/ в .gitignore.
"""

from __future__ import annotations

import logging
import os
import pickle
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.interview.runner import InterviewRunner

log = logging.getLogger("app.store")

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "storage" / "demo_sessions"


@dataclass
class SessionEntry:
    token: str
    runner: InterviewRunner
    updated_at: float = field(default_factory=time.time)
    # Один ход за раз: второй запрос, пока модель думает над первым, получит 409.
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    def __init__(
        self,
        ttl_seconds: int = 6 * 3600,
        max_sessions: int = 200,
        persist_dir: Path | None = None,
    ) -> None:
        self.ttl = ttl_seconds
        self.max_sessions = max_sessions
        self.persist_dir = persist_dir
        self._sessions: dict[str, SessionEntry] = {}
        self._lock = threading.Lock()

    # ---------- публичный интерфейс ----------

    def create(self, runner: InterviewRunner) -> SessionEntry:
        with self._lock:
            self._cleanup()
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda e: e.updated_at)
                self._drop(oldest.token)
            entry = SessionEntry(secrets.token_urlsafe(16), runner)
            self._sessions[entry.token] = entry
        self.save(entry)
        return entry

    def get(self, token: str) -> SessionEntry | None:
        if not TOKEN_RE.match(token):
            return None
        with self._lock:
            self._cleanup()
            entry = self._sessions.get(token) or self._load(token)
            if entry:
                entry.updated_at = time.time()
            return entry

    def save(self, entry: SessionEntry) -> None:
        """Записать состояние на диск (после каждого изменения сессии)."""
        entry.updated_at = time.time()
        if not self.persist_dir:
            return
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            path = self.persist_dir / f"{entry.token}.pkl"
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps(entry.runner))
            os.replace(tmp, path)  # атомарно: при сбое не останется половины файла
        except OSError as e:
            log.warning("не удалось сохранить сессию %s: %s", entry.token[:6], e)

    def __len__(self) -> int:
        return len(self._sessions)

    # ---------- внутреннее ----------

    def _path(self, token: str) -> Path | None:
        return self.persist_dir / f"{token}.pkl" if self.persist_dir else None

    def _load(self, token: str) -> SessionEntry | None:
        path = self._path(token)
        if not path or not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.ttl:
            path.unlink(missing_ok=True)
            return None
        try:
            runner = pickle.loads(path.read_bytes())
        except Exception as e:  # повреждённый файл или несовместимая версия кода
            log.warning("не удалось загрузить сессию %s: %s", token[:6], e)
            return None
        entry = SessionEntry(token, runner)
        self._sessions[token] = entry
        return entry

    def _drop(self, token: str) -> None:
        self._sessions.pop(token, None)
        path = self._path(token)
        if path:
            path.unlink(missing_ok=True)

    def _cleanup(self) -> None:
        now = time.time()
        for token in [t for t, e in self._sessions.items() if now - e.updated_at > self.ttl]:
            self._drop(token)
        if self.persist_dir and self.persist_dir.exists():
            for path in self.persist_dir.glob("*.pkl"):
                if now - path.stat().st_mtime > self.ttl:
                    path.unlink(missing_ok=True)


store = SessionStore(persist_dir=DEFAULT_DIR)
