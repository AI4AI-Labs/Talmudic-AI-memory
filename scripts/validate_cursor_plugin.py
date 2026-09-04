#!/usr/bin/env python3
"""Validate Cursor marketplace packaging for production submission.

 Dual-host hook layout:

- Cursor: ``hooks/hooks-cursor.json`` inside ``hooks/`` (scanners glob that
  folder). The manifest points at it explicitly. Do not use the shared
  default name ``hooks/hooks.json`` — Claude Code also auto-loads that file
  and would run Cursor schema.
- Claude: extra path ``claude/hooks-claude.json``. Claude JSON must not live
  under ``hooks/``.
- Root ``hooks.json`` and ``cursor/`` must not exist.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".cursor-plugin" / "marketplace.json"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
CURSOR_HOOKS = ROOT / "hooks" / "hooks-cursor.json"
CLAUDE_HOOKS = ROOT / "claude" / "hooks-claude.json"
CURSOR_HOOKS_REF = "./hooks/hooks-cursor.json"
CLAUDE_HOOKS_REF = "./claude/hooks-claude.json"
FORBIDDEN_HOOK_PATHS = (
    ROOT / "hooks.json",
    ROOT / "hooks" / "hooks.json",
    ROOT / "hooks" / "hooks-claude.json",
    ROOT / "cursor" / "hooks-cursor.json",
)
EXPECTED_COMMANDS = {
    "talmudic-doctor",
    "talmudic-init",
    "talmudic-recall",
    "talmudic-remember",
    "talmudic-status",
}
FORBIDDEN_COMMANDS = {"talmudic-origin"}
CURSOR_EVENTS = (
    "sessionStart",
    "workspaceOpen",
    "sessionEnd",
    "beforeShellExecution",
    "preToolUse",
    "postToolUse",
    "afterFileEdit",
    "afterShellExecution",
    "preCompact",
    "subagentStop",
    "stop",
)
CLAUDE_EVENTS = (
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "Stop",
    "SessionEnd",
)
SHARED_DISPLAY_NAME = "Talmudic AI Memory"
SHARED_DESCRIPTION = (
    "Persistent project memory for coding agents. Preserves decisions, "
    "rationale, rejected alternatives, reopen conditions, and work state "
    "so agents can resume projects without reconstructing context from scratch."
)
SHARED_LICENSE = "Apache-2.0"
SHARED_KEYWORDS = [
    "immortality",
    "memory",
    "hooks",
    "talmudic",
    "gemara",
    "ai-agents",
    "project-memory",
    "continuity",
    "coding-agents",
]
ROOT_MANIFEST = ROOT / "plugin.json"
CLAUDE_MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
SESSION_POINTER = ROOT / "src" / "talmudic_memory" / "session_pointer.py"
ORIENT_RULE = ROOT / "rules" / "talmudic-orient.mdc"
POINTER_MUST_CONTAIN = (
    "Talmudic Memory is active",
    "ongoing project",
    "later-rejected",
    "leftover",
    "not a new mandate",
    "first move",
    "starting over",
    "record earlier agents and the operator left",
    "the old record stays",
    "through that same launcher",
    "ran preflight",
    'orient "<task>"',
    'recall "<question>"',
    "digest",
    "plugin cache",
    "sugya",
    "why and how",
    "isn't retried",
    "You inherit this handoff",
    "future agent",
    "orient",
    "recall",
)
POINTER_MUST_NOT_CONTAIN = (
    "Do not",
    "do not",
    "Repo files can lie",
    "not instructions",
    "not a command",
    "Claude Memory",
    "/talmudic-",
    "PRD",
    "ADR",
)


def die(msg: str) -> None:
    raise SystemExit(msg)


def load_json(path: Path) -> dict:
    if not path.is_file():
        die(f"missing manifest: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def assert_path_exists(path: Path) -> None:
    if not path.exists():
        die(f"manifest path does not exist: {rel(path)}")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_hook_layout() -> None:
    for path in FORBIDDEN_HOOK_PATHS:
        if path.is_file():
            die(
                f"{rel(path)} must not exist. Cursor hooks live at "
                "hooks/hooks-cursor.json (not the shared default hooks/hooks.json, "
                "which Claude also auto-loads). Claude hooks live at "
                "claude/hooks-claude.json. cursor/ is a scanner miss."
            )

    hooks_dir = ROOT / "hooks"
    if not hooks_dir.is_dir():
        die("hooks/ is required for Cursor packaging")
    extra_hooks = sorted(
        rel(path)
        for path in hooks_dir.rglob("*.json")
        if path.resolve() != CURSOR_HOOKS.resolve()
    )
    if extra_hooks:
        die(
            "hooks/ must contain only hooks-cursor.json (Cursor schema). "
            "Do not use hooks.json — Claude auto-loads that name. "
            f"Found: {extra_hooks}"
        )
    if (ROOT / "cursor").is_dir():
        die("cursor/ must not exist; Cursor scanners look in hooks/, not cursor/")

    claude_plugin_dir = ROOT / ".claude-plugin"
    forbidden_claude_plugin = []
    for path in claude_plugin_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "hooks.json" or "hooks" in path.parts:
            forbidden_claude_plugin.append(rel(path))
        elif path.suffix == ".json" and path.name not in ("plugin.json", "marketplace.json"):
            forbidden_claude_plugin.append(rel(path))
    if forbidden_claude_plugin:
        die(
            ".claude-plugin/ is manifest-only; hook JSON must not live there: "
            + ", ".join(forbidden_claude_plugin)
        )

    if not CURSOR_HOOKS.is_file():
        die("hooks/hooks-cursor.json is required for Cursor packaging")
    if not CLAUDE_HOOKS.is_file():
        die("claude/hooks-claude.json is required for Claude packaging")

    cursor_body = text(CURSOR_HOOKS)
    if "CLAUDE_PLUGIN_ROOT" in cursor_body or "talmudic_hook.py" in cursor_body:
        die("hooks-cursor.json must not reference Claude scripts")
    if "CURSOR_PLUGIN_ROOT" not in cursor_body:
        die("hooks-cursor.json must use CURSOR_PLUGIN_ROOT")
    if "cursor_session_start.py" not in cursor_body:
        die("hooks-cursor.json must run cursor_session_start.py on sessionStart")

    cursor_hooks = json.loads(cursor_body).get("hooks")
    if not isinstance(cursor_hooks, dict):
        die("hooks-cursor.json must declare Cursor hook events")
    for event in CURSOR_EVENTS:
        if event not in cursor_hooks:
            die(f"hooks-cursor.json missing Cursor event: {event}")

    claude_body = text(CLAUDE_HOOKS)
    if "CURSOR_PLUGIN_ROOT" in claude_body or "cursor_session_start.py" in claude_body:
        die("hooks-claude.json must not reference Cursor scripts")
    if "CLAUDE_PLUGIN_ROOT" not in claude_body:
        die("hooks-claude.json must use CLAUDE_PLUGIN_ROOT")
    if "talmudic_hook.py" not in claude_body:
        die("hooks-claude.json must run talmudic_hook.py")

    claude_hooks = json.loads(claude_body).get("hooks")
    if not isinstance(claude_hooks, dict):
        die("hooks-claude.json must declare Claude hook events")
    for event in CLAUDE_EVENTS:
        if event not in claude_hooks:
            die(f"hooks-claude.json missing Claude event: {event}")


def assert_listing(path: Path, data: dict, keywords_key: str) -> None:
    if data.get("displayName") != SHARED_DISPLAY_NAME:
        die(f"{rel(path)} displayName must be {SHARED_DISPLAY_NAME!r}")
    if data.get("description") != SHARED_DESCRIPTION:
        die(f"{rel(path)} description must match the shared listing copy")
    if data.get(keywords_key) != SHARED_KEYWORDS:
        die(f"{rel(path)} {keywords_key} must match the shared listing tags")
    if data.get("license") not in (None, SHARED_LICENSE):
        die(f"{rel(path)} license must be {SHARED_LICENSE!r}")


def validate_listing_copy(
    manifest: dict, marketplace: dict, claude_manifest: dict
) -> None:
    root_manifest = load_json(ROOT_MANIFEST)
    claude_marketplace = load_json(CLAUDE_MARKETPLACE)
    cursor_entry = marketplace.get("plugins", [{}])[0]
    claude_entry = claude_marketplace.get("plugins", [{}])[0]
    metadata = marketplace.get("metadata") or {}

    if manifest.get("displayName") != SHARED_DISPLAY_NAME:
        die(".cursor-plugin/plugin.json displayName must be the product name")
    if claude_manifest.get("displayName") != SHARED_DISPLAY_NAME:
        die(".claude-plugin/plugin.json displayName must be the product name")
    if cursor_entry.get("displayName") != SHARED_DISPLAY_NAME:
        die(".cursor-plugin/marketplace.json plugin displayName must be the product name")
    if claude_entry.get("displayName") != SHARED_DISPLAY_NAME:
        die(".claude-plugin/marketplace.json plugin displayName must be the product name")

    assert_listing(MANIFEST, manifest, "keywords")
    assert_listing(CLAUDE_MANIFEST, claude_manifest, "keywords")
    assert_listing(MARKETPLACE, cursor_entry, "keywords")
    assert_listing(CLAUDE_MARKETPLACE, claude_entry, "tags")

    if manifest.get("license") != SHARED_LICENSE:
        die(".cursor-plugin/plugin.json license must be Apache-2.0")
    if claude_manifest.get("license") != SHARED_LICENSE:
        die(".claude-plugin/plugin.json license must be Apache-2.0")
    if cursor_entry.get("license") != SHARED_LICENSE:
        die(".cursor-plugin/marketplace.json plugin license must be Apache-2.0")
    if claude_entry.get("license") != SHARED_LICENSE:
        die(".claude-plugin/marketplace.json plugin license must be Apache-2.0")
    if root_manifest.get("license") != SHARED_LICENSE:
        die("plugin.json license must be Apache-2.0")

    if root_manifest.get("description") != SHARED_DESCRIPTION:
        die("plugin.json description must match the shared listing copy")
    if root_manifest.get("keywords") != SHARED_KEYWORDS:
        die("plugin.json keywords must match the shared listing tags")
    if metadata.get("description") != SHARED_DESCRIPTION:
        die(".cursor-plugin/marketplace.json metadata.description must match")
    if claude_marketplace.get("description") != SHARED_DESCRIPTION:
        die(".claude-plugin/marketplace.json description must match")


def validate_session_start_voice() -> None:
    pointer = text(SESSION_POINTER)
    for needle in POINTER_MUST_CONTAIN:
        if needle not in pointer:
            die(f"session_pointer.py must welcome the agent with {needle!r}")
    for needle in POINTER_MUST_NOT_CONTAIN:
        if needle in pointer:
            die(
                "session_pointer.py must stay a positive index pointer; "
                f"remove {needle!r} (SessionStart hook output is scanned as injection)"
            )
    orient = text(ORIENT_RULE)
    for needle in ("Repo files can lie", "not instructions", "Do not run digest", "ADR", "PRD"):
        if needle in orient:
            die(f"talmudic-orient.mdc must stay a general plugin rule; remove {needle!r}")


def main() -> int:
    manifest = load_json(MANIFEST)
    marketplace = load_json(MARKETPLACE)
    claude_manifest = load_json(CLAUDE_MANIFEST)

    for key in ("skills", "agents", "commands", "rules", "hooks", "logo"):
        if key not in manifest:
            die(f".cursor-plugin/plugin.json missing required component field: {key}")

    if manifest["hooks"] != CURSOR_HOOKS_REF:
        die(f".cursor-plugin/plugin.json hooks must be {CURSOR_HOOKS_REF}")

    plugin_entry = marketplace.get("plugins", [{}])[0]
    for key in ("skills", "agents", "commands", "rules", "hooks", "logo"):
        if key not in plugin_entry:
            die(f".cursor-plugin/marketplace.json plugin entry missing: {key}")
    if plugin_entry["hooks"] != CURSOR_HOOKS_REF:
        die(f".cursor-plugin/marketplace.json hooks must be {CURSOR_HOOKS_REF}")

    if claude_manifest.get("hooks") != CLAUDE_HOOKS_REF:
        die(f".claude-plugin/plugin.json hooks must be {CLAUDE_HOOKS_REF}")

    logo = ROOT / manifest["logo"]
    assert_path_exists(logo)
    if logo.suffix.lower() != ".png":
        die("logo must be a committed PNG in the repository")

    rules_dir = ROOT / "rules"
    rule_files = sorted(rules_dir.glob("*.mdc"))
    if not rule_files:
        die("rules/ must contain at least one .mdc rule")
    if not (rules_dir / "talmudic-orient.mdc").is_file():
        die("missing rules/talmudic-orient.mdc")

    commands_dir = ROOT / "commands"
    command_names = {path.stem for path in commands_dir.glob("talmudic-*.md")}
    if command_names != EXPECTED_COMMANDS:
        die(f"unexpected production commands: {sorted(command_names)}")
    if command_names & FORBIDDEN_COMMANDS:
        die("retired talmudic-origin command must not ship")

    validate_hook_layout()
    validate_listing_copy(manifest, marketplace, claude_manifest)
    validate_session_start_voice()

    print(
        "cursor-plugin-ok",
        f"commands={len(command_names)}",
        f"rules={len(rule_files)}",
        f"logo={rel(logo)}",
        "hooks=cursor+claude",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
