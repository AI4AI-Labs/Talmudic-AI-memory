from __future__ import annotations

import hashlib
import json
from contextlib import AbstractContextManager, nullcontext
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import ContinuityStorage, FileStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Resume:
    workstream_id: str
    checkpoint: int = 0
    status: str = "ACTIVE"
    active_task: str = ""
    next_exact_action: str = ""
    authoritative_markers: dict[str, str] = field(default_factory=dict)
    open_inflight: list[str] = field(default_factory=list)
    last_verified: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    do_not: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=_now)
    ledger_tail: str = ""


class ContinuityError(RuntimeError):
    pass


class TalmudicStore:
    """Talmudic continuity semantics over a pluggable persistence backend."""

    def __init__(
        self,
        root: str | Path = ".talmudic",
        *,
        storage: ContinuityStorage | None = None,
        actor: dict[str, str] | None = None,
    ) -> None:
        self.storage: ContinuityStorage = storage or FileStore(root)
        # Provenance, not authority. Empty values are omitted to keep records compact.
        self.actor = {k: v for k, v in (actor or {}).items() if v}

    @staticmethod
    def _key(workstream_id: str, name: str) -> str:
        return f"workstreams/{workstream_id}/{name}"

    def _meta(self) -> dict[str, Any]:
        return {"at": _now(), **({"author": dict(self.actor)} if self.actor else {})}

    def _lock(self, key: str) -> AbstractContextManager[None]:
        """Advisory cross-process lock spanning a read-check-write critical section.

        Backends that don't implement ``lock`` (e.g. the in-memory test double, or
        SQLiteStore for now) fall back to a no-op — single-process callers are
        unaffected, and this never raises for a backend that lacks the method.
        """
        locker = getattr(self.storage, "lock", None)
        if locker is None:
            return nullcontext()
        return locker(key)

    def init(
        self,
        workstream_id: str,
        *,
        task: str = "",
        next_action: str = "",
        origin: dict[str, Any] | None = None,
    ) -> Resume:
        key = self._key(workstream_id, "resume.json")
        with self._lock(key):
            if self.storage.exists(key):
                raise ContinuityError(f"workstream already exists: {workstream_id}")
            resume = Resume(workstream_id, active_task=task, next_exact_action=next_action)
            self.storage.write_json(key, asdict(resume))
            if origin is not None:
                self.storage.write_json(self._key(workstream_id, "origin.json"), origin)
        self._checkpoint(resume, reason="INIT")
        return resume

    def load_origin(self, workstream_id: str) -> dict[str, Any] | None:
        key = self._key(workstream_id, "origin.json")
        if not self.storage.exists(key):
            return None
        return self.storage.read_json(key)

    def load(self, workstream_id: str) -> Resume:
        key = self._key(workstream_id, "resume.json")
        if not self.storage.exists(key):
            raise ContinuityError(f"unknown workstream: {workstream_id}")
        data = self.storage.read_json(key)
        known = {f.name for f in fields(Resume)}
        return Resume(**{k: v for k, v in data.items() if k in known})

    def save(self, resume: Resume, *, expected_checkpoint: int | None = None, reason: str = "UPDATE") -> Resume:
        with self._lock(self._key(resume.workstream_id, "resume.json")):
            return self._save_locked(resume, expected_checkpoint=expected_checkpoint, reason=reason)

    def _save_locked(self, resume: Resume, *, expected_checkpoint: int | None = None, reason: str = "UPDATE") -> Resume:
        """Same CAS/write as save(), for callers that already hold the resume.json lock.

        flock is per-open-file-description, not per-process: a second self._lock() call
        on the same key from within an already-locked critical section would block
        forever waiting on a lock this same process already holds. Any method that
        needs to mint an id / append a side record and land it in Resume atomically
        must acquire the lock exactly once and call this, not save().
        """
        current = self.load(resume.workstream_id)
        if expected_checkpoint is not None and current.checkpoint != expected_checkpoint:
            raise ContinuityError(f"STALE_CHECKPOINT expected={expected_checkpoint} current={current.checkpoint}")
        resume.checkpoint = current.checkpoint + 1
        resume.updated_at = _now()
        self.storage.write_json(self._key(resume.workstream_id, "resume.json"), asdict(resume))
        self._checkpoint(resume, reason=reason)
        return resume

    def transition(
        self,
        workstream_id: str,
        *,
        expected_checkpoint: int,
        status: str | None = None,
        task: str | None = None,
        next_action: str | None = None,
        verified: list[str] | None = None,
        blockers: list[str] | None = None,
        do_not: list[str] | None = None,
        reason: str = "TRANSITION",
    ) -> Resume:
        r = self.load(workstream_id)
        if r.checkpoint != expected_checkpoint:
            raise ContinuityError(f"STALE_CHECKPOINT expected={expected_checkpoint} current={r.checkpoint}")
        if status is not None:
            allowed = {"ACTIVE", "BLOCKED", "COMPLETE"}
            if status not in allowed:
                raise ContinuityError(f"invalid workstream status: {status}")
            if status == "COMPLETE" and r.open_inflight:
                raise ContinuityError(f"CANNOT_COMPLETE_OPEN_INFLIGHT ids={','.join(r.open_inflight)}")
            r.status = status
        if task is not None:
            r.active_task = task
        if next_action is not None:
            r.next_exact_action = next_action
        if verified is not None:
            r.last_verified = list(verified)
        if blockers is not None:
            r.blockers = list(blockers)
        if do_not is not None:
            r.do_not = list(do_not)
        if r.status == "COMPLETE" and not r.next_exact_action:
            r.next_exact_action = "NONE"
        return self.save(r, expected_checkpoint=expected_checkpoint, reason=reason)

    def _checkpoint(self, resume: Resume, *, reason: str) -> None:
        payload = asdict(resume)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        self.storage.append_jsonl(
            self._key(resume.workstream_id, "checkpoints.jsonl"),
            {"checkpoint": resume.checkpoint, "reason": reason, "resume_sha256": digest, **self._meta()},
        )

    def set_markers(self, workstream_id: str, markers: dict[str, str]) -> Resume:
        r = self.load(workstream_id)
        cp = r.checkpoint
        r.authoritative_markers = dict(markers)
        return self.save(r, expected_checkpoint=cp, reason="MARKERS")

    def marker_kinds(self, workstream_id: str) -> dict[str, str]:
        key = self._key(workstream_id, "marker_kinds.json")
        return self.storage.read_json(key) if self.storage.exists(key) else {}

    def set_marker_kind(self, workstream_id: str, marker_key: str, kind: str) -> dict[str, str]:
        """Canonical, synced record of *how* to verify a marker (its resolver kind).

        Deliberately separate from Resume.authoritative_markers (the expected values)
        and from the resolver's locator: a resolver kind like "this is checked via
        git-head" is a shared team decision, safe to sync. A locator (e.g. an absolute
        repo path) is often machine-specific and is kept local-only by callers, never
        written through this store — see markers.py / the CLI's marker-source command.
        """
        self.load(workstream_id)  # ContinuityError if the workstream doesn't exist yet
        key = self._key(workstream_id, "marker_kinds.json")
        with self._lock(key):
            kinds = self.storage.read_json(key) if self.storage.exists(key) else {}
            kinds[marker_key] = kind
            self.storage.write_json(key, kinds)
            return dict(kinds)

    def verify_resume(self, workstream_id: str, live_markers: dict[str, str]) -> dict[str, Any]:
        r = self.load(workstream_id)
        mismatches = {
            k: {"expected": v, "actual": live_markers.get(k)}
            for k, v in r.authoritative_markers.items()
            if live_markers.get(k) != v
        }
        missing_live = sorted(set(r.authoritative_markers) - set(live_markers))
        recovery = bool(mismatches or missing_live or r.open_inflight)
        return {
            "status": "RECOVERY_REQUIRED" if recovery else "CONTINUE",
            "workstream_status": r.status,
            "checkpoint": r.checkpoint,
            "next_exact_action": r.next_exact_action,
            "mismatches": mismatches,
            "missing_live_markers": missing_live,
            "open_inflight": list(r.open_inflight),
        }

    def open_inflight(self, workstream_id: str, intent: str, expected_effects: list[dict[str, Any]]) -> str:
        resume_key = self._key(workstream_id, "resume.json")
        inflight_key = self._key(workstream_id, "inflight.jsonl")
        with self._lock(resume_key):
            r = self.load(workstream_id)
            if r.status == "COMPLETE":
                raise ContinuityError("cannot open in-flight on COMPLETE workstream")
            cp = r.checkpoint
            existing = self.storage.read_jsonl(inflight_key)
            wid = f"W-{1 + sum(1 for x in existing if x.get('event') == 'OPEN'):04d}"
            self.storage.append_jsonl(
                inflight_key,
                {
                    "event": "OPEN",
                    "id": wid,
                    "intent": intent,
                    "pre_checkpoint": cp,
                    "expected_effects": expected_effects,
                    "status": "OPEN",
                    **self._meta(),
                },
            )
            r.open_inflight.append(wid)
            self._save_locked(r, expected_checkpoint=cp, reason=f"OPEN_INFLIGHT:{wid}")
        return wid

    def close_inflight(self, workstream_id: str, inflight_id: str, *, state: str, evidence: list[str] | None = None) -> Resume:
        allowed = {"VERIFIED", "PARTIAL", "FAILED", "ABORTED", "RECOVERED", "AMBIGUOUS", "ORPHANED"}
        if state not in allowed:
            raise ContinuityError(f"invalid terminal state: {state}")
        resume_key = self._key(workstream_id, "resume.json")
        inflight_key = self._key(workstream_id, "inflight.jsonl")
        with self._lock(resume_key):
            r = self.load(workstream_id)
            if inflight_id not in r.open_inflight:
                raise ContinuityError(f"in-flight is not open: {inflight_id}")
            cp = r.checkpoint
            self.storage.append_jsonl(
                inflight_key,
                {"event": "CLOSE", "id": inflight_id, "status": state, "evidence": evidence or [], **self._meta()},
            )
            r.open_inflight.remove(inflight_id)
            if state not in {"VERIFIED", "RECOVERED"}:
                r.status = "BLOCKED"
                r.blockers.append(f"{inflight_id}:{state}")
            return self._save_locked(r, expected_checkpoint=cp, reason=f"CLOSE_INFLIGHT:{inflight_id}:{state}")

    def add_sugya(
        self,
        workstream_id: str,
        *,
        expected_checkpoint: int,
        title: str,
        premise: str,
        question: str,
        test: str,
        result: str,
        resolution: str,
        caveat: str = "",
        evidence: list[str] | None = None,
        supersedes: list[str] | None = None,
    ) -> str:
        """Append a Sugya and land it in Resume (ledger_tail, checkpoint) atomically.

        Requires expected_checkpoint and mints the S-#### id under the same lock as the
        Resume CAS: without this, two agents merging via Git can each independently
        compute the same next id (e.g. both mint S-0001 from a base with zero Sugyot)
        and append it with different content. Neither resume.json (untouched by the old
        code path) nor Git (a clean two-way append-only merge) would ever signal the
        collision — the id space itself would silently be inconsistent with content.
        """
        resume_key = self._key(workstream_id, "resume.json")
        sugya_key = self._key(workstream_id, "sugya.jsonl")
        with self._lock(resume_key):
            r = self.load(workstream_id)
            if r.checkpoint != expected_checkpoint:
                raise ContinuityError(f"STALE_CHECKPOINT expected={expected_checkpoint} current={r.checkpoint}")
            rows = self.storage.read_jsonl(sugya_key)
            sid = f"S-{len(rows)+1:04d}"
            self.storage.append_jsonl(
                sugya_key,
                {
                    "id": sid,
                    "title": title,
                    "status": "RESOLVED",
                    "premise": premise,
                    "question": question,
                    "test": test,
                    "observed_result": result,
                    "bounded_resolution": resolution,
                    "caveat": caveat,
                    "evidence_refs": evidence or [],
                    "supersedes": supersedes or [],
                    **self._meta(),
                },
            )
            r.ledger_tail = sid
            self._save_locked(r, expected_checkpoint=expected_checkpoint, reason=f"SUGYA:{sid}")
        return sid

    BREADCRUMB_STATES = {"DECIDED", "APPLIED", "VERIFIED", "BLOCKED", "SUPERSEDED", "REVERTED"}

    def add_breadcrumb(
        self,
        workstream_id: str,
        *,
        expected_checkpoint: int,
        state: str,
        what: str,
        why: str = "",
        evid: str = "",
        impact: str = "",
        supersedes: str = "",
    ) -> str:
        """Append a lightweight Rationale Breadcrumb: routine progress, not a full Sugya.

        Row shape deliberately omits empty optional fields (mirrors _meta()'s falsy-author
        omission). json.dumps(row) is substring-scanned elsewhere (preflight._classify), and
        an always-present-but-empty key like "supersedes": "" still trips a naive "supersed"
        in text check regardless of content — see the historical fix to that classifier.

        Id-minting, the append, and the Resume CAS all happen under one lock acquisition
        (see add_sugya's docstring for why): the staleness check runs *before* anything is
        written, so a rejected stale call never leaves an orphaned, unreferenced breadcrumb
        behind the way append-then-check would.
        """
        if state not in self.BREADCRUMB_STATES:
            raise ContinuityError(f"invalid breadcrumb state: {state}")
        resume_key = self._key(workstream_id, "resume.json")
        bc_key = self._key(workstream_id, "breadcrumb.jsonl")
        with self._lock(resume_key):
            r = self.load(workstream_id)
            if r.checkpoint != expected_checkpoint:
                raise ContinuityError(f"STALE_CHECKPOINT expected={expected_checkpoint} current={r.checkpoint}")
            rows = self.storage.read_jsonl(bc_key)
            rid = f"R-{len(rows)+1:04d}"
            row: dict[str, Any] = {"id": rid, "state": state, "what": what}
            if why:
                row["why"] = why
            if evid:
                row["evid"] = evid
            if impact:
                row["impact"] = impact
            if supersedes:
                row["supersedes"] = supersedes
            row.update(self._meta())
            self.storage.append_jsonl(bc_key, row)
            r.ledger_tail = rid
            self._save_locked(r, expected_checkpoint=expected_checkpoint, reason=f"BREADCRUMB:{rid}")
        return rid
