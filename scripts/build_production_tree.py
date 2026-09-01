#!/usr/bin/env python3
"""Build a deterministic, allowlisted production tree from an exact QA SHA.

PROD pulls QA. This script never copies the repository wholesale. It copies only
paths listed in release/production-files.txt, overlays PROD-owned files, rewrites
public install URLs to the production repository, rejects private/runtime residue,
verifies version alignment, and emits RELEASE_PROVENANCE.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

FORBIDDEN_PARTS = {
    ".git",
    ".talmudic",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "workstreams",
    "dist",
    "build",
    ".eggs",
}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".db"}
FORBIDDEN_NAMES = {".env", "id_rsa", "id_ed25519", "credentials.json"}
QA_REPO = "gilav2/Talmudic-AI-memory"
PUBLIC_REWRITE_PATHS = (
    "README.md",
    "USER_GUIDE.md",
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".claude-plugin/README.md",
    ".cursor-plugin/plugin.json",
    ".cursor-plugin/marketplace.json",
    ".cursor-plugin/README.md",
)
PRESERVE_ON_APPLY = (
    ".github/workflows/promote-from-qa.yml",
)


def die(msg: str) -> None:
    raise SystemExit(msg)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def posix(rel: Path) -> str:
    return str(rel).replace(os.sep, "/")


def is_forbidden(rel: Path) -> bool:
    return any(part in FORBIDDEN_PARTS or part.endswith(".egg-info") for part in rel.parts)


def copy_entry(src: Path, dst_root: Path, source_root: Path) -> None:
    try:
        rel = src.resolve().relative_to(source_root.resolve())
    except Exception:
        die(f"path escapes source root: {src}")
    if is_forbidden(rel):
        return
    if src.is_symlink():
        die(f"symlinks are not allowed in production bundle: {rel}")
    if src.is_file() and (src.name in FORBIDDEN_NAMES or src.suffix.lower() in FORBIDDEN_SUFFIXES):
        die(f"sensitive file type/name rejected: {rel}")
    dst = dst_root / rel
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in sorted(src.iterdir(), key=lambda p: p.name):
            copy_entry(child, dst_root, source_root)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    else:
        die(f"unsupported filesystem entry: {rel}")


def read_version(pyproject: Path) -> str:
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version ="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    die("version not found in pyproject.toml")


def json_version(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def rewrite_public_urls(root: Path, prod_repo: str) -> int:
    replaced = 0
    for rel in PUBLIC_REWRITE_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        if QA_REPO not in body:
            continue
        path.write_text(body.replace(QA_REPO, prod_repo), encoding="utf-8")
        replaced += 1
    return replaced


def scan_public_repo_refs(root: Path, prod_repo: str) -> None:
    offenders = []
    found_prod = False
    expected = f"github.com/{prod_repo}"
    for rel in PUBLIC_REWRITE_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        if QA_REPO in body:
            offenders.append(rel)
        if expected in body or prod_repo in body:
            found_prod = True
    if offenders:
        die(
            "public install surfaces still reference QA repository "
            + QA_REPO
            + ": "
            + ", ".join(offenders)
        )
    if not found_prod:
        die(f"no public surface references expected production repository {prod_repo}")


def read_list(path: Path) -> list[str]:
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def install_pipeline_files(pipeline_root: Path, out: Path) -> None:
    owned = pipeline_root / "release" / "prod-owned"
    if owned.is_dir():
        for src in sorted(p for p in owned.rglob("*") if p.is_file()):
            rel = src.relative_to(owned)
            if is_forbidden(rel):
                die(f"forbidden prod-owned path: {rel}")
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    extra_list = pipeline_root / "release" / "prod-extra.txt"
    if extra_list.is_file():
        for line in read_list(extra_list):
            src = pipeline_root / line
            if not src.is_file():
                die(f"prod-extra path missing: {line}")
            dst = out / line
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def collect_files(root: Path) -> list[Path]:
    return sorted(item for item in root.rglob("*") if item.is_file())


def apply_tree(tree: Path, dest: Path) -> None:
    if not tree.is_dir():
        die(f"production tree missing: {tree}")
    dest.mkdir(parents=True, exist_ok=True)
    old_paths: set[str] = set()
    old_prov = dest / "RELEASE_PROVENANCE.json"
    if old_prov.is_file():
        data = json.loads(old_prov.read_text(encoding="utf-8"))
        old_paths = {str(item["path"]) for item in data.get("files", [])}
    new_paths: set[str] = set()
    for path in collect_files(tree):
        rel = path.relative_to(tree)
        if is_forbidden(rel):
            die(f"forbidden production artifact: {rel}")
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
        new_paths.add(posix(rel))
    for old in sorted(old_paths - new_paths):
        if old in PRESERVE_ON_APPLY or old.startswith(".git/"):
            continue
        target = dest / old
        if target.is_file():
            target.unlink()


def write_provenance(
    out: Path, version: str, source_sha: str, prod_repo: str
) -> list[dict[str, object]]:
    files = []
    for path in collect_files(out):
        files.append(
            {
                "path": posix(path.relative_to(out)),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    provenance = {
        "schema": 1,
        "product": "Talmudic AI Memory",
        "thesis": "The agent dies. The work is immortal.",
        "version": version,
        "source_repository": QA_REPO,
        "source_branch": "main",
        "source_sha": source_sha,
        "target_repository": prod_repo,
        "promotion": "PROD pulls exact QA SHA; allowlisted export; public URLs rewritten to production repo",
        "files": files,
    }
    (out / "RELEASE_PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return files


def build_tree(args: argparse.Namespace) -> list[dict[str, object]]:
    source = Path(args.source).resolve()
    pipeline_root = Path(args.pipeline_root or args.source).resolve()
    out = Path(args.out).resolve()
    allowlist = pipeline_root / (args.allowlist or "release/production-files.txt")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    entries = []
    for line in read_list(allowlist):
        path = source / line
        if not path.exists():
            die(f"allowlisted path missing: {line}")
        entries.append(path)

    for path in entries:
        copy_entry(path, out, source)

    install_pipeline_files(pipeline_root, out)
    rewrite_public_urls(out, args.prod_repo)

    versions = {
        "pyproject": read_version(out / "pyproject.toml"),
        "claude_plugin": json_version(out / ".claude-plugin" / "plugin.json"),
        "cursor_plugin": json_version(out / ".cursor-plugin" / "plugin.json"),
        "plugin": json_version(out / "plugin.json"),
    }
    if any(value != args.version for value in versions.values()):
        die(f"version mismatch: expected {args.version}; found {versions}")

    for path in out.rglob("*"):
        rel = path.relative_to(out)
        if is_forbidden(rel):
            die(f"forbidden production artifact: {rel}")

    scan_public_repo_refs(out, args.prod_repo)
    files = write_provenance(out, args.version, args.source_sha, args.prod_repo)
    print(
        json.dumps(
            {
                "version": args.version,
                "source_sha": args.source_sha,
                "files": len(files),
                "target": args.prod_repo,
            }
        )
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".")
    parser.add_argument("--pipeline-root", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--prod-repo", default="AI4AI-Labs/talmudic-ai-memory")
    parser.add_argument("--allowlist", default="release/production-files.txt")
    parser.add_argument("--apply-to", default="")
    parser.add_argument("--apply-only", action="store_true")
    args = parser.parse_args()

    if args.apply_only:
        apply_tree(Path(args.out).resolve(), Path(args.apply_to).resolve())
        return 0

    if not args.version or not args.source_sha:
        die("--version and --source-sha are required when building")

    build_tree(args)
    if args.apply_to:
        apply_tree(Path(args.out).resolve(), Path(args.apply_to).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
