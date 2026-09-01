# Talmudic Memory — User Guide

**The agent dies. The work is immortal.**

Decision archaeology for coding agents.

Gemara shares **project intelligence** — the why, and especially the why-not. Not a changelog, not chat Memory, not a vector store. The next agent gets **why this, why not that, and when to reconsider it.**

For mechanics and the Gemara-vs-Memory comparison, start with [README.md](README.md).

## The 30-second mental model

```text
chat Memory  → remembers you
git          → remembers what changed
vector store → similar text
Gemara       → remembers why this, and why not that
```

A good Talmudic record is not “worked on database code.”

It is:

```text
Keep SQLite.
Rejected Postgres because X.
Reopen if Y changes.
```

That is useful to a replacement agent.

## Install once

### Cursor

Import `https://github.com/AI4AI-Labs/talmudic-ai-memory`, track **main**, enable **Talmudic AI Memory**, and open a new Agent chat.

After an update: Dashboard → Plugins → **Refresh**.

### Claude Code

```bash
claude plugin marketplace add AI4AI-Labs/talmudic-ai-memory
claude plugin install talmudic-memory@talmudic-ai-memory
```

Restart/start a fresh Claude Code session.

Requirements: Python 3.10+ as `python`, `python3`, or Windows `py -3`.

## Opt in a product project

Create:

```text
.cursor/talmudic.json
```

with:

```json
{"enabled": true}
```

Start a **new** session, then run:

```text
/talmudic-init
```

Init maps the project through pointers such as README/architecture paths and asks before seeding decisions. It is not a repository dump. If an old note says `/talmudic-origin`, that is this command — do not repeat the old name.

Do **not** init-map the Talmudic plugin repository itself.

## The daily loop

```text
new task / new agent
        │
        ▼
SessionStart: "Talmudic Memory is active"
        │
        ▼
search index for THIS task
   orient / recall
        │
        ▼
do the work
        │
        ▼
Remember only what a replacement agent
would otherwise have to rediscover
        │
        ▼
close the session
```

Short sessions are fine. Cursor today and Claude Code tomorrow are fine. The project continuity is not owned by either chat.

### What the agent should do at startup

The normal path is **not** “read all memory.”

SessionStart provides an index pointer. The agent searches for the current task and fetches the relevant Gemara slice. If it needs the reason Postgres was rejected, it should retrieve that record and quote its `S-####` / `R-####` id.

Do not make `digest` the default startup action.

Cursor cloud agents skip SessionStart; the installed project rule tells them to search the index instead.

## Commands

| Command | Use when |
|---|---|
| `/talmudic-init` | First-time project/workstream mapping |
| `/talmudic-remember …` | A future agent must not lose this state, operation, decision, rejection, or reopen condition |
| `/talmudic-recall …` | “Why did we reject X?” / “What did the previous agent establish?” |
| `/talmudic-status` | You need the current workstream state |
| `/talmudic-doctor` | Disposable index/cache needs diagnosis or repair |

Remember classifies candidate memory as **NONE**, **STATE**, **OPERATION**, or **REASONING**. Not every turn deserves a record.

## What to Remember

### Good

- “Use adapter A because B breaks on Windows; reconsider when upstream issue #123 is fixed.”
- “Rejected committing SQLite itself through Git because binary merge/locking makes it unsafe.”
- “Migration is open; production write has happened but verification has not.”
- “This ADR is stale; S-0042 supersedes it.”

### Bad

- “Edited three files.”
- A transcript.
- Every tool call.
- A generic summary of the repository.
- Something Git already says clearly and that carries no future judgment.

The test is simple:

> **Would a competent replacement agent otherwise waste meaningful work or make the wrong move?**

If no, do not Remember it.

## Host Memory is not Gemara

| Host Memory | Git | Gemara |
|---|---|---|
| “I prefer concise answers.” | “Switched to SQLite.” | “Rejected Postgres because X; reopen if Y.” |
| User/chat-owned | Repo history | Workstream-owned |
| Vendor-specific | Shared code | Shared project judgment |

Use `/talmudic-remember` for project continuity. A host's `/remember` is a different product surface.

## Shared Gemara

With a Git remote, canonical continuity lives on the dedicated `talmudic-memory` branch.

Product branches contain product code. They do **not** contain the Gemara.

Local `.talmudic/cache/` is disposable retrieval machinery. It can be rebuilt. Doctor and index maintenance may repair that local machinery but must never rewrite canonical history.

Never:

- merge `talmudic-memory` into product `main`;
- hand-edit canonical records;
- delete the memory branch casually;
- treat the SQLite index as canonical;
- dump the full Gemara into every model context.

## Material writes

Talmudic distinguishes “I intend to do this” from “the durable effect is verified.”

Material operations such as a guarded `git push` require an **In-Flight** record. The guard denies the operation when no unambiguous open intent exists.

That makes operation memory different from a TODO: it tracks the gap between **planned, applied, and verified**.

## What the tests establish

The current smoke path demonstrates a fresh Chat B recovering decisions written by Chat A from Gemara (`POPULATE PASS → RESUME PASS`) without rewriting the stored reasoning.

The scaling harness grows a throwaway Gemara through 10, 50, and 150 records and checks that SessionStart stays a small pointer while targeted retrieval still finds the planted decision. The intended result is `FETCH BOUNDED`, not “load all memory.”

These tests validate continuity and retrieval mechanics. They do not yet prove a universal productivity percentage. Controlled Gemara-vs-no-Gemara project-quality benchmarks are the next evidence layer.

The professional write-up of methods, gold, live trap protocol, dual-harness Chat B, and the bounded-fetch numbers: [docs/ASSAY.md](docs/ASSAY.md).

## If something looks wrong

Run:

```text
/talmudic-status
/talmudic-doctor
```

Doctor is allowed to repair disposable local machinery. It is **not** allowed to “fix” history.

If Recall conflicts with current external reality, do not blindly obey memory. Verify the authoritative system and, when warranted, supersede the old reasoning with the new evidence and reopen condition.
