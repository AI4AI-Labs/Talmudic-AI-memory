from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path


SHELL_SEPARATORS = {";", "&&", "||", "|"}
WINDOWS_DELETE_FLAGS = {"/q", "/s", "/f", "/a"}


def _payload() -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def _command(data: dict) -> str:
    if data.get("command"):
        return str(data["command"])
    tool_input = data.get("tool_input") or {}
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    return ""


def _segments(command: str) -> list[list[str]]:
    """Best-effort shell tokenization without matching quoted prose as commands."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return []
    out: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in SHELL_SEPARATORS:
            if current:
                out.append(current)
                current = []
        else:
            current.append(token)
    if current:
        out.append(current)
    return out


def _basename(token: str) -> str:
    return Path(token).name.lower()


def _is_talmudic_command(tokens: list[str]) -> bool:
    if not tokens:
        return False
    exe = _basename(tokens[0])
    if exe in {"talmudic", "talmudic.exe"}:
        return True
    if exe in {"python", "python3", "python.exe", "py", "py.exe"}:
        joined = " ".join(tokens[1:5]).lower()
        return "-m talmudic_memory.cli" in joined or "talmudic_memory.cli" in joined
    return False


def _cache_cleanup_only(tokens: list[str], cwd: Path) -> bool:
    if not tokens:
        return False
    exe = _basename(tokens[0])
    if exe not in {"rm", "rmdir", "del", "remove-item", "remove-item.exe"}:
        return False

    # Absolute POSIX paths begin with '/', so slash-prefixed arguments cannot be
    # discarded generically. Skip only known Windows `del` switches; normal
    # dash-prefixed options remain options on POSIX/PowerShell.
    targets = [
        t for t in tokens[1:]
        if not t.startswith("-") and t.lower() not in WINDOWS_DELETE_FLAGS
    ]
    if not targets:
        return False

    cache_root = (cwd / ".talmudic" / "cache").resolve()
    for target in targets:
        p = Path(target)
        resolved = (p if p.is_absolute() else cwd / p).resolve()
        try:
            resolved.relative_to(cache_root)
        except ValueError:
            return False
    return True


def _segment_is_material(tokens: list[str], cwd: Path) -> bool:
    if not tokens or _is_talmudic_command(tokens) or _cache_cleanup_only(tokens, cwd):
        return False
    low = [t.lower() for t in tokens]
    exe = _basename(low[0])

    if exe == "git" and len(low) > 1 and low[1] == "push":
        return True
    if exe in {"rm", "rmdir", "del", "remove-item", "remove-item.exe"}:
        return any(flag in low for flag in {"-r", "-rf", "-fr", "-f", "--recursive", "--force"}) or exe in {"del", "remove-item", "remove-item.exe"}
    if exe == "kubectl" and len(low) > 1 and low[1] in {"apply", "delete", "patch", "replace", "scale"}:
        return True
    if exe == "terraform" and len(low) > 1 and low[1] in {"apply", "destroy", "import"}:
        return True
    if exe in {"npm", "pnpm", "yarn"} and "publish" in low[1:3]:
        return True
    if exe in {"docker", "podman"} and len(low) > 1 and low[1] in {"push", "rm", "rmi"}:
        return True
    if exe == "aws" and len(low) > 2:
        if low[1] == "s3" and low[2] in {"rm", "mv", "cp", "sync"}:
            return True
        return any(t in {"delete", "terminate", "update", "put", "create"} or t.startswith(("delete-", "terminate-", "update-", "put-", "create-")) for t in low[1:])
    if exe == "az":
        return any(t in {"delete", "update", "create", "set"} for t in low[1:])
    if exe == "gcloud":
        return any(t in {"delete", "deploy", "update", "create"} for t in low[1:])
    if exe in {"alembic", "django-admin", "manage.py"}:
        return any("migrat" in t for t in low[1:])
    if exe in {"psql", "mysql", "sqlite3"}:
        sql = " ".join(low[1:])
        return any(f"{kw} " in f" {sql} " for kw in ("insert", "update", "delete", "alter", "drop", "create", "truncate"))
    return False


def _material(command: str, cwd: Path) -> bool:
    return any(_segment_is_material(segment, cwd) for segment in _segments(command))


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resume_from_pointer(cwd: Path) -> dict | None:
    pointer = cwd / ".talmudic" / "cache" / "active_workstream.json"
    meta = _load_json(pointer) if pointer.exists() else None
    if not meta:
        return None
    resume_path = meta.get("resume_path")
    if resume_path:
        resume = _load_json(Path(str(resume_path)))
        if resume:
            return resume
    workstream_id = str(meta.get("workstream_id") or "")
    if not workstream_id:
        return None
    for base in (cwd / ".talmudic" / "mirror", cwd / ".talmudic" / "local"):
        candidate = base / "workstreams" / workstream_id / "resume.json"
        resume = _load_json(candidate)
        if resume:
            return resume
    return None


def _active_resume(cwd: Path) -> dict | None:
    pointed = _resume_from_pointer(cwd)
    if pointed:
        return pointed
    candidates: list[dict] = []
    for base in (cwd / ".talmudic" / "mirror", cwd / ".talmudic" / "local"):
        ws_root = base / "workstreams"
        if not ws_root.exists():
            continue
        for resume_path in ws_root.rglob("resume.json"):
            resume = _load_json(resume_path)
            if resume and resume.get("status") != "COMPLETE":
                candidates.append(resume)
    return candidates[0] if len(candidates) == 1 else None


def main() -> int:
    data = _payload()
    command = _command(data)
    cwd = Path(data.get("cwd") or Path.cwd()).resolve()
    if not command or not _material(command, cwd):
        return 0

    resume = _active_resume(cwd)
    if resume and resume.get("open_inflight"):
        return 0

    print(
        "TALMUDIC_MATERIAL_WRITE_GUARD: this command may leave a durable effect, but no unambiguous active workstream with an open In-Flight record was found. Open an In-Flight intent first, then retry. Talmudic CLI operations and disposable `.talmudic/cache` cleanup are never blocked by this guard.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
