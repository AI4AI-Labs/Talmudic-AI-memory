from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator, Protocol

if sys.platform == "win32":  # pragma: no cover - exercised only on Windows CI
    import msvcrt
else:
    import fcntl


class ContinuityStorage(Protocol):
    """Minimal persistence contract used by the Talmudic continuity core."""

    def exists(self, key: str) -> bool: ...

    def read_json(self, key: str) -> dict[str, Any]: ...

    def write_json(self, key: str, data: dict[str, Any]) -> None: ...

    def append_jsonl(self, key: str, data: dict[str, Any]) -> None: ...

    def read_jsonl(self, key: str) -> list[dict[str, Any]]: ...


@contextlib.contextmanager
def _flock(path: Path) -> Iterator[None]:
    """Cross-process advisory exclusive lock, stdlib-only (no third-party dependency).

    Spans a read-check-write critical section so two concurrent writers cannot both
    pass a staleness check before either has written (TOCTOU). Released automatically
    if the holding process dies, since the OS releases file locks on file-descriptor
    close/process exit either way.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as fh:
        if sys.platform == "win32":  # pragma: no cover - exercised only on Windows CI
            if fh.tell() == 0:
                fh.write(b"\0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


class FileStore:
    """Atomic local-filesystem implementation of ContinuityStorage."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def lock(self, key: str):
        """Advisory exclusive lock scoped to one logical key (e.g. a resume.json path).

        Used by TalmudicStore to make its read-check-write CAS sequence atomic across
        processes. Other ContinuityStorage backends may omit this method entirely;
        callers must treat it as optional (``getattr(storage, "lock", None)``).
        """
        return _flock(self._path(key).with_suffix(self._path(key).suffix + ".lock"))

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def read_json(self, key: str) -> dict[str, Any]:
        return json.loads(self._path(key).read_text(encoding="utf-8"))

    def write_json(self, key: str, data: dict[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name, dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def append_jsonl(self, key: str, data: dict[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, sort_keys=True) + "\n")

    def read_jsonl(self, key: str) -> list[dict[str, Any]]:
        path = self._path(key)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class SQLiteStore:
    """Zero-config local durable store using Python's built-in sqlite3.

    The core still addresses records by logical keys, so callers do not need to know
    whether persistence is file-backed or SQLite-backed.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS documents (key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_key_seq ON events(key, seq)")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30)

    def exists(self, key: str) -> bool:
        with self._connect() as conn:
            return conn.execute("SELECT 1 FROM documents WHERE key = ?", (key,)).fetchone() is not None

    def read_json(self, key: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM documents WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise FileNotFoundError(key)
        return json.loads(row[0])

    def write_json(self, key: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents(key, payload) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload",
                (key, payload),
            )
            conn.commit()

    def append_jsonl(self, key: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data, sort_keys=True)
        with self._connect() as conn:
            conn.execute("INSERT INTO events(key, payload) VALUES (?, ?)", (key, payload))
            conn.commit()

    def read_jsonl(self, key: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM events WHERE key = ? ORDER BY seq", (key,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
