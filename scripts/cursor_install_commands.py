#!/usr/bin/env python3
"""Copy plugin slash commands and the static Cursor SessionStart index pointer.

Cursor's plugin `commands` field often does not refresh the `/` menu. Project
`.cursor/commands/*.md` files do. Plugin-packaged alwaysApply rules are dropped;
project `.cursor/rules/talmudic-orient.mdc` is included at composer create. That
rule says Gemara is indexed: search it (`orient` / `recall`); do not run
`digest`. Both copies are local host machinery, not Gemara.
"""

from __future__ import annotations

from pathlib import Path

from cursor_adapter import extract_cwd, plugin_root, read_stdin_json


def _copy_text(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    body = src.read_text(encoding="utf-8")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.read_text(encoding="utf-8") == body:
        return False
    dest.write_text(body, encoding="utf-8")
    return True


def install_cursor_project_commands(*, plugin_root: Path, project_root: Path) -> list[str]:
    plugin = plugin_root.resolve()
    project = project_root.resolve()
    if project == plugin:
        return []
    source = plugin / "commands"
    if not source.is_dir():
        return []
    dest = project / ".cursor" / "commands"
    written: list[str] = []
    for src in sorted(source.glob("talmudic-*.md")):
        if _copy_text(src, dest / src.name):
            written.append(src.name)
    return written


def install_cursor_project_orient_rule(*, plugin_root: Path, project_root: Path) -> str | None:
    """Copy the static SessionStart index-pointer rule into an opted-in project.

    Project ``alwaysApply`` rules are included at composer create. Plugin-packaged
    alwaysApply rules are not. This file is duty, not a Gemara digest snapshot.
    """
    plugin = plugin_root.resolve()
    project = project_root.resolve()
    if project == plugin:
        return None
    dest = project / ".cursor" / "rules" / "talmudic-orient.mdc"
    if not _copy_text(plugin / "host" / "cursor" / "talmudic-orient.mdc", dest):
        return None
    return dest.name


def main() -> int:
    data = read_stdin_json()
    project = Path(extract_cwd(data))
    root = plugin_root()
    install_cursor_project_commands(plugin_root=root, project_root=project)
    install_cursor_project_orient_rule(plugin_root=root, project_root=project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
