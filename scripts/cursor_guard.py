#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from cursor_adapter import (
    enrich_payload,
    extract_cwd,
    project_enables_talmudic,
    read_stdin_json,
    run_continuity_script,
    write_json,
)

GUARD_FAIL_CLOSED_MESSAGE = (
    "TALMUDIC_MATERIAL_WRITE_GUARD: material-write guard failed closed. "
    "The continuity guard did not return a clean allow."
)


def permission_for_guard_exit(returncode: int) -> str:
    """Only an explicit 0 from talmudic_guard.py is allow; every other outcome denies."""
    return "allow" if returncode == 0 else "deny"


def _deny(message: str) -> int:
    write_json(
        {
            "permission": "deny",
            "user_message": message,
            "agent_message": message,
        }
    )
    return 2


def _allow() -> int:
    write_json({"permission": "allow"})
    return 0


def main() -> int:
    incoming: dict = {}
    try:
        incoming = read_stdin_json()
        payload = enrich_payload(incoming, default_event="beforeShellExecution")
        if not project_enables_talmudic(Path(str(payload.get("cwd") or "."))):
            return _allow()
        result = run_continuity_script("talmudic_guard.py", payload)
        if result.stderr:
            sys.stderr.write(result.stderr)
        if permission_for_guard_exit(result.returncode) == "allow":
            return _allow()
        message = (result.stderr or "").strip() or GUARD_FAIL_CLOSED_MESSAGE
        return _deny(message)
    except Exception as exc:
        try:
            if not project_enables_talmudic(Path(extract_cwd(incoming))):
                return _allow()
        except Exception:
            return _allow()
        return _deny(f"{GUARD_FAIL_CLOSED_MESSAGE} ({type(exc).__name__}: {exc})")


if __name__ == "__main__":
    raise SystemExit(main())
