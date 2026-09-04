from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPTS_DIR.parent

_CLAUDE_EVENTS = {
    "sessionstart": "SessionStart",
    "sessionend": "SessionEnd",
    "precompact": "PreCompact",
    "pretooluse": "PreToolUse",
    "posttooluse": "PostToolUse",
    "beforeshellexecution": "PreToolUse",
    "aftershellexecution": "PostToolUse",
    "afterfileedit": "PostToolUse",
    "stop": "Stop",
    "subagentstop": "SubagentStop",
}

_TOOL_NAMES = {
    "shell": "Bash",
    "bash": "Bash",
    "edit": "Write",
    "write": "Write",
    "task": "Task",
}


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")


def _normalize_event(raw: str) -> str:
    key = raw.strip().lower().replace("_", "").replace("-", "")
    return _CLAUDE_EVENTS.get(key, raw.strip())


def detected_event(data: dict[str, Any], default: str = "") -> str:
    argv_event = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = argv_event or str(data.get("hook_event_name") or data.get("event") or default)
    return _normalize_event(raw)


def plugin_root() -> Path:
    for key in ("CURSOR_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        raw = os.getenv(key)
        if raw:
            return Path(raw).resolve()
    return PLUGIN_ROOT


def project_enables_talmudic(project_root: Path) -> bool:
    """User-scope Cursor plugins load in every window; hooks must no-op elsewhere.

    A project opts in with `.cursor/talmudic.json` `{"enabled": true}`, or by
    already having a `.talmudic/` directory. The plugin checkout itself never
    opts in. `enabled: false` wins over a leftover `.talmudic/` directory.
    """
    project = Path(project_root).resolve()
    if project == plugin_root():
        return False
    marker = project / ".cursor" / "talmudic.json"
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and "enabled" in data:
            return data.get("enabled") is True
    return (project / ".talmudic").is_dir()


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    root = str(plugin_root())
    env.setdefault("CURSOR_PLUGIN_ROOT", root)
    env.setdefault("PLUGIN_ROOT", root)
    env.setdefault("CLAUDE_PLUGIN_ROOT", root)
    return env


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


def _windows_hook_host() -> bool:
    if os.name == "nt":
        return True
    return any(os.getenv(key) for key in ("WINDIR", "SYSTEMROOT", "MSYSTEM", "MINGW_PREFIX"))


def coerce_cursor_path(raw: str) -> str:
    """Cursor/Git Bash Windows roots look like ``/c:/temp/app`` or ``/c/temp/app``."""
    text = str(raw).strip().strip('"')
    if text.startswith("file://"):
        text = text[7:]
    if len(text) >= 4 and text[0] in "/\\" and text[1].isalpha() and text[2] == ":":
        return f"{text[1]}:{text[3:]}"
    if (
        _windows_hook_host()
        and len(text) >= 4
        and text[0] in "/\\"
        and text[1].isalpha()
        and text[2] == "/"
    ):
        return f"{text[1]}:{text[2:]}"
    return text


def extract_command(data: dict[str, Any]) -> str:
    if data.get("command"):
        return str(data["command"])
    tool_input = _tool_input(data)
    return str(tool_input.get("command") or "")


def _usable_project_dir(raw: Any) -> Path | None:
    """Reject the plugin tree and relative '.' so sessionStart is not empty.

    Cursor plugin hooks run from ``CURSOR_PLUGIN_ROOT``. sessionStart's
    documented payload has ``workspace_roots`` and no ``cwd``; when ``cwd``
    is present it is often that plugin path, which ``project_enables_talmudic``
    refuses — empty hook output in an opted-in dummy.
    """
    if raw is None:
        return None
    text = str(raw).strip().strip('"')
    if not text or text in {".", "./", ".\\"}:
        return None
    try:
        resolved = Path(coerce_cursor_path(text)).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    try:
        if resolved == plugin_root():
            return None
    except OSError:
        return None
    return resolved


def extract_cwd(data: dict[str, Any]) -> str:
    candidates: list[Any] = []
    if data.get("cwd"):
        candidates.append(data.get("cwd"))
    roots = data.get("workspace_roots")
    if isinstance(roots, str) and roots.strip():
        candidates.append(roots)
    elif isinstance(roots, list):
        candidates.extend(roots)
    tool_input = _tool_input(data)
    working = tool_input.get("working_directory") or tool_input.get("cwd")
    if working:
        candidates.append(working)
    env_project = os.getenv("CURSOR_PROJECT_DIR") or os.getenv("CLAUDE_PROJECT_DIR")
    if env_project:
        candidates.append(env_project)
    for raw in candidates:
        usable = _usable_project_dir(raw)
        if usable is not None:
            return str(usable)
    fallback = _usable_project_dir(Path.cwd())
    if fallback is not None:
        return str(fallback)
    return str(Path.cwd().resolve())


def map_tool_name(raw: str) -> str:
    if not raw:
        return raw
    mapped = _TOOL_NAMES.get(raw.strip().lower())
    return mapped or raw


def enrich_payload(data: dict[str, Any], default_event: str = "") -> dict[str, Any]:
    payload = dict(data)
    event = detected_event(payload, default_event)
    if event:
        payload["hook_event_name"] = event
        payload["event"] = event

    if not payload.get("session_id") and payload.get("conversation_id"):
        payload["session_id"] = payload["conversation_id"]

    payload["cwd"] = extract_cwd(payload)

    command = extract_command(payload)
    if command:
        payload["command"] = command

    if not payload.get("file_path"):
        tool_input = _tool_input(payload)
        path = tool_input.get("file_path") or tool_input.get("path")
        if path:
            payload["file_path"] = str(path)

    incoming_event = str(data.get("hook_event_name") or data.get("event") or default_event)
    flattened = incoming_event.strip().lower().replace("_", "").replace("-", "")
    tool_name = str(payload.get("tool_name") or "")
    if flattened == "afterfileedit":
        tool_name = tool_name or "Write"
    elif flattened in {"beforeshellexecution", "aftershellexecution"}:
        tool_name = tool_name or "Shell"
    payload["tool_name"] = map_tool_name(tool_name)

    if not payload.get("cursor_version"):
        payload["cursor_version"] = os.getenv("CURSOR_VERSION") or "cursor-plugin"

    if event == "SessionStart" and not payload.get("source"):
        payload["source"] = "startup"

    if event == "PreCompact" and not payload.get("source"):
        trigger = str(payload.get("trigger") or "auto")
        payload["source"] = trigger if trigger in {"auto", "manual"} else "auto"

    return payload


def run_continuity_script(script_name: str, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    script = SCRIPTS_DIR / script_name
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=child_env(),
        cwd=str(payload.get("cwd") or Path.cwd()),
    )
