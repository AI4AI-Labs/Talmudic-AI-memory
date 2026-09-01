from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


MAX_POINTERS = 24
MAX_FILE_BYTES = 256 * 1024
HEADING_BYTES = 8192
MAX_DEPTH = 4

SKIP_DIRS = {
    ".git",
    ".talmudic",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    "vendor",
    "target",
    ".next",
    "coverage",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}

GEMARA_NAMES = {
    "resume.json",
    "checkpoints.jsonl",
    "inflight.jsonl",
    "sugya.jsonl",
    "breadcrumb.jsonl",
    "origin.json",
    "marker_kinds.json",
    "intent.json",
}

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".woff",
    ".woff2",
    ".ttf",
    ".so",
    ".dylib",
    ".exe",
    ".bin",
    ".pyc",
    ".whl",
    ".gz",
    ".tar",
}

ROOT_KIND = {
    "readme.md": "readme",
    "readme": "readme",
    "readme.rst": "readme",
    "readme.txt": "readme",
    "contributing.md": "contributing",
    "changelog.md": "changelog",
    "architecture.md": "architecture",
    "thesis.md": "thesis",
    "prd.md": "prd",
    "product.md": "product",
    "agents.md": "host-guide",
    "claude.md": "host-guide",
    "pyproject.toml": "manifest",
    "package.json": "manifest",
    "cargo.toml": "manifest",
    "go.mod": "manifest",
    "gemfile": "manifest",
    "makefile": "manifest",
    "dockerfile": "manifest",
    "docker-compose.yml": "manifest",
    "docker-compose.yaml": "manifest",
}

KIND_PRIORITY = {
    "readme": 0,
    "prd": 1,
    "thesis": 2,
    "architecture": 3,
    "product": 4,
    "host-guide": 5,
    "changelog": 6,
    "contributing": 7,
    "manifest": 8,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_remote_url(url: str) -> str:
    """Drop userinfo from git remotes so tokens never enter Gemara."""
    if "://" not in url:
        return url
    parts = urlsplit(url)
    host = parts.hostname or ""
    netloc = f"{host}:{parts.port}" if parts.port else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _kind_for(rel: str, name: str) -> str | None:
    lower = name.lower()
    if lower in ROOT_KIND:
        return ROOT_KIND[lower]
    if "prd" in lower or "product-requirement" in lower:
        return "prd"
    if "thesis" in lower:
        return "thesis"
    if "architect" in lower or re.search(r"(^|[-_])adr([-_.]|$)", lower):
        return "architecture"
    if "product" in lower and lower.endswith((".md", ".txt", ".rst")):
        return "product"
    parts = Path(rel).parts
    if parts and parts[0] in {"docs", "doc", "documentation"} and lower.endswith((".md", ".rst", ".txt")):
        if "overview" in lower:
            return "product"
    return None


def _git(project_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_info(project_root: Path) -> dict[str, Any] | None:
    toplevel = _git(project_root, "rev-parse", "--show-toplevel")
    if not toplevel or Path(toplevel).resolve() != project_root.resolve():
        return None
    info: dict[str, Any] = {}
    head = _git(project_root, "rev-parse", "HEAD")
    if head:
        info["head"] = head
    branch = _git(project_root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        info["branch"] = branch
    remote = _git(project_root, "remote", "get-url", "origin")
    if remote:
        info["origin"] = sanitize_remote_url(remote)
    log = _git(project_root, "log", "-5", "--pretty=%s")
    if log:
        info["recent_subjects"] = [line for line in log.splitlines() if line.strip()]
    return info or None


def _quoted_toml_field(text: str, key: str) -> str:
    match = re.search(rf'^{key}\s*=\s*"([^"]*)"', text, flags=re.M)
    return match.group(1) if match else ""


def _manifest(project_root: Path) -> dict[str, str] | None:
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file() and pyproject.stat().st_size <= MAX_FILE_BYTES:
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            text = ""
        name = _quoted_toml_field(text, "name")
        description = _quoted_toml_field(text, "description")
        if name or description:
            return {"name": name, "description": description[:240]}
    package = project_root / "package.json"
    if package.is_file() and package.stat().st_size <= MAX_FILE_BYTES:
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(data, dict):
            name = str(data.get("name") or "")
            description = str(data.get("description") or "")
            if name or description:
                return {"name": name, "description": description[:240]}
    return None


def _first_heading(path: Path) -> str:
    try:
        raw = path.read_bytes()[:HEADING_BYTES]
    except OSError:
        return ""
    if b"\0" in raw:
        return ""
    text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:200]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return ""


def _eligible(path: Path) -> bool:
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size > MAX_FILE_BYTES:
        return False
    if path.suffix.lower() in BINARY_SUFFIXES:
        return False
    return True


def survey_project(project_root: str | Path) -> dict[str, Any]:
    """Map pointer files in the project tree. Does not copy document bodies."""
    root = Path(project_root).resolve()
    candidates: list[dict[str, Any]] = []
    if root.is_dir():
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            rel_dir = Path(dirpath).resolve().relative_to(root)
            depth = 0 if rel_dir == Path(".") else len(rel_dir.parts)
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
            if depth > MAX_DEPTH:
                dirnames.clear()
                continue
            for name in filenames:
                if name in GEMARA_NAMES:
                    continue
                path = Path(dirpath) / name
                rel = path.relative_to(root).as_posix()
                kind = _kind_for(rel, name)
                if kind is None or not _eligible(path):
                    continue
                candidates.append(
                    {
                        "path": rel,
                        "kind": kind,
                        "heading": _first_heading(path),
                        "bytes": path.stat().st_size,
                    }
                )
    candidates.sort(key=lambda item: (KIND_PRIORITY.get(item["kind"], 50), item["path"]))
    origin: dict[str, Any] = {
        "title": "Project origin map",
        "surveyed_at": _now(),
        "pointers": candidates[:MAX_POINTERS],
    }
    git = _git_info(root)
    if git:
        origin["git"] = git
    manifest = _manifest(root)
    if manifest:
        origin["manifest"] = manifest
    return origin
