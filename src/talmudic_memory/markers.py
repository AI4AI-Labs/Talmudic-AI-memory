from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_KINDS = {"git-head", "git-state", "file-text", "file-int", "static"}


class MarkerResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarkerSource:
    key: str
    kind: str
    locator: str | None = None


def parse_marker_source(spec: str) -> MarkerSource:
    """Parse "KEY=KIND[|LOCATOR]".

    git-head/git-state default their locator to the project repo when omitted (the
    common case needs zero per-machine config). file-text/file-int have no sensible
    default filename, so a locator is required for them. static never takes a locator.
    """
    if "=" not in spec:
        raise ValueError(f"expected KEY=KIND[|LOCATOR], got {spec}")
    key, rhs = spec.split("=", 1)
    parts = rhs.split("|", 1)
    kind = parts[0]
    locator = parts[1] if len(parts) == 2 and parts[1] else None
    if kind not in _KINDS:
        raise ValueError(f"unsupported marker source kind: {kind}")
    if kind in {"file-text", "file-int"} and not locator:
        raise ValueError(f"marker source kind {kind} requires a locator (file path)")
    if kind == "static" and locator:
        raise ValueError("static marker source does not take a locator")
    return MarkerSource(key=key, kind=kind, locator=locator)


def _run_git(args: list[str], *, cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise MarkerResolutionError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def resolve_marker(source: MarkerSource, *, resume_value: Any, project_root: Path) -> str:
    """Compute the actual current value for one marker. Raises MarkerResolutionError on failure.

    git-head/git-state resolve against project_root (the tracked project repo) when no
    explicit locator override is configured — never against the Gemara mirror, which
    would silently verify the wrong repository.
    """
    if source.kind == "static":
        return str(resume_value)
    if source.kind == "git-head":
        repo = Path(source.locator) if source.locator else project_root
        return _run_git(["rev-parse", "HEAD"], cwd=repo)
    if source.kind == "git-state":
        repo = Path(source.locator) if source.locator else project_root
        head = _run_git(["rev-parse", "HEAD"], cwd=repo)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True)
        if status.returncode != 0:
            raise MarkerResolutionError(f"git status failed in {repo}: {status.stderr.strip()}")
        if not status.stdout.strip():
            return f"{head}|CLEAN"
        digest = hashlib.sha256(status.stdout.encode()).hexdigest()
        return f"{head}|DIRTY:{digest}"
    if source.kind in {"file-text", "file-int"}:
        path = Path(source.locator) if source.locator else project_root
        if not path.is_absolute():
            path = project_root / path
        if not path.exists():
            raise MarkerResolutionError(f"marker file does not exist: {path}")
        text = path.read_text(encoding="utf-8").strip()
        if source.kind == "file-int":
            try:
                int(text)
            except ValueError as exc:
                raise MarkerResolutionError(f"marker file {path} does not contain an integer: {text!r}") from exc
        return text
    raise MarkerResolutionError(f"unsupported marker source kind: {source.kind}")


def resolve_markers(
    authoritative_markers: dict[str, str],
    sources: dict[str, MarkerSource],
    *,
    project_root: Path,
) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """Fail-closed resolution over every authoritative marker.

    A key with no configured source is "unresolved" — we have no way to check it,
    which is not the same as its live value being absent. A resolver that raises is
    recorded in "errors". Neither case is silently treated as passing verification.
    """
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    errors: dict[str, str] = {}
    for key in authoritative_markers:
        source = sources.get(key)
        if source is None:
            unresolved.append(key)
            continue
        try:
            resolved[key] = resolve_marker(source, resume_value=authoritative_markers[key], project_root=project_root)
        except Exception as exc:  # resolver failures are verification failures, not state facts
            errors[key] = f"{type(exc).__name__}: {exc}"
    return resolved, unresolved, errors
