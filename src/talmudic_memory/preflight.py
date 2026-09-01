from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .index import GemaraIndex


@dataclass
class PreflightResult:
    status: str
    previous_cursor: int
    current_cursor: int
    changes_seen: int
    relevant_changes: list[dict[str, Any]]
    blocking_changes: list[dict[str, Any]]
    next_action: str


def _cursor_path(project_root: Path, actor_key: str) -> Path:
    safe = actor_key.replace("/", "_").replace("\\", "_").replace(":", "_") or "anonymous"
    return project_root / ".talmudic" / "cache" / "cursors" / f"{safe}.json"


def _read_cursor(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("cursor", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _write_cursor(path: Path, cursor: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cursor": cursor}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# Prose fields worth scanning for concept keywords. Deliberately values only, via
# dict.get() on named fields, never json.dumps(row) — serializing the whole row
# would scan key *names* too, so an unrelated key present-but-empty (e.g. an empty
# "blockers": [] or "supersedes": "") used to trip this classifier regardless of
# content. That bug was live in production: every Sugya always carries a
# "supersedes" key (see add_sugya), so every existing Sugya record misclassified
# as SUPERSESSION independent of whether it actually superseded anything.
_PROSE_FIELDS = (
    "title", "premise", "question", "test", "observed_result", "bounded_resolution",
    "caveat", "what", "why", "impact",
)
_TERMINAL_INFLIGHT_FAILURE_STATES = {"FAILED", "ABORTED", "BLOCKED", "AMBIGUOUS", "ORPHANED"}


def _prose(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(f) or "") for f in _PROSE_FIELDS).lower()


def _classify(row: dict[str, Any], kind: str) -> tuple[str, bool]:
    """Classify one indexed record's importance for preflight review.

    Inspects structured fields/kind first, prose second (values of a curated field
    list, never the whole serialized payload) — see _PROSE_FIELDS docstring above
    for why that distinction matters.
    """
    prose = _prose(row)
    reason = str(row.get("reason") or "")
    breadcrumb_state = str(row.get("state") or "")  # only meaningful for kind == "breadcrumb"
    inflight_terminal_state = reason.split(":")[-1] if kind == "checkpoint" else ""

    has_do_not = bool(row.get("do_not"))
    recovery_required = "recovery_required" in prose or "recovery required" in prose
    breaking_change = "breaking" in prose
    if has_do_not or recovery_required or breaking_change or any(t in prose for t in ("schema", "contract", "migration")):
        return "CRITICAL_CHANGE", bool(has_do_not or recovery_required or breaking_change)

    has_supersedes = bool(row.get("supersedes"))
    if has_supersedes or breadcrumb_state == "SUPERSEDED" or any(t in prose for t in ("supersed", "deprecated", "replaced")):
        return "SUPERSESSION", False

    has_blockers = bool(row.get("blockers"))
    is_blocked = (
        has_blockers
        or breadcrumb_state == "BLOCKED"
        or inflight_terminal_state in _TERMINAL_INFLIGHT_FAILURE_STATES
    )
    if is_blocked:
        return "BLOCKER", True

    return "GENERAL_CHANGE", False


def _all_index_records(index: GemaraIndex) -> list[dict[str, Any]]:
    if not index.path.exists():
        return []
    with index._connect() as conn:  # internal local cache access only
        rows = conn.execute(
            "SELECT rowid AS cursor, workstream_id, kind, record_id, title, payload FROM records ORDER BY rowid"
        ).fetchall()
    return [dict(r) for r in rows]


def run_preflight(*, project_root: Path, canonical_root: Path, index_path: Path, actor_key: str,
                  advance: bool = True) -> PreflightResult:
    index = GemaraIndex(index_path)
    if not index.status(canonical_root).get("fresh"):
        index.build(canonical_root)

    records = _all_index_records(index)
    current = int(records[-1]["cursor"]) if records else 0
    cursor_file = _cursor_path(project_root, actor_key)
    previous = _read_cursor(cursor_file)
    delta = [r for r in records if int(r["cursor"]) > previous]

    relevant: list[dict[str, Any]] = []
    blocking: list[dict[str, Any]] = []
    for record in delta:
        try:
            payload = json.loads(record.get("payload") or "{}")
        except json.JSONDecodeError:
            payload = {}
        category, is_blocking = _classify(payload, record["kind"])
        item = {
            "cursor": int(record["cursor"]),
            "workstream_id": record["workstream_id"],
            "kind": record["kind"],
            "record_id": record["record_id"],
            "title": record.get("title") or "",
            "category": category,
        }
        relevant.append(item)
        if is_blocking:
            blocking.append(item)

    if advance and not blocking:
        _write_cursor(cursor_file, current)

    status = "BLOCKED" if blocking else ("READY_WITH_CHANGES" if relevant else "READY")
    next_action = "RECONCILE_BLOCKING_CHANGE" if blocking else ("REVIEW_DELTA" if relevant else "CONTINUE")
    return PreflightResult(status, previous, current, len(delta), relevant, blocking, next_action)
