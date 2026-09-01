from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import ContinuityError, TalmudicStore
from .storage import FileStore

DEFAULT_BRANCH = "talmudic-memory"
CLIENT_MANAGED = "CLIENT_MANAGED"
HOST_MANAGED = "HOST_MANAGED"


def _run(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=check,
    )


def _git_root(cwd: Path) -> Path | None:
    try:
        out = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd).stdout.strip()
        return Path(out) if out else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _origin(root: Path) -> str | None:
    try:
        out = _run(["git", "remote", "get-url", "origin"], cwd=root).stdout.strip()
        return out or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _remote_branch_exists(root: Path, branch: str) -> bool:
    try:
        result = _run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch], cwd=root, check=False)
        return result.returncode == 0 and bool(result.stdout.strip())
    except FileNotFoundError:
        return False


def _sync_strategy() -> str:
    """Resolve who owns synchronization with the Git remote.

    Default is CLIENT_MANAGED because a cloud/container runtime may still expose a
    normal local clone that must explicitly push before the container disappears.
    A host may opt into HOST_MANAGED only by exposing an explicit capability signal.
    This avoids guessing from vendor name, container markers, or filesystem shape.
    """
    explicit = os.getenv("TALMUDIC_GIT_SYNC_STRATEGY", "").strip().upper()
    if explicit in {CLIENT_MANAGED, HOST_MANAGED}:
        return explicit
    host_flag = os.getenv("TALMUDIC_HOST_MANAGED_GIT", "").strip().lower()
    if host_flag in {"1", "true", "yes", "on"}:
        return HOST_MANAGED
    return CLIENT_MANAGED


def _ensure_local_exclude(root: Path) -> None:
    exclude = root / ".git" / "info" / "exclude"
    if not exclude.parent.exists():
        return
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    marker = ".talmudic/"
    if marker not in existing.splitlines():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(marker + "\n")


@dataclass
class Workspace:
    project_root: Path
    mode: str
    canonical_root: Path
    config_path: Path
    branch: str | None = None
    origin: str | None = None
    sync_strategy: str = CLIENT_MANAGED

    @property
    def shared(self) -> bool:
        return self.mode == "GIT_SHARED"

    def pull(self) -> None:
        if not self.shared or self.sync_strategy == HOST_MANAGED:
            return
        try:
            _run(["git", "pull", "--rebase", "origin", self.branch or DEFAULT_BRANCH], cwd=self.canonical_root)
        except subprocess.CalledProcessError as exc:
            raise ContinuityError(f"GIT_SYNC_PULL_FAILED: {exc.stderr.strip()}") from exc

    def push(self, *, message: str = "talmudic: persist continuity") -> bool:
        if not self.shared:
            return False
        if self.sync_strategy == HOST_MANAGED:
            # The host owns publication/synchronization of its remote-backed workspace.
            # Talmudic never performs a duplicate push in this mode.
            return False
        try:
            # Exclude the advisory *.lock sidecar files TalmudicStore's cross-process
            # locking creates alongside resume.json/marker_kinds.json etc. They're
            # disposable coordination artifacts, not continuity records, and must not
            # join the sacred canonical history.
            _run(["git", "add", "-A", "--", ".", ":!**/*.lock"], cwd=self.canonical_root)
            staged = _run(["git", "diff", "--cached", "--quiet"], cwd=self.canonical_root, check=False)
            if staged.returncode == 0:
                return False
            _run(["git", "commit", "-m", message], cwd=self.canonical_root)
            first = _run(["git", "push", "origin", self.branch or DEFAULT_BRANCH], cwd=self.canonical_root, check=False)
            if first.returncode == 0:
                return True
            _run(["git", "pull", "--rebase", "origin", self.branch or DEFAULT_BRANCH], cwd=self.canonical_root)
            _run(["git", "push", "origin", self.branch or DEFAULT_BRANCH], cwd=self.canonical_root)
            return True
        except subprocess.CalledProcessError as exc:
            raise ContinuityError(f"GIT_SYNC_PUSH_FAILED: {exc.stderr.strip()}") from exc

    def store(self, *, actor: dict[str, str] | None = None) -> TalmudicStore:
        return TalmudicStore(storage=FileStore(self.canonical_root), actor=actor)


def _write_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bootstrap_shared(root: Path, origin: str, branch: str) -> Workspace:
    state_dir = root / ".talmudic"
    mirror = state_dir / "mirror"
    config = state_dir / "config.json"
    strategy = _sync_strategy()
    _ensure_local_exclude(root)

    if not mirror.exists():
        mirror.parent.mkdir(parents=True, exist_ok=True)
        if _remote_branch_exists(root, branch):
            _run(["git", "clone", "--single-branch", "--branch", branch, origin, str(mirror)], cwd=root)
        else:
            mirror.mkdir(parents=True, exist_ok=True)
            _run(["git", "init"], cwd=mirror)
            _run(["git", "checkout", "--orphan", branch], cwd=mirror)
            warning = (
                "# Talmudic Memory shared branch\n\n"
                "This branch is the canonical shared Gemara for this project.\n\n"
                "**Do not delete this branch. Deleting it deletes the shared Talmudic history unless another backup exists.**\n\n"
                "It is intentionally separate from product branches and should not be merged into main by default.\n"
            )
            (mirror / "README.md").write_text(warning, encoding="utf-8")
            _run(["git", "add", "README.md"], cwd=mirror)
            _run(["git", "commit", "-m", "talmudic: initialize shared Gemara branch"], cwd=mirror)
            _run(["git", "remote", "add", "origin", origin], cwd=mirror)
            _run(["git", "push", "-u", "origin", branch], cwd=mirror)

    data = {
        "mode": "GIT_SHARED",
        "sync_strategy": strategy,
        "branch": branch,
        "origin": origin,
        "canonical_root": str(mirror),
        "warning": "Deleting the shared Talmudic branch deletes the canonical Gemara unless another backup exists.",
    }
    _write_config(config, data)
    return Workspace(root, "GIT_SHARED", mirror, config, branch=branch, origin=origin, sync_strategy=strategy)


def _bootstrap_local(root: Path) -> Workspace:
    state_dir = root / ".talmudic"
    canonical = state_dir / "local"
    canonical.mkdir(parents=True, exist_ok=True)
    config = state_dir / "config.json"
    data = {
        "mode": "LOCAL_ONLY",
        "sync_strategy": "LOCAL",
        "canonical_root": str(canonical),
        "warning": "No shared Git remote was detected. Continuity is limited to this durable project/harness filesystem.",
    }
    _write_config(config, data)
    return Workspace(root, "LOCAL_ONLY", canonical, config)


def inspect_workspace(cwd: str | Path | None = None, *, branch: str = DEFAULT_BRANCH) -> Workspace:
    """Resolve existing continuity storage without creating, cloning, pulling, or pushing anything.

    This is the only resolver Doctor/index-maintenance commands may use. It is intentionally
    read-only with respect to the canonical Gemara and Git remote.
    """
    here = Path(cwd or os.getcwd()).resolve()
    git_root = _git_root(here)
    root = git_root or here
    state_dir = root / ".talmudic"
    config = state_dir / "config.json"

    if config.exists():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
            mode = str(data.get("mode") or "LOCAL_ONLY")
            canonical = Path(data.get("canonical_root") or (state_dir / "local"))
            return Workspace(
                root,
                mode,
                canonical,
                config,
                branch=str(data.get("branch") or branch) if mode == "GIT_SHARED" else None,
                origin=str(data.get("origin") or "") or None,
                sync_strategy=str(data.get("sync_strategy") or CLIENT_MANAGED),
            )
        except (OSError, json.JSONDecodeError):
            pass

    origin = _origin(root) if git_root else None
    mirror = state_dir / "mirror"
    if origin and mirror.exists():
        return Workspace(root, "GIT_SHARED", mirror, config, branch=branch, origin=origin, sync_strategy=_sync_strategy())

    local = state_dir / "local"
    return Workspace(root, "LOCAL_ONLY", local, config)


def prepare_workspace(cwd: str | Path | None = None, *, branch: str = DEFAULT_BRANCH) -> Workspace:
    here = Path(cwd or os.getcwd()).resolve()
    git_root = _git_root(here)
    root = git_root or here
    origin = _origin(root) if git_root else None
    if origin:
        return _bootstrap_shared(root, origin, branch)
    return _bootstrap_local(root)
