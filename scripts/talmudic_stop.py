from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from talmudic_memory.observer import SUGGESTION, ObserverSpool, is_significant


#: Ordinary tool lines *or* chat-only Stop cycles before a one-line suggestion.
#: Chat-only research has no tool spool; Stop still fires every turn. Override
#: with TALMUDIC_NUDGE_EVERY. A Remember resets both counters.
DEFAULT_NUDGE_EVERY = 12


def _payload() -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def nudge_every() -> int:
    raw = os.environ.get("TALMUDIC_NUDGE_EVERY", str(DEFAULT_NUDGE_EVERY))
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_NUDGE_EVERY
    return parsed if parsed > 0 else DEFAULT_NUDGE_EVERY


def _spool_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _new_look_here(rows: list[dict], last: int) -> bool:
    for row in rows[last:]:
        if row.get("significant") is True:
            return True
        if is_significant(
            tool_name=str(row.get("tool_name") or ""),
            event=str(row.get("event") or ""),
        ):
            return True
    return False


def main() -> int:
    data = _payload()
    if data.get("stop_hook_active"):
        return 0

    cwd = Path(data.get("cwd") or Path.cwd()).resolve()
    spool = ObserverSpool(cwd / ".talmudic" / "cache" / "observer.jsonl")
    rows = _spool_rows(spool.path)
    count = len(rows)
    state = spool.read_nudge_state()
    last = state["nudge_at_count"]
    if count < last:
        last = 0
    stops = state["stops_since_bookmark"] + 1
    every = nudge_every()

    look_here = _new_look_here(rows, last)
    due = look_here or (count - last >= every) or (stops >= every)
    if not due:
        spool.set_watermark(last, stops_since_bookmark=stops)
        return 0

    spool.set_watermark(count, stops_since_bookmark=0)
    print(json.dumps({"decision": "block", "reason": SUGGESTION}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
