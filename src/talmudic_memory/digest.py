from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import ContinuityError, Resume, TalmudicStore
from .orient import open_inflight_detail
from .storage import FileStore

#: Default cap on the *full* render's UTF-8 byte size before falling back to
#: the light (titles-only) render. Keeps a first-boot injection bounded even
#: on a workstream with a long Sugya history.
DEFAULT_BUDGET_BYTES = 8000


#: How many of the most recent breadcrumbs to render in the full digest. Breadcrumbs
#: are the frequent/routine write path, so unlike Sugyot (all rendered) only a tail
#: is shown - the point is "what just happened," not the full history (that's what
#: recall/orient are for).
RECENT_BREADCRUMBS = 5


def _sugyot(canonical_root: Path, workstream_id: str) -> list[dict[str, Any]]:
    return FileStore(canonical_root).read_jsonl(f"workstreams/{workstream_id}/sugya.jsonl")


def _breadcrumbs(canonical_root: Path, workstream_id: str) -> list[dict[str, Any]]:
    return FileStore(canonical_root).read_jsonl(f"workstreams/{workstream_id}/breadcrumb.jsonl")


def remember_from_line(origin: dict[str, Any] | None) -> str | None:
    """One digest line for the origin epoch. Dates/commits are provenance, not sort keys."""
    if not origin:
        return None
    surveyed = origin.get("surveyed_at")
    surveyed_text = surveyed.strip() if isinstance(surveyed, str) else ""
    git = origin.get("git")
    head = ""
    if isinstance(git, dict):
        raw_head = git.get("head")
        head = raw_head.strip() if isinstance(raw_head, str) else ""
    if surveyed_text and head:
        return f"Gemara remembers from {surveyed_text} at {head}"
    if surveyed_text:
        return f"Gemara remembers from {surveyed_text}"
    if head:
        return f"Gemara remembers from {head}"
    return None


def _origin(canonical_root: Path, workstream_id: str) -> dict[str, Any] | None:
    store = FileStore(canonical_root)
    key = f"workstreams/{workstream_id}/origin.json"
    if not store.exists(key):
        return None
    return store.read_json(key)


def _render(
    resume: Resume,
    sugyot: list[dict[str, Any]],
    breadcrumbs: list[dict[str, Any]],
    open_inflight: list[dict[str, Any]],
    origin: dict[str, Any] | None,
    *,
    full: bool,
) -> str:
    lines = [f"# Talmudic orientation — {resume.workstream_id}", ""]
    lines.append(f"Status: {resume.status} | checkpoint {resume.checkpoint}")
    if resume.ledger_tail:
        lines.append(f"Ledger tail: {resume.ledger_tail}")
    lines.append(f"Active task: {resume.active_task or '(none)'}")
    lines.append(f"Next action: {resume.next_exact_action or '(none)'}")
    if resume.blockers:
        lines.append(f"Blockers: {', '.join(resume.blockers)}")
    epoch = remember_from_line(origin)
    if epoch:
        lines.append(epoch)
    if origin is not None:
        pointers = origin.get("pointers") or []
        lines.append("")
        if pointers:
            lines.append("Project-map pointers:")
            for item in pointers:
                path = str(item.get("path") or "")
                kind = str(item.get("kind") or "")
                heading = str(item.get("heading") or "")
                extra = f" [{kind}]" if kind else ""
                if heading:
                    lines.append(f"- {path}{extra} {heading}")
                else:
                    lines.append(f"- {path}{extra}")
        else:
            lines.append("Project map: no pointer files found.")

    if open_inflight:
        lines.append("")
        lines.append("Open In-Flight:")
        for item in open_inflight:
            lines.append(f"- {item['id']}: {item['intent']}")

    if sugyot:
        lines.append("")
        lines.append(f"Sugyot ({len(sugyot)}):")
        for s in sugyot:
            lines.append(f"- {s.get('id', '')} {s.get('title', '')}")
            if full:
                if s.get("question"):
                    lines.append(f"  Q: {s['question']}")
                if s.get("bounded_resolution"):
                    lines.append(f"  Resolution: {s['bounded_resolution']}")
                if s.get("caveat"):
                    lines.append(f"  Caveat: {s['caveat']}")

    if full and breadcrumbs:
        recent = breadcrumbs[-RECENT_BREADCRUMBS:]
        lines.append("")
        lines.append(f"Recent breadcrumbs ({len(recent)} of {len(breadcrumbs)}):")
        for b in recent:
            lines.append(f"- {b.get('id', '')} [{b.get('state', '')}] {b.get('what', '')}")
            if b.get("why"):
                lines.append(f"  Why: {b['why']}")

    lines.append("")
    return "\n".join(lines)


def render_session_digest(
    canonical_root: Path,
    workstream_id: str | None,
    *,
    prefer_full: bool,
    budget_bytes: int = DEFAULT_BUDGET_BYTES,
) -> tuple[str, str]:
    """Render a compact workstream digest for operators and debug.

    Read-only with respect to canonical Gemara: this never bootstraps, clones,
    pulls, pushes, or mutates Resume/checkpoints/In-Flight/Sugya.

    SessionStart does **not** inject this text. The hook tells the agent to
    search the index (``orient`` / ``recall``) so a workstream with thousands of
    Sugyot is not dumped into every new chat.

    ``prefer_full=True`` attempts a full render — Resume + open In-Flight +
    every Sugya's question/resolution/caveat — and falls back to the light
    render (titles only) if that exceeds ``budget_bytes``. ``prefer_full=False``
    always renders light.

    Returns ``(mode_used, text)`` where ``mode_used`` is one of
    ``"full"``, ``"light"``, ``"none"``.
    """
    if not workstream_id:
        return (
            "none",
            "Talmudic Memory: no active workstream yet for this project. "
            "Use /talmudic-init to map this project and create one.",
        )

    try:
        resume = TalmudicStore(storage=FileStore(canonical_root)).load(workstream_id)
    except ContinuityError:
        return "none", f"Talmudic Memory: workstream '{workstream_id}' not found."

    sugyot = _sugyot(canonical_root, workstream_id)
    breadcrumbs = _breadcrumbs(canonical_root, workstream_id)
    open_inflight = open_inflight_detail(canonical_root, workstream_id, resume.open_inflight)
    origin = _origin(canonical_root, workstream_id)

    if prefer_full:
        full_text = _render(resume, sugyot, breadcrumbs, open_inflight, origin, full=True)
        if len(full_text.encode("utf-8")) <= budget_bytes:
            return "full", full_text

    return "light", _render(resume, sugyot, breadcrumbs, open_inflight, origin, full=False)
