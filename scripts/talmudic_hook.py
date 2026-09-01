from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_PLUGIN_CANDIDATE = Path(__file__).resolve().parents[1]
_PLUGIN_SRC = _PLUGIN_CANDIDATE / "src"
if _PLUGIN_SRC.is_dir() and str(_PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_SRC))

from talmudic_memory.runtime import write_project_runtime
from talmudic_memory.session_pointer import session_start_pointer


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_input() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _project_dir(data: dict) -> Path:
    if data.get("cwd"):
        return Path(_coerce_host_path(str(data["cwd"]))).resolve()
    roots = data.get("workspace_roots") or []
    if roots:
        return Path(_coerce_host_path(str(roots[0]))).resolve()
    return Path.cwd().resolve()


def _coerce_host_path(raw: str) -> str:
    text = str(raw).strip().strip('"')
    if text.startswith("file://"):
        text = text[7:]
    if len(text) >= 4 and text[0] in "/\\" and text[1].isalpha() and text[2] == ":":
        text = f"{text[1]}:{text[3:]}"
    return text


def _plugin_root() -> Path | None:
    for key in ("CURSOR_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"):
        raw = os.getenv(key)
        if raw:
            return Path(raw).resolve()
    candidate = Path(__file__).resolve().parents[1]
    return candidate if (candidate / "pyproject.toml").exists() else None


def _plugin_src() -> Path | None:
    root = _plugin_root()
    if root is None:
        return None
    src = root / "src"
    return src if (src / "talmudic_memory").is_dir() else None


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    src = _plugin_src()
    if src is not None:
        env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run_captured(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_runtime_env(),
    )


def _ensure_runtime() -> tuple[bool, list[str] | str]:
    """Returns (ok, argv-list) on success, (False, error-message) otherwise.

    The success value is a plain argv list, not a shell string — a prior
    version built a quoted string (``'"{sys.executable}" -m ...'``) and
    re-split it with ``shlex.split(..., posix=os.name != "nt")``, but
    shlex's non-posix mode does not strip quote characters from tokens, so
    on Windows the resulting argv[0] still had literal quotes embedded and
    subprocess.run couldn't find the executable. An argv list sidesteps
    shell quoting entirely.
    """
    root = _plugin_root()
    if root is not None and (root / "src" / "talmudic_memory").is_dir():
        return True, [sys.executable, "-m", "talmudic_memory.cli"]
    if shutil.which("talmudic"):
        return True, ["talmudic"]
    if root is None:
        return False, "plugin root unavailable"
    commands = [
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--user", str(root)],
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", str(root)],
    ]
    for cmd in commands:
        result = _run_captured(cmd)
        if result.returncode == 0:
            return True, [sys.executable, "-m", "talmudic_memory.cli"]
    return False, "runtime install failed"


def _run_runtime(runtime_command: list[str], args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return _run_captured(runtime_command + args, cwd=cwd)


def _compact_preflight_output(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()[:1000]
    return json.dumps(
        {
            key: data.get(key)
            for key in ("status", "changes_seen", "blocking_changes", "next_action")
            if key in data
        },
        sort_keys=True,
    )


def main() -> int:
    data = _read_input()
    project = _project_dir(data)
    state = project / ".talmudic"
    state.mkdir(parents=True, exist_ok=True)

    session_id = str(data.get("session_id") or data.get("conversation_id") or "")
    model = str(data.get("model_id") or data.get("model") or os.getenv("CLAUDE_MODEL") or "")
    event = str(data.get("hook_event_name") or data.get("event") or "")
    runtime = "cursor" if data.get("cursor_version") else "claude-code"
    explicit_agent = str(data.get("agent_id") or os.getenv("TALMUDIC_AGENT_ID") or "")
    actor = {
        "agent_id": explicit_agent or (f"{runtime}:{session_id}" if session_id else runtime),
        "session_id": session_id,
        "role": os.getenv("TALMUDIC_ROLE", "primary"),
        "model": model,
        "runtime": runtime,
        "updated_at": _now(),
    }
    (state / "actor.json").write_text(json.dumps(actor, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Rewrite the launcher on every event. sessionEnd/preCompact used to
    # update actor.json without calling write_project_runtime, so the
    # project pin could stay on an older plugin checkout than Cursor loaded.
    try:
        write_project_runtime(
            project,
            python=sys.executable,
            src=_plugin_src(),
        )
    except OSError as exc:
        sys.stderr.write(f"TALMUDIC: could not write project launcher: {exc}\n")

    lowered = event.lower().replace("_", "")
    if lowered == "precompact":
        (state / "context-pressure.json").write_text(
            json.dumps({"at": _now(), "session_id": session_id, "model": model}, indent=2) + "\n",
            encoding="utf-8",
        )

    if lowered == "sessionstart":
        runtime_ok, runtime_command = _ensure_runtime()
        runtime_display = ""
        try:
            runtime_state = json.loads((state / "runtime.json").read_text(encoding="utf-8"))
            runtime_display = str(runtime_state.get("command") or "")
            if runtime_state.get("available"):
                runtime_ok = True
        except (OSError, UnicodeError, json.JSONDecodeError):
            runtime_display = " ".join(runtime_command) if runtime_ok else ""
        if not runtime_display:
            runtime_display = " ".join(runtime_command) if runtime_ok else ""
        bootstrap_note = "not run"
        preflight_note = "not run"
        if runtime_ok:
            bootstrap = _run_runtime(runtime_command, ["bootstrap"], cwd=project)
            if bootstrap.returncode == 0:
                bootstrap_note = "synced"
                preflight = _run_runtime(runtime_command, ["preflight"], cwd=project)
                if preflight.returncode in {0, 4}:
                    preflight_note = _compact_preflight_output(preflight.stdout)
                else:
                    preflight_note = f"error: {preflight.stderr.strip()[:500]}"
            else:
                bootstrap_note = f"error: {bootstrap.stderr.strip()[:500]}"

        runtime_note = runtime_display if runtime_ok else f"UNAVAILABLE: {runtime_command}"
        print(
            session_start_pointer()
            + f"Runtime={runtime_note}. Bootstrap={bootstrap_note}. Preflight={preflight_note}. "
            + f"Session provenance: agent_id={actor['agent_id']} session_id={session_id or 'unknown'} model={model or 'unknown'} runtime={runtime}."
        )
    elif lowered in {"precompact", "sessionend"}:
        print(
            "Talmudic: compacting. Remember this if a future agent would miss it."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
