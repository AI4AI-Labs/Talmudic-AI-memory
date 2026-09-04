---
name: talmudic-memory
description: Project intelligence (Gemara) via the talmudic CLI — why and why-not, not Claude Memory or MEMORY.md. At the start of work in an opted-in Talmudic project (`.cursor/talmudic.json` enabled or `.talmudic/` present), and whenever the operator says Remember/Recall/Status/Doctor, Talmudic Init, or invokes /talmudic-remember, /talmudic-recall, /talmudic-status, /talmudic-doctor, /talmudic-init. If this workspace is not opted in, do not use this skill. Persist workstream judgment so a future agent can resume. If you see /talmudic-origin, that is /talmudic-init.
---

# Talmudic Memory — Workstream Continuity Skill

## What this skill does

Keep the work alive even when the current agent/session/context disappears.

Do not preserve the conversation. Preserve the **intelligence of the project**: current state, why a choice was made, **why alternatives were not**, evidence pointers, and recovery information. The why-not is usually trapped in one session; Gemara is how it is shared.

The user-facing vocabulary is intentionally small:

- **Remember** — preserve something future work should not lose.
- **Recall** — retrieve a past decision, rationale, result or state.
- **Status** — show where the workstream stands and what changed since this participant last saw it.
- **Doctor** — diagnose Talmudic machinery; Doctor may repair disposable cache/index only, never canonical Gemara.

Internal CLI primitives remain available for hooks/recovery, but do not make the user learn them.

This is **not** Claude Memory. "Remember this" in a chat must not be routed to MEMORY.md or the host memory plugin. Persist project decisions with `/talmudic-remember` (or the Remember router below) and the `talmudic` CLI.

Operator slash commands (Claude Code `/help` Custom commands, Cursor `/` command menu):

- `/talmudic-remember` — classify NONE / STATE / OPERATION / REASONING, then write Gemara.
- `/talmudic-recall` — search Gemara.
- `/talmudic-status` — current Resume.
- `/talmudic-doctor` — health of local machinery only.
- `/talmudic-init` — first-time map of an existing project. `init` surveys automatically (A). Then **question the operator** before seeding a few Sugyot from the current changelog slice and designs (B). Stop after A if they are silent. Do not dump document bodies.

If you encounter `/talmudic-origin` or “Talmudic Origin” in old Gemara, chats, or PRs: that is `/talmudic-init`. Do not repeat Origin as the operator command. `origin.json` is the internal pointer-map file, not a slash command. Git remotes named `origin` are unrelated.

Do not name a command `/remember`. That collides with Claude Memory.

## Start of work (opt-in gate)

This skill applies only when the current workspace is opted in: `.cursor/talmudic.json` is `{"enabled": true}`, or `.talmudic/` already exists.

If neither is present, stop using this skill (no-op). Do not create `.talmudic/`, do not copy rules or commands, and do not run the CLI.

When opted in, before investigating, planning, or implementing: if this conversation already contains "Talmudic Memory is active" (`hooks_context` / SessionStart), you are joining an ongoing project. Files may be unfinished or still present a later-rejected path as current — leftover, not a new mandate. Gemara is the record earlier agents and the operator left: why decisions were made and how the work was carried out — tried, worked, failed and why — so it isn't retried. Later records supersede what a file still says. If reality contradicts a Sugya, add a new one with the operator; the old record stays. Sync and preflight already ran. Your first move: launcher in `.talmudic/runtime.json`, then `orient "<task>"` or `recall "<question>"`. Quote record ids; tie work to the record, not a leftover file. Search pulls this task's slice; `digest` dumps the workstream; globbing the tree or the plugin cache is starting over. After Gemara has the why and how, open files to extend or change the work. You inherit this handoff, and it's yours to keep current: when this session learns a why, a how, or a why-not a future agent would miss, record it in Gemara through that same launcher (`sugya` or `note`). Then continue this skill.

If SessionStart is missing (cloud agents skip it): same first move after resolving the launcher. `/talmudic-status` is Resume, not a substitute for searching the index. If the launcher is missing, report a bootstrap problem; do not hunt the repo for source.

## Runtime resolution

On hook-capable hosts, hooks write `.talmudic/runtime.json` (the project launcher pin). Cursor sets `CURSOR_PLUGIN_ROOT` for those hooks; the launcher prefers that over a fallback recorded at write time.

Before invoking the CLI:

1. Use the `command` recorded in `.talmudic/runtime.json` (`.talmudic/talmudic.cmd` on Windows, `.talmudic/talmudic` on Unix). Those launchers pin this plugin checkout.
2. Do not run a global `talmudic` or `python -m talmudic_memory.cli`. Those can be an older pip install.
3. If the launcher is missing, report a runtime/bootstrap problem instead of hunting the repo for source or pretending continuity is active.

Do not assume a user-level console-script directory is on PATH.

## Sync policy — freshness before memory use

Shared Gemara is independent of product-code branches and is persisted aggressively on the dedicated `talmudic-memory` branch.

Use one simple rule:

> **Sync before consuming memory, before acting on memory, and before changing memory.**

This means:

1. **Before answering or planning from project history/state** — synchronize first, refresh the local index when needed, then Recall/Preflight and answer from the refreshed view.
2. **Before substantive work or a new task/workstream** — synchronize first, run change-aware Preflight, then act.
3. **Before any canonical write** — synchronize immediately before the transition, reconcile stale/conflicting state, write, commit, and push immediately when `GIT_SHARED`.

Do not poll continuously and do not inject history on every turn. Synchronize at semantic boundaries where stale memory could cause a wrong answer, duplicate work, stale planning, or conflicting canonical writes.

For `GIT_SHARED`, the normal sequence is:

```text
sync latest talmudic-memory
→ refresh local index if canonical HEAD changed
→ consume/act/write
→ canonical write accepted?
   → commit + push immediately
```

For `LOCAL_ONLY`, the same protocol applies without remote fetch/push.

## Start / Resume — automatic preflight

Before substantive work: if SessionStart already ran in this conversation, skip steps 1–6. First move: search the index for the current task (`orient` / `recall`). Quote record ids from that search. Do not run digest, glob the tree, or hunt the plugin cache.

Otherwise:

1. Resolve the runtime.
2. Bootstrap/connect project continuity and synchronize the latest shared Gemara when available.
3. Treat storage mode explicitly:
   - `GIT_SHARED`: canonical Gemara is on the dedicated `talmudic-memory` branch and shared across participating agents.
   - `LOCAL_ONLY`: continuity is limited to this durable project/harness filesystem; do not claim cross-machine sharing.
4. Identify the active namespaced workstream: `<repo-or-project>/<scope>/<workstream>`.
5. Run change-aware preflight on the synchronized view.
6. Load current Status/Hot Resume.
7. Run `orient "<current user task/request>"` against the synchronized view **before** inspecting the repo or repeating any test/investigation.
8. If preflight reports blocking contract/schema/recovery changes, or orient reports open In-Flight/blockers, reconcile before new material writes. If orient reports `PRIOR_WORK_FOUND`, verify and extend only what is missing/changed instead of repeating the prior investigation.

On hook-capable hosts, SessionStart performs bootstrap/sync + preflight and injects a **pointer**: leftover files are not a new mandate; Gemara holds why and how; you inherit the handoff; first move is the launcher then `orient "<task>"` or `recall "<question>"`; `digest` dumps, search pulls a slice; write `sugya` / `note` on that launcher. Claude Code injects that pointer (`<session_start_digest>`). Cursor Agent (3.18.9+) injects it as `hooks_context` and sets `TALMUDIC_MEMORY=1`. It does **not** dump Sugyot. Cloud agents skip `sessionStart` — then search the index the same way (`orient "<task>"` / `recall "<question>"`). `digest` is an operator/debug dump of the whole workstream and does not scale.

Preflight answers:
- **Where are we now?**
- **What changed since this participant last checked?**

Preflight is a change/safety detector, not a substitute for prior-work lookup — it does not answer "has this exact task already been done?" `orient` answers that for a *specific* task by searching indexed canonical history and returning a compact packet (Resume + relevant Checkpoints/Sugyot/In-Flight + blockers). `recall` answers a question the same way. `digest` is an operator/debug dump of the whole workstream — do not run it at session start; it does not scale to thousands of Sugyot.

**Invariant: no substantial repeated work before canonical prior-work lookup.** Do not start investigating, testing, or re-implementing a task until `orient` or `recall` has been run for it.

No relevant *change* (preflight's concern) means no change-delta should be injected merely for completeness. That is separate from searching the index for the current task.

The `talmudic-memory` branch is continuity infrastructure. **Deleting it deletes the canonical shared Gemara unless another backup exists.** Do not merge it into product/main branches by default.

## Remember router

Before any Remember/canonical transition, synchronize the shared Gemara first when `GIT_SHARED`.

When asked to remember something — or when a hook reaches a meaningful boundary — classify first:

1. **OPERATION** — a durable real-world action is starting/ending → In-Flight open/close/recovery.
2. **STATE** — current work state/next safe action changed → checkpoint/Resume transition.
3. **REASONING** — a meaningful decision, rejection, failure, changed assumption or supersession occurred. Routine progress worth remembering but not worth a full Sugya → a Rationale Breadcrumb (`note`). A surprising failure, contested design choice, or superseded rule that a future agent could otherwise repeat → a Sugya. See "REASONING / Sugya minimum" below for how to choose between them.
4. **NONE** — future work would not regret losing this → write nothing.

Do not create canonical history merely because a user asked a question or a tool was called.

Once a canonical transition is accepted, persist it immediately. In `GIT_SHARED`, commit and push it to `talmudic-memory` without waiting for a product-code commit, task end, PR, or session end.

### REASONING / Sugya minimum

For material decisions preserve compactly:
- what was considered/tested;
- selected approach and why;
- rejected/deferred alternative(s) and why;
- discriminating result when useful;
- caveat/reopen condition;
- evidence/source pointers;
- supersession when applicable.

Preserve externalized engineering rationale, never hidden chain-of-thought.

### Rationale Breadcrumb — the default, Sugya is the exception

Most REASONING-classified moments are routine: a decision was made, a change was applied, something was verified. Use a compact breadcrumb, not a full Sugya:

```text
<runtime> note <workstream> --expected <checkpoint> --state DECIDED --what "<short change>" [--why] [--evid] [--impact] [--supersedes]
```

`--state` is one of `DECIDED | APPLIED | VERIFIED | BLOCKED | SUPERSEDED | REVERTED`. Keep `--what`/`--why` short — this is a breadcrumb, not a report. Each one advances `Resume.ledger_tail`, so the next agent's `orient` / `recall` sees what most recently happened without needing to read full Sugya history.

Reserve a full Sugya for the exception, not the default — create one only when a future agent could otherwise repeat a mistake without the reasoning:
- a surprising failure mode;
- a contested design choice between two plausible approaches;
- a migration or change that produced an unexpected result;
- an older rule being superseded (state why, never silently);
- a guardrail that exists because a real test failed.

When in doubt whether something is routine progress or reasoning worth preserving in full, prefer the breadcrumb — a Sugya can always follow later if the question turns out to matter more than it first appeared.

## Recall

For questions about project history/rationale/state, **synchronize first**. Then search Talmudic Memory before reconstructing intent from current code.

Normal sequence:

```text
<runtime> sync
<runtime> recall "<natural-language question>" [--workstream <id>]
```

If SessionStart or another boundary has just synchronized and no canonical change could have occurred since, an unnecessary duplicate sync may be skipped. When uncertain, synchronize.

The alpha retrieval layer performs deterministic token-ranked lexical recall, so natural-language questions do not need to exactly match stored sentences.

If retrieval returns several plausible records, read the smallest relevant set. Follow evidence/source pointers only when needed. Do not load the full historical ledger by default.

A question itself does not create a Sugya. A newly discovered unresolved question that materially affects future work may become an open/continued reasoning record through the normal Remember router.

## Status

Status is a memory-consuming operation. Synchronize first when shared state may have changed.

Status should present:
- current task;
- lifecycle state;
- checkpoint;
- blockers;
- open In-Flight operations;
- last verified items;
- exact next safe action;
- effective current actor (`agent_id`, `session_id`, `role`, `model`) when available;
- relevant changes surfaced by preflight.

Do not infer current status from source code when canonical Resume is available; verify against systems of record when the Resume itself signals uncertainty/divergence.

## Doctor

Doctor is read-only with respect to canonical Gemara.

It may inspect:
- runtime availability;
- shared branch/mirror state;
- canonical store presence;
- current actor/provenance;
- index integrity/freshness;
- open In-Flight/recovery state.

It may repair/rebuild **only disposable local machinery**, such as the SQLite index/cache. Never repair a bad index by rewriting canonical history.

## Sacred canonical history

The Gemara is append/transition history, not a cache.

Only explicit continuity operations (`init`, `intent`, `close`, `checkpoint`, `sugya`, `note`, marker updates including `marker-source`'s resolver-kind write, and future documented transitions) may write canonical state.

`doctor`, `recall`, `orient`, `digest`, preflight, index build/update/status/rebuild/search, observer hooks and diagnostics are read-only with respect to Gemara. Synchronizing the local mirror from the authoritative remote is a read/freshness operation, not a canonical-history rewrite.

Old reasoning is superseded, not silently erased.

## Material writes — synchronous safety boundary

Before a durable or potentially irreversible operation (DB/schema mutation, deploy/publish, external API write, destructive file/cloud operation, remote configuration change):

1. Synchronize the latest shared Gemara.
2. Ensure the intended workstream is active.
3. Ensure preflight/recovery state is not blocking.
4. Open an In-Flight record with the expected durable effect; persist/push it immediately when shared.
5. Perform the operation.
6. Inspect the real system of record independently.
7. Close as `VERIFIED`/`RECOVERED` only from evidence; otherwise preserve the uncertain terminal state and fail closed; persist/push the close immediately.

Where supported, a synchronous material-write hook enforces this before risky shell operations. The guard itself never writes to Gemara.

`APPLIED != VERIFIED`.

### Marker verification — fail-closed, configure once

`authoritative_markers` on Resume claim what should be true (a commit, a schema version, a file's contents). That claim is only as good as it is actually checked. Configure a resolver once per marker:

```text
<runtime> marker-source <workstream> KEY=KIND[|LOCATOR]     # kinds: git-head, git-state, file-text, file-int, static
<runtime> verify <workstream>                                 # auto-resolves every configured marker
```

`git-head`/`git-state` default their locator to the project repository itself, so the common case needs only the kind. A marker with no configured resolver reports `VERIFICATION_REQUIRED`, not a silent pass — that is the fail-closed guarantee, and it is the reason `verify` with no arguments is meaningfully different from `verify` never being run.

The resolver *kind* is a shared team decision and is canonical/synced. The resolver *locator* (e.g. an absolute repository path) is often machine-specific and stays local to the machine that configured it — never write a locator through anything but `marker-source`.

## Boundary documentation — outcome-driven, vendor-agnostic

Talmudic defines **what continuity outcome must exist**, not how a particular vendor/runtime must produce it.

On hook-capable hosts, nags are one sentence: `Talmudic: Remember this if a future agent would miss it.` They fire immediately on look-here events (plan enter/exit, Cursor switch-to-plan, subagent stop), at Stop after a stretch of ordinary tool activity (default 12 events), and at Stop after 12 chat-only cycles with no tools (`TALMUDIC_NUDGE_EVERY`). They do not re-teach the Remember router. A Remember resets both counters, so an agent that already bookmarks never gets the nag.

The primary agent already holds the relevant working context and should use the cheapest appropriate mechanism available in its runtime. Remember when the story has shape; do not create canonical history merely because a tool was called.

Priority order:

1. **NONE** — nothing future-relevant changed → write nothing and finish.
2. **Simple STATE / OPERATION** — write directly through the Talmudic runtime from current context.
3. **Clear REASONING already present in context** — write the compact Sugya directly.
4. **Reasoning genuinely needs distillation** — delegate only when the runtime provides an economical mechanism and delegation materially improves the record.
5. If delegation is unavailable or expensive, the primary agent writes the compact record itself.

Never spawn a fresh subagent merely to decide `NONE`. Never re-read the project merely to document work the active agent already understands.

The optional `talmudic-scribe` agent is a reasoning distiller, not the default classifier or required lifecycle step.

Hooks write only bounded disposable observer telemetry to `.talmudic/cache/observer.jsonl`; this is not transcript history and not canonical Gemara. Stop counts those lines and nags once per threshold. A successful Remember / canonical CLI write (`note`, `sugya`, checkpoint, In-Flight, …) replaces the spool with one baseline line (`canonical_write`) and resets the watermark — zero model tokens, no Gemara body. The counter then means “tool events since last bookmark,” not “since the session began.” Recall/sync/doctor do not reset it. Talmudic's own documentation machinery (scribe/agent delegation, Talmudic CLI operations, observer cleanup and related control traffic) is not workstream activity and must not create recursive observer delta.

A subsequent Stop below the threshold, with no new look-here event, must pass without a suggestion.

## Index maintenance — internal

The SQLite index is disposable and non-authoritative. It follows the local synchronized canonical view; it is never pushed or shared.

Internal maintenance primitives:

```text
index build
index update
index status
index rebuild
index search
```

Normal users should ask Doctor/Recall rather than choose maintenance primitives themselves. `index rebuild` changes only local index/cache state.

## Cross-workstream learning

You may Recall relevant Sugyot from another namespaced workstream when explicitly useful. Synchronize first, then treat retrieved records as project history/evidence, not authorization to write into that other workstream.

## Provenance

Meaningful canonical contributions carry one compact actor shape when available:
- `agent_id`;
- `session_id`;
- `role`;
- `model`.

The effective actor is shared across hook state, CLI provenance, Status and preflight. Identity is provenance, not authority. No participant owns the Gemara. Host-unexposed fields may remain unknown rather than being guessed.

## Recovery rule

If documented state and authoritative state disagree:

`NO NEW MATERIAL WRITE`

Reconcile first. If an effect may already exist and cannot be proven absent, fail closed rather than replaying it.

## Minimalism

The active working agent should spend as little additional effort as possible on continuity administration. Reuse context already loaded in the primary model. Hooks provide lifecycle discipline; the Core provides deterministic persistence/safety; optional delegation is reserved for reasoning that genuinely benefits from distillation. Recall retrieves only relevant history; canonical Sugyot contain only future-relevant rationale.

Do not continuously poll. The synchronization policy is boundary-driven: freshness before memory-dependent answers/planning, before substantive work, and before canonical writes.