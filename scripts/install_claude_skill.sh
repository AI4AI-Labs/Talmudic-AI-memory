#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/skills/talmudic-memory/SKILL.md"
DST_DIR="$HOME/.claude/skills/talmudic-memory"

mkdir -p "$DST_DIR"
cp "$SRC" "$DST_DIR/SKILL.md"

echo "Installed Talmudic Memory skill to $DST_DIR/SKILL.md"
echo "Invoke with /talmudic-memory or let Claude auto-load it when relevant."
