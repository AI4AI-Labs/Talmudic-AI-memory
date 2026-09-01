#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from cursor_adapter import (
    detected_event,
    enrich_payload,
    project_enables_talmudic,
    read_stdin_json,
    run_continuity_script,
    write_json,
)


def _suggestion_from_observer_stdout(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    nested = data.get("hookSpecificOutput")
    if isinstance(nested, dict) and nested.get("additionalContext"):
        return str(nested["additionalContext"])
    return str(data.get("additionalContext") or "")


def main() -> int:
    incoming = read_stdin_json()
    payload = enrich_payload(incoming)
    if not project_enables_talmudic(Path(str(payload.get("cwd") or "."))):
        return 0
    result = run_continuity_script("talmudic_observer.py", payload)
    if result.stderr:
        sys.stderr.write(result.stderr)

    suggestion = _suggestion_from_observer_stdout(result.stdout or "")
    if not suggestion:
        return 0

    event = detected_event(payload)
    flattened = event.strip().lower().replace("_", "").replace("-", "")
    if flattened in {"stop", "subagentstop"}:
        write_json({"followup_message": suggestion})
    else:
        write_json({"additional_context": suggestion})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
