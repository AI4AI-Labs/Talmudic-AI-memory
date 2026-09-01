from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _flat(value: str) -> str:
    return value.strip().lower().replace("_", "").replace("-", "")


#: Host tools that usually mean a decision or plan just became visible.
#: Not every Shell/Write. Task/Agent stay excluded to avoid nested-agent loops.
SIGNIFICANT_TOOLS = frozenset({
    "exitplanmode",
    "enterplanmode",
    "createplan",
    "updateplan",
    "switchmode",
})

SIGNIFICANT_EVENTS = frozenset({
    "subagentstop",
})

SUGGESTION = "Talmudic: Remember this if a future agent would miss it."


def is_significant(*, tool_name: str = "", event: str = "", tool_input: dict[str, Any] | None = None) -> bool:
    ev = _flat(event)
    if ev in SIGNIFICANT_EVENTS:
        return True
    tool = _flat(tool_name)
    if tool in {"exitplanmode", "enterplanmode", "createplan", "updateplan"}:
        return True
    if tool == "switchmode":
        incoming = tool_input if isinstance(tool_input, dict) else {}
        target = _flat(str(
            incoming.get("target_mode_id")
            or incoming.get("mode")
            or incoming.get("target_mode")
            or ""
        ))
        return "plan" in target
    return False


def is_post_like_event(event: str) -> bool:
    ev = _flat(event)
    return ev in {"posttooluse", "afterfileedit", "aftershellexecution", "subagentstop"}


@dataclass
class ObserverSpool:
    """Disposable, non-canonical event buffer used by hooks and the scribe.

    This is deliberately outside the Gemara. It may be deleted or rebuilt at any
    time. Only explicit continuity commands are allowed to write canonical state.
    """

    path: Path

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"at": _now(), **event}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")

    def read(self, *, limit: int = 200) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return rows[-limit:]

    def line_count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def set_watermark(self, count: int, *, stops_since_bookmark: int = 0) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        (self.path.parent / "observer-nudge.json").write_text(
            json.dumps(
                {
                    "nudge_at_count": max(0, count),
                    "stops_since_bookmark": max(0, stops_since_bookmark),
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def read_nudge_state(self) -> dict[str, int]:
        path = self.path.parent / "observer-nudge.json"
        if not path.exists():
            return {"nudge_at_count": 0, "stops_since_bookmark": 0}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"nudge_at_count": 0, "stops_since_bookmark": 0}
        if not isinstance(data, dict):
            return {"nudge_at_count": 0, "stops_since_bookmark": 0}
        try:
            nudge = max(0, int(data.get("nudge_at_count") or 0))
        except (TypeError, ValueError):
            nudge = 0
        try:
            stops = max(0, int(data.get("stops_since_bookmark") or 0))
        except (TypeError, ValueError):
            stops = 0
        return {"nudge_at_count": nudge, "stops_since_bookmark": stops}

    def mark_documented(self, event: dict[str, Any]) -> None:
        """Replace tool-event noise with one baseline line after a Gemara write.

        Stop then counts *new* observer events since this bookmark. The line is
        a counter reset, not Gemara content — no body, and the model is not
        asked to read it.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"at": _now(), **event}
        self.path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        self.set_watermark(1)
