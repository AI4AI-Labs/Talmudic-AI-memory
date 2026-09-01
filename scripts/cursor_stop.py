#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from cursor_adapter import (
    enrich_payload,
    project_enables_talmudic,
    read_stdin_json,
    run_continuity_script,
    write_json,
)


def main() -> int:
    incoming = read_stdin_json()
    status = str(incoming.get("status") or "completed").lower()
    if status in {"aborted", "error"}:
        return 0

    payload = enrich_payload(incoming, default_event="stop")
    if not project_enables_talmudic(Path(str(payload.get("cwd") or "."))):
        return 0
    result = run_continuity_script("talmudic_stop.py", payload)
    if result.stderr:
        sys.stderr.write(result.stderr)

    raw = (result.stdout or "").strip()
    if not raw:
        return 0

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    if not isinstance(data, dict):
        return 0
    if data.get("decision") != "block":
        return 0

    reason = str(data.get("reason") or "").strip()
    if reason:
        write_json({"followup_message": reason})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
