"""Project-local Talmudic CLI launcher.

A global ``python -m talmudic_memory.cli`` can resolve to an older pip
install. Write a launcher under ``.talmudic/`` that
puts this plugin's ``src`` on ``PYTHONPATH``. The interpreter is
rediscovered at run time (``py -3`` / ``python`` / ``python3``).

Cursor expands ``${CURSOR_PLUGIN_ROOT}`` for plugin hooks. The launcher
prefers that directory at run time when it is set, then the ``src``
recorded when a hook last called ``write_project_runtime``.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

MISSING_PYTHON_MESSAGE = "TALMUDIC: Python 3.10+ not found. Install Python and ensure python or py -3 is on PATH."
LAUNCHER_WRITE_PREFIX = "TALMUDIC: could not write project launcher:"


def package_src() -> Path:
    return Path(__file__).resolve().parents[1]


def plugin_src_from_env() -> Path | None:
    for key in ("CURSOR_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"):
        raw = os.getenv(key)
        if not raw:
            continue
        src = Path(raw) / "src"
        if (src / "talmudic_memory").is_dir():
            return src.resolve()
    return None


def discover_plugin_src(hint: Path | str | None = None) -> Path:
    env_src = plugin_src_from_env()
    if env_src is not None:
        return env_src
    if hint is not None:
        candidate = Path(hint)
        src = candidate if candidate.name == "src" else candidate / "src"
        if (src / "talmudic_memory").is_dir():
            return src.resolve()
        if (candidate / "talmudic_memory").is_dir():
            return candidate.resolve()
    return package_src()


def runtime_pin_is_usable(src: str) -> bool:
    path = Path(src)
    return (path / "talmudic_memory").is_dir()


def _replace_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_project_runtime(
    project_root: Path,
    *,
    python: str | None = None,
    src: Path | None = None,
) -> dict[str, object]:
    project = project_root.resolve()
    interpreter = python or sys.executable
    source = discover_plugin_src(src)
    state_dir = project / ".talmudic"
    state_dir.mkdir(parents=True, exist_ok=True)
    launcher_error: OSError | None = None
    if os.name == "nt":
        launcher = state_dir / "talmudic.cmd"
        command = ".talmudic\\talmudic.cmd"
        body = _windows_cmd_body(source)
    else:
        launcher = state_dir / "talmudic"
        command = ".talmudic/talmudic"
        body = _unix_sh_body(source)
    try:
        _replace_text(launcher, body)
        if os.name != "nt":
            mode = launcher.stat().st_mode
            launcher.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as exc:
        launcher_error = exc
        sys.stderr.write(f"{LAUNCHER_WRITE_PREFIX} {launcher}: {exc}\n")
    payload: dict[str, object] = {
        "available": True,
        "command": command,
        "python": interpreter,
        "src": str(source),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if launcher_error is not None:
        payload["launcher_error"] = str(launcher_error)
    _replace_text(state_dir / "runtime.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def _windows_cmd_body(source: Path) -> str:
    fallback = str(source)
    return (
        "@echo off\r\n"
        "setlocal EnableExtensions\r\n"
        f'set "TALMUDIC_FALLBACK={fallback}"\r\n'
        'set "TALMUDIC_SRC="\r\n'
        'if defined CURSOR_PLUGIN_ROOT if exist "%CURSOR_PLUGIN_ROOT%\\src\\talmudic_memory\\__init__.py" (\r\n'
        '  set "TALMUDIC_SRC=%CURSOR_PLUGIN_ROOT%\\src"\r\n'
        ")\r\n"
        'if not defined TALMUDIC_SRC if defined CLAUDE_PLUGIN_ROOT if exist "%CLAUDE_PLUGIN_ROOT%\\src\\talmudic_memory\\__init__.py" (\r\n'
        '  set "TALMUDIC_SRC=%CLAUDE_PLUGIN_ROOT%\\src"\r\n'
        ")\r\n"
        'if not defined TALMUDIC_SRC set "TALMUDIC_SRC=%TALMUDIC_FALLBACK%"\r\n'
        'set "PYTHONPATH=%TALMUDIC_SRC%"\r\n'
        "where py >nul 2>&1\r\n"
        "if %ERRORLEVEL% EQU 0 (\r\n"
        "  py -3 -m talmudic_memory.cli %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "where python >nul 2>&1\r\n"
        "if %ERRORLEVEL% EQU 0 (\r\n"
        "  python -m talmudic_memory.cli %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        "where python3 >nul 2>&1\r\n"
        "if %ERRORLEVEL% EQU 0 (\r\n"
        "  python3 -m talmudic_memory.cli %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        f"echo {MISSING_PYTHON_MESSAGE} 1>&2\r\n"
        "exit /b 1\r\n"
    )


def _unix_sh_body(source: Path) -> str:
    quoted_src = _sh_single_quote(str(source))
    return (
        "#!/bin/sh\n"
        f"TALMUDIC_FALLBACK={quoted_src}\n"
        "if [ -n \"${CURSOR_PLUGIN_ROOT:-}\" ] && [ -f \"$CURSOR_PLUGIN_ROOT/src/talmudic_memory/__init__.py\" ]; then\n"
        '  TALMUDIC_SRC="$CURSOR_PLUGIN_ROOT/src"\n'
        'elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/src/talmudic_memory/__init__.py" ]; then\n'
        '  TALMUDIC_SRC="$CLAUDE_PLUGIN_ROOT/src"\n'
        "else\n"
        '  TALMUDIC_SRC="$TALMUDIC_FALLBACK"\n'
        "fi\n"
        'export PYTHONPATH="$TALMUDIC_SRC"\n'
        "if command -v python3 >/dev/null 2>&1; then\n"
        '  exec python3 -m talmudic_memory.cli "$@"\n'
        "fi\n"
        "if command -v python >/dev/null 2>&1; then\n"
        '  exec python -m talmudic_memory.cli "$@"\n'
        "fi\n"
        "if command -v py >/dev/null 2>&1; then\n"
        '  exec py -3 -m talmudic_memory.cli "$@"\n'
        "fi\n"
        f'echo "{MISSING_PYTHON_MESSAGE}" >&2\n'
        "exit 1\n"
    )


def _sh_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
