from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .index import GemaraIndex
from .runtime import runtime_pin_is_usable
from .workspace import DEFAULT_BRANCH, Workspace


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return None


def _open_inflight(canonical_root: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    root = canonical_root / "workstreams"
    if not root.exists():
        return found
    for resume_path in root.rglob("resume.json"):
        try:
            data = json.loads(resume_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for wid in data.get("open_inflight") or []:
            found.append({"workstream": data.get("workstream_id", ""), "inflight_id": wid})
    return found


def diagnose(workspace: Workspace, *, state_root: Path, index_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    checks.append({
        "name": "python",
        "status": "PASS" if sys.version_info >= (3, 10) else "FAIL",
        "detail": sys.version.split()[0],
    })
    git = shutil.which("git")
    checks.append({"name": "git", "status": "PASS" if git else "WARN", "detail": git or "not found"})

    canonical_exists = workspace.canonical_root.exists()
    checks.append({
        "name": "canonical_store",
        "status": "PASS" if canonical_exists else "FAIL",
        "detail": str(workspace.canonical_root),
    })

    if workspace.shared:
        remote = _run(["git", "ls-remote", "--exit-code", "--heads", "origin", workspace.branch or DEFAULT_BRANCH], cwd=workspace.project_root)
        remote_ok = bool(remote and remote.returncode == 0 and remote.stdout.strip())
        checks.append({
            "name": "shared_branch",
            "status": "PASS" if remote_ok else "FAIL",
            "detail": workspace.branch or DEFAULT_BRANCH,
            "warning": "Deleting this branch deletes the canonical shared Gemara unless another backup exists.",
        })
        if canonical_exists:
            clean = _run(["git", "status", "--porcelain"], cwd=workspace.canonical_root)
            dirty = bool(clean and clean.stdout.strip())
            checks.append({
                "name": "mirror_clean",
                "status": "WARN" if dirty else "PASS",
                "detail": clean.stdout.strip() if dirty and clean else "clean",
            })
    else:
        checks.append({
            "name": "sharing_scope",
            "status": "WARN",
            "detail": "LOCAL_ONLY: no shared Git remote detected",
        })

    actor_path = state_root / "actor.json"
    if actor_path.exists():
        try:
            actor = json.loads(actor_path.read_text(encoding="utf-8"))
            has_session = bool(actor.get("session_id"))
            checks.append({
                "name": "session_provenance",
                "status": "PASS" if has_session else "WARN",
                "detail": {k: actor.get(k, "") for k in ("agent_id", "session_id", "role", "model")},
            })
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({"name": "session_provenance", "status": "WARN", "detail": f"unreadable actor.json: {exc}"})
    else:
        checks.append({"name": "session_provenance", "status": "WARN", "detail": "actor.json not present"})

    runtime_path = state_root / "runtime.json"
    if runtime_path.is_file():
        try:
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            src = str(runtime.get("src") or "")
            usable = runtime_pin_is_usable(src)
            checks.append({
                "name": "project_runtime",
                "status": "WARN" if src and not usable else "PASS",
                "detail": {
                    "src": src,
                    "updated_at": runtime.get("updated_at"),
                    "note": (
                        "Pinned plugin src is missing. A hook should rewrite .talmudic/runtime.json from CURSOR_PLUGIN_ROOT."
                        if src and not usable
                        else "project launcher pin"
                    ),
                },
            })
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({"name": "project_runtime", "status": "WARN", "detail": f"unreadable runtime.json: {exc}"})

    idx = GemaraIndex(index_path).status(workspace.canonical_root)
    checks.append({
        "name": "index",
        "status": "PASS" if idx.get("fresh") else ("WARN" if not idx.get("exists") else "FAIL"),
        "detail": idx,
    })

    open_ops = _open_inflight(workspace.canonical_root)
    checks.append({
        "name": "recovery_state",
        "status": "WARN" if open_ops else "PASS",
        "detail": open_ops or "no open In-Flight operations",
    })

    overall = "PASS"
    if any(c["status"] == "FAIL" for c in checks):
        overall = "FAIL"
    elif any(c["status"] == "WARN" for c in checks):
        overall = "WARN"

    return {
        "status": overall,
        "mode": workspace.mode,
        "shared": workspace.shared,
        "branch": workspace.branch,
        "checks": checks,
        "recommended_actions": _recommend(checks),
    }


def _recommend(checks: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    by_name = {c["name"]: c for c in checks}
    idx = by_name.get("index", {})
    detail = idx.get("detail") if isinstance(idx.get("detail"), dict) else {}
    if idx.get("status") != "PASS":
        actions.append("Run `talmudic index update`; if integrity fails, run `talmudic index rebuild`.")
    branch = by_name.get("shared_branch")
    if branch and branch.get("status") == "FAIL":
        actions.append("Restore or recreate the `talmudic-memory` branch from backup before making new continuity writes.")
    recovery = by_name.get("recovery_state")
    if recovery and recovery.get("status") == "WARN":
        actions.append("Reconcile open In-Flight operations against the real system of record before new material writes.")
    prov = by_name.get("session_provenance")
    if prov and prov.get("status") == "WARN":
        actions.append("Start/resume through a supported plugin hook or set session provenance explicitly.")
    pin = by_name.get("project_runtime")
    if pin and pin.get("status") == "WARN":
        actions.append(
            "Rewrite this folder's launcher pin (`.talmudic/runtime.json`). "
            "The next plugin hook should set src from CURSOR_PLUGIN_ROOT."
        )
    if detail.get("integrity") == "FAIL":
        actions.append("The index is disposable; rebuild it. Do not alter canonical Gemara records to repair an index failure.")
    return actions
