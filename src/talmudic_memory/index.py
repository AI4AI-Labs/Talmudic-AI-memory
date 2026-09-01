from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INDEX_SCHEMA_VERSION = 1
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "for", "from", "how",
    "i", "in", "into", "is", "it", "not", "of", "on", "or", "our", "that", "the", "this", "through",
    "to", "was", "we", "were", "what", "when", "where", "why", "with", "itself", "itself", "decide", "decided",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_files(canonical_root: Path) -> list[Path]:
    ws = canonical_root / "workstreams"
    if not ws.exists():
        return []
    out: list[Path] = []
    for path in ws.rglob("*"):
        if path.is_file() and path.name in {
            "resume.json",
            "checkpoints.jsonl",
            "inflight.jsonl",
            "sugya.jsonl",
            "breadcrumb.jsonl",
            "origin.json",
        }:
            out.append(path)
    return sorted(out)


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(path.read_text(encoding="utf-8"))]


def _kind(path: Path) -> str:
    return {
        "resume.json": "resume",
        "checkpoints.jsonl": "checkpoint",
        "inflight.jsonl": "inflight",
        "sugya.jsonl": "sugya",
        "breadcrumb.jsonl": "breadcrumb",
        "origin.json": "origin",
    }[path.name]


def _record_id(kind: str, row: dict[str, Any], ordinal: int) -> str:
    if row.get("id"):
        return str(row["id"])
    if kind == "checkpoint" and row.get("checkpoint") is not None:
        return f"C-{row['checkpoint']}"
    if kind == "resume":
        return "RESUME"
    if kind == "origin":
        return "ORIGIN"
    return f"{kind.upper()}-{ordinal:04d}"


def _text(row: dict[str, Any]) -> str:
    preferred = [
        "title", "active_task", "next_exact_action", "intent", "question", "premise",
        "test", "observed_result", "bounded_resolution", "caveat", "reason", "status",
        "what", "why", "impact",
    ]
    parts: list[str] = []
    for key in preferred:
        value = row.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
    pointers = row.get("pointers")
    if isinstance(pointers, list):
        for item in pointers:
            if not isinstance(item, dict):
                continue
            for key in ("path", "heading", "kind"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    parts.append(value)
    git = row.get("git")
    if isinstance(git, dict):
        for key in ("branch", "head", "origin"):
            value = git.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
        subjects = git.get("recent_subjects")
        if isinstance(subjects, list):
            parts.extend(str(item) for item in subjects if isinstance(item, str) and item)
    manifest = row.get("manifest")
    if isinstance(manifest, dict):
        for key in ("name", "description"):
            value = manifest.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
    return "\n".join(parts)


def _terms(query: str) -> list[str]:
    tokens = [t.lower() for t in re.findall(r"[\w-]+", query, flags=re.UNICODE) if len(t) >= 2]
    useful = [t for t in tokens if t not in STOPWORDS]
    return useful or tokens


def _score(query: str, row: sqlite3.Row) -> float:
    terms = _terms(query)
    if not terms:
        return 0.0
    title = str(row["title"] or "").lower()
    text = str(row["text"] or "").lower()
    payload = str(row["payload"] or "").lower()
    combined = f"{title}\n{text}\n{payload}"
    phrase = query.strip().lower()
    score = 0.0
    if phrase and phrase in combined:
        score += 25.0
    hits = 0
    for term in terms:
        if term in combined:
            hits += 1
            score += 2.0
            if term in title:
                score += 3.0
            elif term in text:
                score += 1.0
    score += 8.0 * (hits / len(terms))
    if row["kind"] == "sugya":
        score += 0.5
    return score


@dataclass
class IndexResult:
    sources_scanned: int
    sources_changed: int
    records_indexed: int
    index_path: str


class GemaraIndex:
    """Rebuildable local SQLite index over canonical Talmudic records.

    The index is never authoritative. It can always be discarded/rebuilt from
    canonical Git/shared/local workstream records.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (
                    path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    record_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS records (
                    source_path TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    workstream_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL DEFAULT '',
                    payload TEXT NOT NULL,
                    PRIMARY KEY(source_path, ordinal)
                );
                CREATE INDEX IF NOT EXISTS idx_records_workstream_kind ON records(workstream_id, kind);
                CREATE INDEX IF NOT EXISTS idx_records_record_id ON records(record_id);
                """
            )
            conn.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(INDEX_SCHEMA_VERSION),),
            )
            conn.commit()

    def build(self, canonical_root: str | Path, *, force: bool = False) -> IndexResult:
        canonical_root = Path(canonical_root)
        self._ensure_schema()
        files = _source_files(canonical_root)
        changed = 0
        indexed = 0
        live_rel: set[str] = set()
        with self._connect() as conn:
            for path in files:
                rel = path.relative_to(canonical_root).as_posix()
                live_rel.add(rel)
                digest = _sha256(path)
                old = conn.execute("SELECT sha256 FROM sources WHERE path=?", (rel,)).fetchone()
                if old is not None and old["sha256"] == digest and not force:
                    indexed += int(conn.execute("SELECT COUNT(*) FROM records WHERE source_path=?", (rel,)).fetchone()[0])
                    continue
                changed += 1
                rows = _rows(path)
                parts = rel.split("/")
                workstream_id = "/".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
                kind = _kind(path)
                conn.execute("DELETE FROM records WHERE source_path=?", (rel,))
                for ordinal, row in enumerate(rows, start=1):
                    conn.execute(
                        "INSERT INTO records(source_path, ordinal, workstream_id, kind, record_id, title, text, payload) "
                        "VALUES(?,?,?,?,?,?,?,?)",
                        (
                            rel, ordinal, workstream_id, kind, _record_id(kind, row, ordinal),
                            str(row.get("title") or ""), _text(row), json.dumps(row, sort_keys=True),
                        ),
                    )
                conn.execute(
                    "INSERT INTO sources(path, sha256, record_count) VALUES(?,?,?) "
                    "ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256, record_count=excluded.record_count",
                    (rel, digest, len(rows)),
                )
                indexed += len(rows)
            existing = [r[0] for r in conn.execute("SELECT path FROM sources").fetchall()]
            for rel in existing:
                if rel not in live_rel:
                    conn.execute("DELETE FROM records WHERE source_path=?", (rel,))
                    conn.execute("DELETE FROM sources WHERE path=?", (rel,))
                    changed += 1
            conn.commit()
        return IndexResult(len(files), changed, indexed, str(self.path))

    def rebuild(self, canonical_root: str | Path) -> IndexResult:
        if self.path.exists():
            with self._connect() as conn:
                conn.executescript(
                    """
                    DROP TABLE IF EXISTS records;
                    DROP TABLE IF EXISTS sources;
                    DROP TABLE IF EXISTS meta;
                    """
                )
                conn.commit()
        return self.build(canonical_root, force=True)

    def status(self, canonical_root: str | Path) -> dict[str, Any]:
        canonical_root = Path(canonical_root)
        if not self.path.exists():
            return {"exists": False, "fresh": False, "index_path": str(self.path), "reason": "INDEX_MISSING"}
        try:
            with self._connect() as conn:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                schema = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                indexed = {r[0]: r[1] for r in conn.execute("SELECT path, sha256 FROM sources").fetchall()}
                record_count = int(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0])
        except sqlite3.DatabaseError as exc:
            return {"exists": True, "fresh": False, "index_path": str(self.path), "integrity": "FAIL", "error": str(exc)}
        current = {p.relative_to(canonical_root).as_posix(): _sha256(p) for p in _source_files(canonical_root)}
        stale = sorted(k for k in set(current) | set(indexed) if current.get(k) != indexed.get(k))
        return {
            "exists": True,
            "fresh": not stale and integrity == "ok" and schema is not None and int(schema[0]) == INDEX_SCHEMA_VERSION,
            "integrity": integrity,
            "schema_version": int(schema[0]) if schema else None,
            "sources": len(indexed),
            "records": record_count,
            "stale_sources": stale,
            "index_path": str(self.path),
        }

    def search(self, query: str, *, limit: int = 20, workstream: str | None = None) -> list[dict[str, Any]]:
        """Token-ranked lexical recall suitable for natural-language questions.

        This deliberately stays local/deterministic for alpha: no embeddings, remote
        model call, or semantic filter can hide canonical history. Multi-term questions
        are matched by term coverage instead of requiring an exact substring.
        """
        if not self.path.exists():
            return []
        terms = _terms(query)
        if not terms:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        for term in terms:
            pattern = f"%{term}%"
            clauses.append("(title LIKE ? OR text LIKE ? OR payload LIKE ?)")
            params.extend([pattern, pattern, pattern])
        sql = "SELECT workstream_id, kind, record_id, title, text, payload FROM records WHERE (" + " OR ".join(clauses) + ")"
        if workstream:
            sql += " AND workstream_id = ?"
            params.append(workstream)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        ranked = sorted(((row, _score(query, row)) for row in rows), key=lambda pair: (-pair[1], pair[0]["workstream_id"], pair[0]["record_id"]))
        out: list[dict[str, Any]] = []
        for row, score in ranked[:limit]:
            item = dict(row)
            item["score"] = round(score, 3)
            out.append(item)
        return out
