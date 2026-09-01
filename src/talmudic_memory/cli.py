from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .core import ContinuityError, TalmudicStore
from .digest import DEFAULT_BUDGET_BYTES, render_session_digest
from .doctor import diagnose
from .index import GemaraIndex
from .markers import MarkerSource, parse_marker_source, resolve_markers
from .observer import ObserverSpool
from .orient import orient as orient_task
from .preflight import run_preflight
from .runtime import write_project_runtime
from .survey import survey_project
from .workspace import Workspace, inspect_workspace, prepare_workspace


TERMINAL_INFLIGHT_STATES = ["VERIFIED", "PARTIAL", "FAILED", "ABORTED", "RECOVERED", "AMBIGUOUS", "ORPHANED"]


class _Parser(argparse.ArgumentParser):
    """Print the loaded package path on argparse errors so a pip install is obvious."""

    def error(self, message: str) -> None:
        extra = f"\nloaded {__file__}\n"
        if "invalid choice" in message:
            extra += (
                "If that path is not this clone's src/talmudic_memory, "
                "run ./talmudic (Unix) or .\\talmudic.cmd (Windows) from the plugin root, "
                "or set PYTHONPATH to that src directory. "
                "A pip/site-packages install may lack survey or this clone's CLI. "
            )
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}{extra}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kv(items: list[str]) -> dict[str, str]:
    out = {}
    for item in items:
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {item}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def _state_dir() -> Path:
    return Path.cwd() / ".talmudic"


def _hook_actor() -> dict[str, str]:
    path = _state_dir() / "actor.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: str(data.get(k, "")) for k in ("agent_id", "session_id", "role", "model")}
    except (OSError, json.JSONDecodeError):
        return {}


def _actor(args: argparse.Namespace) -> dict[str, str]:
    """Resolve one actor shape for hooks, CLI, canonical provenance, status and preflight."""
    captured = _hook_actor()
    return {
        "agent_id": args.agent_id or os.getenv("TALMUDIC_AGENT_ID", "") or captured.get("agent_id", ""),
        "session_id": args.session_id or os.getenv("TALMUDIC_SESSION_ID", "") or captured.get("session_id", ""),
        "role": args.role or os.getenv("TALMUDIC_ROLE", "") or captured.get("role", ""),
        "model": args.model or os.getenv("TALMUDIC_MODEL", "") or captured.get("model", ""),
    }


def _persist_actor(actor: dict[str, str]) -> None:
    """Persist the effective local actor so hooks and later CLI calls see the same identity."""
    clean = {k: v for k, v in actor.items() if v}
    if not clean:
        return
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True)
    (state / "actor.json").write_text(
        json.dumps({**clean, "updated_at": _now()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _actor_key_from(actor: dict[str, str]) -> str:
    return actor.get("agent_id") or actor.get("session_id") or actor.get("role") or "anonymous"


def _observer_cache_dir(workspace: Workspace | None) -> Path:
    if workspace is not None:
        return workspace.project_root / ".talmudic" / "cache"
    return Path.cwd() / ".talmudic" / "cache"


def _reset_observer_after_canonical_write(workspace: Workspace | None, cmd: str, workstream: str = "") -> None:
    """Zero-token counter reset: documented events drop off the observer spool."""
    try:
        ObserverSpool(_observer_cache_dir(workspace) / "observer.jsonl").mark_documented(
            {"event": "canonical_write", "cmd": cmd, "workstream": workstream}
        )
    except OSError:
        return


def _index_path(workspace: Workspace | None, explicit_root: str | None) -> Path:
    # explicit_root takes precedence over any synthesized workspace stub so that
    # writers and readers of cache paths agree regardless of which code path built
    # the Workspace object for a given --root invocation.
    if explicit_root:
        return Path(explicit_root).resolve() / ".cache" / "index.db"
    if workspace is not None:
        return workspace.project_root / ".talmudic" / "cache" / "index.db"
    return Path(".talmudic").resolve() / ".cache" / "index.db"


def _active_pointer_path(workspace: Workspace | None, explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).resolve() / ".cache" / "active_workstream.json"
    if workspace is not None:
        return workspace.project_root / ".talmudic" / "cache" / "active_workstream.json"
    return Path(".talmudic").resolve() / ".cache" / "active_workstream.json"


def _marker_locator_path(workspace: Workspace | None, explicit_root: str | None, workstream_id: str) -> Path:
    """Local-only marker locator overrides: never through TalmudicStore/self.storage.

    self.storage for a GIT_SHARED workspace is FileStore(canonical_root), and
    Workspace.push() runs `git add -A` inside canonical_root on every mutating
    command — anything written through the store there gets committed/pushed
    regardless of whether index.py recognizes the filename. Locator overrides are
    often machine-specific (e.g. an absolute repo path), so they're written by
    direct Path I/O under the same local project-cache tree as
    active_workstream.json/preflight cursors, deliberately outside canonical_root.
    """
    safe = workstream_id.replace("/", "_").replace("\\", "_").replace(":", "_") or "anonymous"
    if explicit_root:
        return Path(explicit_root).resolve() / ".cache" / "marker_sources" / f"{safe}.json"
    if workspace is not None:
        return workspace.project_root / ".talmudic" / "cache" / "marker_sources" / f"{safe}.json"
    return Path(".talmudic").resolve() / ".cache" / "marker_sources" / f"{safe}.json"


def _resolve_configured_markers(
    store: TalmudicStore,
    workspace: Workspace | None,
    explicit_root: str | None,
    workstream_id: str,
    authoritative_markers: dict[str, str],
) -> tuple[dict[str, str], list[str], dict[str, str]]:
    kinds = store.marker_kinds(workstream_id)
    locator_path = _marker_locator_path(workspace, explicit_root, workstream_id)
    locators = json.loads(locator_path.read_text(encoding="utf-8")) if locator_path.exists() else {}
    sources = {key: MarkerSource(key=key, kind=kind, locator=locators.get(key)) for key, kind in kinds.items()}
    project_root = workspace.project_root if workspace is not None else Path(explicit_root or ".").resolve()
    return resolve_markers(authoritative_markers, sources, project_root=project_root)


def _resolve_workstream_id(
    explicit: str | None, workspace: Workspace | None, explicit_root: str | None
) -> str | None:
    """Explicit ``--workstream`` wins; otherwise fall back to the project's
    last-active workstream pointer (written by init/status/checkpoint/etc.)."""
    if explicit:
        return explicit
    pointer = _active_pointer_path(workspace, explicit_root)
    if not pointer.exists():
        return None
    try:
        return json.loads(pointer.read_text(encoding="utf-8")).get("workstream_id") or None
    except (OSError, json.JSONDecodeError):
        return None


def _set_active_workstream(
    workspace: Workspace | None,
    explicit_root: str | None,
    workstream_id: str,
    actor: dict[str, str],
) -> None:
    pointer = _active_pointer_path(workspace, explicit_root)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    canonical_root = workspace.canonical_root if workspace is not None else Path(explicit_root or ".talmudic").resolve()
    resume_path = canonical_root / "workstreams" / workstream_id / "resume.json"
    pointer.write_text(
        json.dumps(
            {
                "workstream_id": workstream_id,
                "resume_path": str(resume_path),
                "actor": {k: v for k, v in actor.items() if v},
                "updated_at": _now(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    p = _Parser(prog="talmudic", description="Talmudic Memory continuity runtime")
    p.add_argument("--root", default=None, help="Explicit legacy/local store root. Omit for project auto-resolution.")
    p.add_argument("--agent-id")
    p.add_argument("--session-id")
    p.add_argument("--role")
    p.add_argument("--model")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap")
    sub.add_parser("sync")
    sub.add_parser("doctor")
    sub.add_parser("survey", help="Map project pointer files (read-only). Init writes this automatically.")
    pf = sub.add_parser("preflight", help=argparse.SUPPRESS)
    pf.add_argument("--no-advance", action="store_true")

    ix = sub.add_parser("index", help="Internal index maintenance/retrieval primitives")
    ixsub = ix.add_subparsers(dest="index_cmd", required=True)
    ixsub.add_parser("build")
    ixsub.add_parser("update")
    ixsub.add_parser("rebuild")
    ixsub.add_parser("status")
    ixs = ixsub.add_parser("search")
    ixs.add_argument("query")
    ixs.add_argument("--limit", type=int, default=20)
    ixs.add_argument("--workstream")

    recall = sub.add_parser("recall", help="Recall project/workstream history using natural-language terms")
    recall.add_argument("query")
    recall.add_argument("--limit", type=int, default=10)
    recall.add_argument("--workstream")

    orient_p = sub.add_parser(
        "orient",
        help="Search prior canonical work for a task before acting; returns a compact orientation packet. Does not sync — run `talmudic sync` first when freshness matters.",
    )
    orient_p.add_argument("task")
    orient_p.add_argument("--workstream")
    orient_p.add_argument("--limit", type=int, default=8)

    digest_p = sub.add_parser(
        "digest",
        help="Render a compact workstream digest (operator/debug). SessionStart does not inject this.",
    )
    digest_p.add_argument("--workstream")
    digest_p.add_argument("--mode", choices=["full", "light"], default="light")
    digest_p.add_argument("--budget-bytes", type=int, default=DEFAULT_BUDGET_BYTES)

    i = sub.add_parser("init", help=argparse.SUPPRESS)
    i.add_argument("workstream")
    i.add_argument("--task", default="")
    i.add_argument("--next", dest="next_action", default="")

    s = sub.add_parser("status", help="Show current resumable workstream state")
    s.add_argument("workstream")

    m = sub.add_parser("markers", help=argparse.SUPPRESS)
    m.add_argument("workstream")
    m.add_argument("pairs", nargs="+")

    ms = sub.add_parser("marker-source", help=argparse.SUPPRESS)
    ms.add_argument("workstream")
    ms.add_argument("source", help="KEY=KIND[|LOCATOR]; kinds: git-head, git-state, file-text, file-int, static")

    v = sub.add_parser("verify", help=argparse.SUPPRESS)
    v.add_argument("workstream")
    v.add_argument("pairs", nargs="*")

    t = sub.add_parser("checkpoint", help=argparse.SUPPRESS)
    t.add_argument("workstream")
    t.add_argument("--expected", type=int, required=True, dest="expected_checkpoint")
    t.add_argument("--status", choices=["ACTIVE", "BLOCKED", "COMPLETE"])
    t.add_argument("--task")
    t.add_argument("--next", dest="next_action")
    t.add_argument("--verified", action="append")
    t.add_argument("--blocker", action="append", dest="blockers")
    t.add_argument("--do-not", action="append", dest="do_not")
    t.add_argument("--reason", default="TRANSITION")

    w = sub.add_parser("intent", help=argparse.SUPPRESS)
    w.add_argument("workstream")
    w.add_argument("intent")
    w.add_argument("--effect", action="append", default=[])

    c = sub.add_parser("close", help=argparse.SUPPRESS)
    c.add_argument("workstream")
    c.add_argument("inflight_id")
    c.add_argument("--state", required=True, choices=TERMINAL_INFLIGHT_STATES)
    c.add_argument("--evidence", action="append", default=[])

    a = sub.add_parser("sugya", help=argparse.SUPPRESS)
    a.add_argument("workstream")
    a.add_argument("--expected", type=int, required=True, dest="expected_checkpoint")
    a.add_argument("--title", required=True)
    a.add_argument("--premise", required=True)
    a.add_argument("--question", required=True)
    a.add_argument("--test", required=True)
    a.add_argument("--result", required=True)
    a.add_argument("--resolution", required=True)
    a.add_argument("--caveat", default="")
    a.add_argument("--evidence", action="append", default=[])
    a.add_argument("--supersedes", action="append", default=[])

    n = sub.add_parser("note", help=argparse.SUPPRESS)
    n.add_argument("workstream")
    n.add_argument("--expected", type=int, required=True, dest="expected_checkpoint")
    n.add_argument("--state", required=True, choices=sorted(TalmudicStore.BREADCRUMB_STATES))
    n.add_argument("--what", required=True)
    n.add_argument("--why", default="")
    n.add_argument("--evid", default="")
    n.add_argument("--impact", default="")
    n.add_argument("--supersedes", default="")

    args = p.parse_args()
    actor = _actor(args)
    _persist_actor(actor)

    # Sacred-history invariant: doctor/index/recall/orient/digest/preflight/survey
    # may read canonical Gemara or the project tree, but never bootstrap, clone,
    # pull, push, mutate, or repair Gemara. Callers sync first with `sync` when
    # freshness matters.
    read_only = args.cmd in {
        "doctor",
        "index",
        "recall",
        "orient",
        "digest",
        "preflight",
        "survey",
    }
    if read_only:
        if args.root:
            root = Path(args.root).resolve()
            workspace = Workspace(root, "LOCAL_ONLY", root, root / ".config.json")
            state_root = root
        else:
            workspace = inspect_workspace()
            state_root = workspace.project_root / ".talmudic"
        canonical_root = workspace.canonical_root
        index_path = _index_path(workspace, args.root)

        if args.cmd == "doctor":
            result = diagnose(workspace, state_root=state_root, index_path=index_path)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 3 if result["status"] == "FAIL" else 0

        if args.cmd == "survey":
            result = survey_project(workspace.project_root)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        if args.cmd == "preflight":
            result = run_preflight(
                project_root=workspace.project_root,
                canonical_root=canonical_root,
                index_path=index_path,
                actor_key=_actor_key_from(actor),
                advance=not args.no_advance,
            ).__dict__
            print(json.dumps(result, indent=2, sort_keys=True))
            return 4 if result["status"] == "BLOCKED" else 0

        index = GemaraIndex(index_path)
        if args.cmd == "recall":
            if not index.status(canonical_root).get("fresh"):
                index.build(canonical_root)
            result = {
                "query": args.query,
                "results": index.search(args.query, limit=args.limit, workstream=args.workstream),
            }
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        if args.cmd == "orient":
            workstream_id = _resolve_workstream_id(args.workstream, workspace, args.root)
            result = asdict(orient_task(
                query=args.task,
                canonical_root=canonical_root,
                index_path=index_path,
                workstream_id=workstream_id,
                limit=args.limit,
            ))
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        if args.cmd == "digest":
            workstream_id = _resolve_workstream_id(args.workstream, workspace, args.root)
            mode_used, text = render_session_digest(
                canonical_root,
                workstream_id,
                prefer_full=(args.mode == "full"),
                budget_bytes=args.budget_bytes,
            )
            print(json.dumps({"mode": mode_used, "text": text}, indent=2, sort_keys=True))
            return 0

        if args.index_cmd in {"build", "update"}:
            result = index.build(canonical_root).__dict__
        elif args.index_cmd == "rebuild":
            result = index.rebuild(canonical_root).__dict__
        elif args.index_cmd == "status":
            result = index.status(canonical_root)
        elif args.index_cmd == "search":
            if not index.status(canonical_root).get("fresh"):
                index.build(canonical_root)
            result = {"query": args.query, "results": index.search(args.query, limit=args.limit, workstream=args.workstream)}
        else:
            raise AssertionError(args.index_cmd)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    workspace: Workspace | None = None
    if args.root:
        explicit = Path(args.root).resolve()
        store = TalmudicStore(explicit, actor=actor)
    else:
        try:
            workspace = prepare_workspace()
            workspace.pull()
            store = workspace.store(actor=actor)
        except ContinuityError as e:
            print(json.dumps({"error": str(e)}))
            return 2

    if args.cmd == "bootstrap":
        if workspace is None:
            project_root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
            result = {"mode": "EXPLICIT_ROOT", "root": str(args.root), "current_actor": actor}
        else:
            project_root = workspace.project_root
            result = {
                "mode": workspace.mode,
                "project_root": str(workspace.project_root),
                "canonical_root": str(workspace.canonical_root),
                "branch": workspace.branch,
                "shared": workspace.shared,
                "current_actor": actor,
                "warning": (
                    "Deleting the talmudic-memory branch deletes the canonical shared Gemara unless another backup exists."
                    if workspace.shared
                    else "No shared Git remote detected; continuity is LOCAL_ONLY."
                ),
            }
        result["runtime"] = write_project_runtime(project_root)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.cmd == "sync":
        if workspace is None:
            result = {"mode": "EXPLICIT_ROOT", "synced": False}
        else:
            workspace.pull()
            result = {"mode": workspace.mode, "synced": True, "shared": workspace.shared}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    index_path = _index_path(workspace, args.root)
    mutating = {"init", "markers", "checkpoint", "intent", "close", "sugya", "note", "marker-source"}
    workstream_commands = mutating | {"status", "verify"}
    try:
        if args.cmd == "init":
            project_root = workspace.project_root if workspace is not None else Path.cwd().resolve()
            origin = survey_project(project_root)
            result = store.init(
                args.workstream, task=args.task, next_action=args.next_action, origin=origin
            ).__dict__
            result["origin"] = origin
            result["runtime"] = write_project_runtime(project_root)
        elif args.cmd == "status":
            result = store.load(args.workstream).__dict__
            result["current_actor"] = {k: v for k, v in actor.items() if v}
            origin = store.load_origin(args.workstream)
            if origin is not None:
                result["origin"] = origin
        elif args.cmd == "markers":
            result = store.set_markers(args.workstream, _kv(args.pairs)).__dict__
        elif args.cmd == "verify":
            if args.pairs:
                result = store.verify_resume(args.workstream, _kv(args.pairs))
            else:
                r = store.load(args.workstream)
                resolved, unresolved, errors = _resolve_configured_markers(
                    store, workspace, args.root, args.workstream, r.authoritative_markers
                )
                if unresolved or errors:
                    result = {
                        "status": "VERIFICATION_REQUIRED",
                        "unresolved_markers": unresolved,
                        "resolver_errors": errors,
                    }
                else:
                    result = store.verify_resume(args.workstream, resolved)
        elif args.cmd == "marker-source":
            source = parse_marker_source(args.source)
            kinds = store.set_marker_kind(args.workstream, source.key, source.kind)
            locator_written = None
            if source.locator:
                locator_path = _marker_locator_path(workspace, args.root, args.workstream)
                locator_path.parent.mkdir(parents=True, exist_ok=True)
                data = json.loads(locator_path.read_text(encoding="utf-8")) if locator_path.exists() else {}
                data[source.key] = source.locator
                locator_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                locator_written = source.locator
            result = {"marker": source.key, "kind": source.kind, "locator": locator_written, "marker_kinds": kinds}
        elif args.cmd == "checkpoint":
            result = store.transition(
                args.workstream,
                expected_checkpoint=args.expected_checkpoint,
                status=args.status,
                task=args.task,
                next_action=args.next_action,
                verified=args.verified,
                blockers=args.blockers,
                do_not=args.do_not,
                reason=args.reason,
            ).__dict__
        elif args.cmd == "intent":
            effects = [{"description": e, "state": "UNKNOWN"} for e in args.effect]
            result = {"inflight_id": store.open_inflight(args.workstream, args.intent, effects)}
        elif args.cmd == "close":
            result = store.close_inflight(args.workstream, args.inflight_id, state=args.state, evidence=args.evidence).__dict__
        elif args.cmd == "sugya":
            result = {
                "sugya_id": store.add_sugya(
                    args.workstream,
                    expected_checkpoint=args.expected_checkpoint,
                    title=args.title,
                    premise=args.premise,
                    question=args.question,
                    test=args.test,
                    result=args.result,
                    resolution=args.resolution,
                    caveat=args.caveat,
                    evidence=args.evidence,
                    supersedes=args.supersedes,
                )
            }
        elif args.cmd == "note":
            result = {
                "breadcrumb_id": store.add_breadcrumb(
                    args.workstream,
                    expected_checkpoint=args.expected_checkpoint,
                    state=args.state,
                    what=args.what,
                    why=args.why,
                    evid=args.evid,
                    impact=args.impact,
                    supersedes=args.supersedes,
                )
            }
        else:
            raise AssertionError(args.cmd)

        if args.cmd in mutating:
            _reset_observer_after_canonical_write(
                workspace, args.cmd, getattr(args, "workstream", "") or ""
            )

        if args.cmd in workstream_commands:
            _set_active_workstream(workspace, args.root, args.workstream, actor)

        if workspace is not None and args.cmd in mutating:
            workspace.push(message=f"talmudic: {args.cmd}")
            GemaraIndex(index_path).build(workspace.canonical_root)
    except (ContinuityError, ValueError) as e:
        print(json.dumps({"error": str(e)}))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    if args.cmd == "verify" and result.get("status") in {"VERIFICATION_REQUIRED", "RECOVERY_REQUIRED"}:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
