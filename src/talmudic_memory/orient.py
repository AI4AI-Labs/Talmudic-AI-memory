from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .core import ContinuityError, TalmudicStore
from .index import GemaraIndex
from .storage import FileStore


@dataclass
class OrientationResult:
    """Compact request-time packet: what canonical history already says about a task.

    This is the missing read-side routing layer: search prior canonical work for the
    current task *before* acting, instead of investigating/testing first and only
    discovering prior Gemara later via an explicit Recall.
    """

    query: str
    workstream_id: str | None
    resume: dict[str, Any] | None
    prior_work: list[dict[str, Any]]
    open_inflight: list[dict[str, Any]]
    blockers: list[str]
    status: str
    suggested_action: str


def open_inflight_detail(canonical_root: Path, workstream_id: str, open_ids: list[str]) -> list[dict[str, Any]]:
    if not open_ids:
        return []
    rows = FileStore(canonical_root).read_jsonl(f"workstreams/{workstream_id}/inflight.jsonl")
    opens = {row["id"]: row for row in rows if row.get("event") == "OPEN"}
    return [
        {
            "id": wid,
            "intent": opens.get(wid, {}).get("intent", ""),
            "expected_effects": opens.get(wid, {}).get("expected_effects", []),
        }
        for wid in open_ids
    ]


def orient(
    *,
    query: str,
    canonical_root: Path,
    index_path: Path,
    workstream_id: str | None,
    limit: int = 8,
) -> OrientationResult:
    """Combine an index search over the task with the workstream's Resume/In-Flight
    state into one compact packet, so an agent checks prior canonical work first.

    Read-only with respect to canonical Gemara: this never bootstraps, clones, pulls,
    pushes, or mutates Resume/checkpoints/In-Flight/Sugya. Callers own syncing the
    workspace (git pull) before calling this, per the sync-before-consume policy.
    """
    index = GemaraIndex(index_path)
    if not index.status(canonical_root).get("fresh"):
        index.build(canonical_root)

    prior_work = index.search(query, limit=limit, workstream=workstream_id)

    resume: dict[str, Any] | None = None
    open_inflight: list[dict[str, Any]] = []
    blockers: list[str] = []
    if workstream_id:
        try:
            r = TalmudicStore(storage=FileStore(canonical_root)).load(workstream_id)
        except ContinuityError:
            r = None
        if r is not None:
            resume = asdict(r)
            blockers = list(r.blockers)
            open_inflight = open_inflight_detail(canonical_root, workstream_id, r.open_inflight)

    if open_inflight:
        status = "BLOCKED_OPEN_INFLIGHT"
        suggested_action = (
            "Reconcile open In-Flight before any new material write: "
            + ", ".join(item["id"] for item in open_inflight)
        )
    elif blockers:
        status = "BLOCKED"
        suggested_action = "Resolve recorded blockers before continuing: " + ", ".join(blockers)
    elif prior_work:
        status = "PRIOR_WORK_FOUND"
        suggested_action = "Related canonical work exists. Review it and verify only what is missing/changed."
    else:
        status = "NO_PRIOR_WORK"
        suggested_action = "No directly relevant canonical work found for this task. Proceed."

    return OrientationResult(
        query=query,
        workstream_id=workstream_id,
        resume=resume,
        prior_work=prior_work,
        open_inflight=open_inflight,
        blockers=blockers,
        status=status,
        suggested_action=suggested_action,
    )
