#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_SRC))

from cursor_adapter import (
    enrich_payload,
    plugin_root,
    project_enables_talmudic,
    read_stdin_json,
    run_continuity_script,
    write_json,
)
from cursor_install_commands import (
    install_cursor_project_commands,
    install_cursor_project_orient_rule,
)
from cursor_session_start import run_session_start
from talmudic_memory.runtime import write_project_runtime


def _event_key(event: str) -> str:
    return event.strip().lower().replace("_", "").replace("-", "")


def _write_runtime(project: Path) -> None:
    try:
        write_project_runtime(
            project,
            python=sys.executable,
            src=_PLUGIN_SRC if (_PLUGIN_SRC / "talmudic_memory").is_dir() else None,
        )
    except OSError as exc:
        sys.stderr.write(f"TALMUDIC: could not write project launcher: {exc}\n")


def main() -> int:
    data = read_stdin_json()
    payload = enrich_payload(data)
    event = str(payload.get("hook_event_name") or "")
    key = _event_key(event)
    project = Path(str(payload.get("cwd") or "."))
    if key == "sessionstart":
        return run_session_start(payload)

    if not project_enables_talmudic(project):
        return 0

    if key == "workspaceopen":
        try:
            install_cursor_project_commands(
                plugin_root=plugin_root(),
                project_root=Path(str(payload.get("cwd") or ".")),
            )
            install_cursor_project_orient_rule(
                plugin_root=plugin_root(),
                project_root=Path(str(payload.get("cwd") or ".")),
            )
        except OSError as exc:
            sys.stderr.write(
                f"TALMUDIC: could not install project slash commands or orient rule: {exc}\n"
            )
    _write_runtime(Path(str(payload.get("cwd") or ".")))
    if key == "workspaceopen":
        return 0

    if event == "PreCompact":
        run_continuity_script("talmudic_observer.py", payload)

    result = run_continuity_script("talmudic_hook.py", payload)
    text = (result.stdout or "").strip()
    if result.stderr:
        sys.stderr.write(result.stderr)

    if event == "PreCompact":
        write_json({"user_message": text})
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
