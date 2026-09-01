---
name: talmudic-remember
description: Persist project continuity into the Talmudic Gemara via the talmudic CLI. Not Claude Memory, not MEMORY.md.
argument-hint: "[what a future agent must not lose]"
---

# /talmudic-remember

The operator invoked **Talmudic project intelligence**, not Claude Memory.

Do **not** use Claude Memory, MEMORY.md, user-memory tools, or "save to memory" plugins. Those store personal/chat facts. This command writes **workstream intelligence** (Gemara) through the `talmudic` CLI only: the why, and the why-not — not a changelog recap.

Operator text (may be empty):

$ARGUMENTS

## Runtime

1. Use the `command` in `.talmudic/runtime.json` (`.\.talmudic\talmudic.cmd` on Windows PowerShell, `.talmudic/talmudic` on Unix).
2. Do **not** run `python -m talmudic_memory.cli` or a global `talmudic` — they can be an older pip install.
3. If the launcher is missing, report a runtime problem. Do not pretend a write happened.

When `GIT_SHARED`, `sync` immediately before any canonical write.

## Choose the mechanism, then write

Classify first. Tell the operator which you chose.

1. **NONE** — a future agent would not miss this → write nothing and say so.
2. **OPERATION** — a durable real-world action is starting/ending → `intent` / `close` (In-Flight).
3. **STATE** — current task / next safe action changed → `checkpoint`.
4. **REASONING** — a decision, rejection, failure, or supersession:
   - routine progress → `note` (breadcrumb). Default.
   - a future agent could otherwise repeat a mistake or re-propose a rejected path → `sugya` (why this, **why not** the alternatives, when to reopen).

Do not spawn `talmudic-scribe` merely to decide NONE. Do not hand-edit Gemara files. After a successful CLI write, say the record id and stop.
