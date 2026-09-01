#!/usr/bin/env python3
"""Cursor sessionStart command hook.

Official output is ``env`` plus ``additional_context``. Cursor Agent (3.18.9+)
injects ``additional_context`` into the chat as ``hooks_context``. ``env``
reaches later hooks. Cloud agents skip this event.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

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
from talmudic_memory.runtime import write_project_runtime


def _write_runtime(project: Path) -> None:
    try:
        write_project_runtime(
            project,
            python=sys.executable,
            src=_PLUGIN_SRC if (_PLUGIN_SRC / "talmudic_memory").is_dir() else None,
        )
    except OSError as exc:
        sys.stderr.write(f"TALMUDIC: could not write project launcher: {exc}\n")


def run_session_start(payload: dict[str, Any]) -> int:
    project = Path(str(payload.get("cwd") or "."))
    if not project_enables_talmudic(project):
        return 0

    try:
        install_cursor_project_commands(
            plugin_root=plugin_root(),
            project_root=project,
        )
        install_cursor_project_orient_rule(
            plugin_root=plugin_root(),
            project_root=project,
        )
    except OSError as exc:
        sys.stderr.write(
            f"TALMUDIC: could not install project slash commands or orient rule: {exc}\n"
        )
    _write_runtime(project)

    result = run_continuity_script("talmudic_hook.py", payload)
    text = (result.stdout or "").strip()
    if result.stderr:
        sys.stderr.write(result.stderr)

    session_id = str(payload.get("session_id") or "")
    env = {"TALMUDIC_MEMORY": "1"}
    if session_id:
        env["TALMUDIC_SESSION_ID"] = session_id
    write_json({"env": env, "additional_context": text})
    return 0


def main() -> int:
    payload = enrich_payload(read_stdin_json(), default_event="sessionStart")
    return run_session_start(payload)


if __name__ == "__main__":
    raise SystemExit(main())
