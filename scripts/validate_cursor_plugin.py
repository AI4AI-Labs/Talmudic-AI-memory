#!/usr/bin/env python3
"""Validate Cursor marketplace packaging for production submission."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".cursor-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".cursor-plugin" / "marketplace.json"
HOOKS = ROOT / "hooks" / "hooks-cursor.json"
EXPECTED_COMMANDS = {
    "talmudic-doctor",
    "talmudic-init",
    "talmudic-recall",
    "talmudic-remember",
    "talmudic-status",
}
FORBIDDEN_COMMANDS = {"talmudic-origin"}


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


def main() -> int:
    manifest = load_json(MANIFEST)
    marketplace = load_json(MARKETPLACE)

    for key in ("skills", "agents", "commands", "rules", "hooks", "logo"):
        if key not in manifest:
            die(f".cursor-plugin/plugin.json missing required component field: {key}")

    plugin_entry = marketplace.get("plugins", [{}])[0]
    for key in ("skills", "agents", "commands", "rules", "hooks", "logo"):
        if key not in plugin_entry:
            die(f".cursor-plugin/marketplace.json plugin entry missing: {key}")

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

    if not HOOKS.is_file():
        die("hooks/hooks-cursor.json is required for Cursor packaging")
    if (ROOT / "hooks" / "hooks.json").is_file():
        hooks_cursor = json.loads(HOOKS.read_text(encoding="utf-8"))
        if "hooks" not in hooks_cursor:
            die("hooks-cursor.json must declare Cursor hook events")

    print(
        "cursor-plugin-ok",
        f"commands={len(command_names)}",
        f"rules={len(rule_files)}",
        f"logo={rel(logo)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
