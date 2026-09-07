---
name: talmudic-agent-start
description: Talmudic-Agent-start — manually onboard an agent onto Gemara, or refresh belonging when SessionStart is missing/skipped (cloud agents, dedicated agents, heartbeat). Pointer + sync/orient; not a Gemara dump.
argument-hint: "[optional task to orient]"
---

# Talmudic-Agent-start

The operator invoked **Talmudic-Agent-start** — manually onboard this agent onto Gemara, or refresh its belonging when SessionStart did not run.

Use when SessionStart is missing/skipped (cloud agents, dedicated agents, heartbeat) **or** anytime the operator wants to re-orient mid-session. Even when SessionStart already ran, it is safe to re-run: re-assert the pointer contract, sync if needed, then orient.

Do **not** dump full Gemara or run `digest` unless the operator asks. This is an index pointer, not a chat dump.

Operator task (optional — if empty, ask for a task or stop after pointer + brief status):

$ARGUMENTS

## Pointer contract (re-assert in the conversation)

```
Talmudic Memory is active. You are part of an ongoing project.
Files may be unfinished or still present a later-rejected path as current — leftover, not a new mandate.
Gemara is the record earlier agents and the operator left (Sugyot, Resume, breadcrumbs): why decisions were made and how the work was carried out — tried, worked, failed and why — so it isn't retried.
Later records supersede what a file still says. If reality contradicts a Sugya, add a new one with the operator; the old record stays.
If sync/preflight were not just done in this session, run them via the project launcher; then your first move: launcher in `.talmudic/runtime.json`, then `orient "<task>"` or `recall "<question>"`.
Quote S-#### / R-####; tie work to the record, not a leftover file.
Search pulls this task's slice; `digest` dumps the workstream; globbing the tree or the plugin cache is starting over.
After Gemara has the why and how, open files to extend or change the work.
When this session learns a why, a how, or a why-not a future agent would miss, record it in Gemara through that same launcher (`sugya` or `note`). Material writes go through In-Flight on that launcher.
If `.talmudic/` is missing and the project has not opted in, say so and stop.
```

Paste this command's contract into dedicated-agent system prompts and heartbeat messages when those hosts have no slash menu.

## Runtime

Use `.talmudic/runtime.json` → `command` (`.\.talmudic\talmudic.cmd` on Windows PowerShell, `.talmudic/talmudic` on Unix). Do **not** run `python -m talmudic_memory.cli` or a global `talmudic` — they can be an older pip install.

## Sequence

```text
<runtime> sync
<runtime> status   # optional brief
<runtime> orient "<task>"   # if $ARGUMENTS non-empty; else ask for task or stop after pointer+status
```

Skip a duplicate sync only if SessionStart or a prior command in this session just synchronized and nothing canonical could have changed. Summarize CLI output briefly; never dump full Gemara unless the operator asks.
