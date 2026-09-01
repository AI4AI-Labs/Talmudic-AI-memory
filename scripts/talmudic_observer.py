from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from talmudic_memory.observer import (
    SUGGESTION,
    ObserverSpool,
    is_post_like_event,
    is_significant,
)


SELF_TOOL_NAMES = {"agent", "task", "sendmessage"}


def _is_talmudic_command(command: str) -> bool:
    low = command.strip().lower()
    return low.startswith("talmudic ") or "-m talmudic_memory.cli" in low


def _tool_input(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("tool_input")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _emit_suggestion(event: str) -> None:
    print(
        json.dumps(
            {
                "additionalContext": SUGGESTION,
                "hookSpecificOutput": {
                    "hookEventName": event or "PostToolUse",
                    "additionalContext": SUGGESTION,
                },
            }
        )
    )


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {"raw": raw[:4000]}

    cwd = Path(data.get("cwd") or Path.cwd()).resolve()
    event = str(data.get("hook_event_name") or data.get("event") or "unknown")
    session_id = str(data.get("session_id") or data.get("conversation_id") or "")
    model = str(data.get("model_id") or data.get("model") or "")
    tool_name = str(data.get("tool_name") or "")
    command = str(data.get("command") or "")
    tool_input = _tool_input(data)
    significant = is_significant(tool_name=tool_name, event=event, tool_input=tool_input)

    # Talmudic machinery must never create new workstream delta merely by
    # documenting/maintaining itself. This prevents feedback loops where a
    # scribe invocation or continuity CLI call causes another boundary pass.
    # Plan/subagent-stop boundaries are the exception: they are look-here events.
    if tool_name.strip().lower() in SELF_TOOL_NAMES and not significant:
        return 0
    if command and _is_talmudic_command(command):
        return 0

    compact: dict[str, object] = {
        "event": event,
        "session_id": session_id,
        "model": model,
    }
    for key in ("tool_name", "command", "file_path", "status", "reason"):
        if key in data and data[key] is not None:
            compact[key] = str(data[key])[:2000]
    if significant:
        compact["significant"] = True

    spool = ObserverSpool(cwd / ".talmudic" / "cache" / "observer.jsonl")
    spool.append(compact)

    if significant and is_post_like_event(event):
        spool.set_watermark(spool.line_count())
        _emit_suggestion(event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
