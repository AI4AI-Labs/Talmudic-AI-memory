# Talmudic AI Memory

> **The agent dies. The work is immortal.**

**Talmudic** names the reasoning shape — premise → dispute → ruling → reopen-if. It is infrastructure for project judgment, not religious content.

**Agents are temporary. Project intelligence should compound.**

Talmudic gives an AI-built project a **Gemara**: durable project judgment that survives the agent, session, model, and IDE that produced it.

Gemara remembers **what was decided, why, why not, and when to reconsider it**.

Git remembers what changed. Built-in agent memory remembers the user and conversation. **Gemara remembers what the project learned.**

Beta **0.3.0b1** · Cursor + Claude Code · Git-backed · model-agnostic · Apache-2.0  
Day-to-day usage: [USER_GUIDE.md](USER_GUIDE.md) · Evidence: [docs/ASSAY.md](docs/ASSAY.md)

---

## Project immortality, not infinite context

An agent can disappear. A chat can be deleted. Tomorrow's agent can be a different model in a different IDE with no access to the conversation that shaped the project.

**The project should still know what it learned.**

Talmudic does not try to make an AI session immortal. It makes the project's accumulated judgment survive the agents that produced it.

```text
Agent A ──learns──┐
Agent B ──learns──┤
Agent C ──learns──┤
                  ▼
               GEMARA
                  │
        accumulated judgment
                  │
                  ▼
Agent D ──inherits what matters
```

That includes something normal project artifacts routinely lose: **the plausible paths that were already tried, rejected, and understood.**

A future agent can often inspect the code and infer why the selected implementation works. It cannot inspect code and discover every attractive alternative previous agents already killed.

**Why-not is project intelligence.**

## Sugya = a structured decision record (Talmud-style reasoning unit)

A **Sugya** is one recorded argument, not a transcript.

```text
S-0142 — Local project storage

Selected:
  SQLite as the local disposable index.

Rejected:
  Synchronizing the SQLite database itself through Git.

Why not:
  Binary synchronization creates merge and locking risk.

Reopen if:
  The storage model changes enough to remove those constraints.
```

A commit can show that SQLite landed. Gemara preserves the judgment surrounding it.

When a replacement agent proposes the rejected path, it can retrieve `S-0142`, understand why it was rejected, and check whether the reopen condition has actually occurred.

Old reasoning is not sacred. **It is challengeable, supersedable project history.**

## What Gemara remembers

Gemara is deliberately narrower than “remember everything.”

It preserves what a competent replacement agent would otherwise have to rediscover:

- **what** was decided;
- **why** it was decided;
- **why not** the rejected alternatives;
- **when** a decision should be reopened;
- current workstream state and the next safe action;
- durable operations that are still unresolved.

### Different records solve different problems

| Capability | **Gemara** | Built-in agent memory (Claude, Cursor, etc.) | Git / changelog | Leading memory plugins |
|---|---|---|---|---|
| Primary purpose | **Preserve project judgment** | Remember user/session context | Preserve code/change history | Preserve or retrieve past context |
| Records decisions | **Structured record** | Sometimes | Outcome usually visible | Product-dependent |
| Records decision rationale | **Explicit field** | Sometimes | Sometimes | Product-dependent |
| Records rejected alternatives | **Explicit field** | Rarely | Rarely | Product-dependent |
| Records why an alternative was rejected | **Explicit field** | Rarely | Rarely | Product-dependent |
| Records when to reconsider | **Explicit reopen condition** | No standard mechanism | Rarely | Product-dependent |
| Tracks unresolved durable operations | **In-Flight record** | No standard mechanism | No | Product-dependent |
| Cross-agent / cross-model continuity | **Designed into the data model** | Host-dependent | Code/history only | Product-dependent |
| Retrieval strategy | **Indexed, bounded retrieval** | Host-controlled | Search/history | Usually retrieval-based |
| Canonical reasoning history | **Yes, with record IDs and provenance** | No standard mechanism | Commit history ≠ reasoning | Product-dependent |

**Use built-in memory to remember the user. Use Git to remember changes. Use Gemara to remember judgment.**

The distinction is not primarily where text is stored. It is **what is preserved and what the next agent is expected to do with it**.

## Cross-agent continuity, tested

We did not only ask whether Gemara could store reasoning. We tested whether a replacement agent could inherit it.

### Replacement-agent smoke

The Cursor test writes distinctive project decisions in **Chat A**, then opens a **new Chat B** and requires it to recover those decisions from Gemara rather than re-derive them from repository state or conversation memory.

```text
Chat A                         Chat B
populate Gemara  ──────────►  fresh session
                              search index
                              retrieve S-#### / R-####
                              recover prior judgment
                              avoid the stale rejected path
```

Result:

```text
POPULATE PASS  →  RESUME PASS
```

A deliberately planted rejected-path trap makes the distinction observable: the replacement agent should find the recorded reasoning and refuse the stale proposal because of **project history**, not because it happens to reason its way to the same answer again.

Hard numbers from [docs/ASSAY.md](docs/ASSAY.md) — not invented marketing stats:

| Measurement | Result |
|---|---|
| Two-agent smoke (Chat A dies → Chat B) | `POPULATE PASS` → `RESUME PASS` |
| SessionStart pointer (10 / 50 / 150 Sugyot) | **237 tokens, flat** |
| Targeted `orient` fetch (same sizes) | **2,065 tokens, flat**; planted rejection still found |
| Full `digest` dump (same sizes) | **488 → 2,047 → 5,886** (grows with history) |
| Cloud killpoint (new session, no handoff) | Recovered In-Flight as **RECOVERED**; did **not** re-run an already-applied migration |

Gold is `FETCH BOUNDED`: the map stays small while a dump does not. At a tiny corpus a dump can still be cheaper than one fetch — that caveat is in the assay.

### Bounded retrieval as Gemara grows

Continuity is not useful if every new session has to swallow the entire past.

The stress harness grows a throwaway Gemara through **10, 50, and 150 records**, plants a known decision, and measures:

- SessionStart pointer size;
- targeted `orient` / `recall` retrieval;
- repeated fetch cost during work;
- full-`digest` cost as history grows;
- whether the planted decision remains retrievable.

Gold result:

```text
FETCH BOUNDED
```

The startup pointer stays small and the relevant decision remains retrievable without injecting the whole Gemara.

At very small corpus sizes, dumping everything can be cheaper than one structured fetch. The result is about **scaling behavior**, not a claim that retrieval is always cheaper.

The Cursor development line reached **203 passing tests** while adding this continuity and bounded-retrieval path. Those are engineering tests, not a universal productivity claim. The next evidence layer is controlled **Gemara vs no-Gemara** testing of repeated errors, rejected-path recurrence, redundant investigation, cross-agent contradictions, operator corrections, and correct reopening of stale decisions.

## Map, not dump

More memory is not automatically better memory.

Talmudic's normal path is:

```text
              GEMARA
                 │
                 ▼
        disposable local index
                 │
          task-specific search
          orient / recall
                 │
                 ▼
         relevant records only
                 │
                 ▼
             next agent
```

SessionStart injects a small **index pointer**, not the Gemara.

The agent searches for the current task and retrieves the relevant reasoning. Thousands of unrelated Sugyot stay out of context.

`digest` exists for operator/debug use. It is deliberately not the normal startup strategy.

## No model owns the Gemara

Claude, Cursor, GPT, Grok, and whatever comes next are participants in a project. None of them is the authority merely because it wrote a record.

Agent/model identity is **provenance, not ownership**.

A Gemara record can be challenged. New evidence can satisfy a reopen condition. New reasoning can supersede old reasoning without silently erasing the history that produced it.

That is the point: **continuity without freezing thought.**

## How Talmudic stores it

With a Git remote, canonical Gemara lives on a dedicated `talmudic-memory` branch, separate from product code.

```text
product branches                  talmudic-memory
(main / feature / develop)        (shared Gemara)
        │                               │
        └── product code                └── workstreams/
                                                │
<project>/.talmudic/                      canonical records
  runtime.json
  cache/index.db  ← disposable
```

The canonical records cover three continuity classes:

| Class | Record | Purpose |
|---|---|---|
| **STATE** | Resume / Checkpoint | Where the work stands and the next safe action |
| **REASONING** | Sugya / note | Why, why-not, evidence, reopen condition |
| **OPERATION** | In-Flight | Durable action stays open until verified or failed |

Never merge `talmudic-memory` into product `main`. Never hand-edit canonical Gemara. The local SQLite index is disposable and rebuildable.

No Git remote means Talmudic falls back to local-only continuity.

## Install

Python 3.10+ as `python`, `python3`, or Windows `py -3`.

### Cursor

Import:

```text
https://github.com/AI4AI-Labs/talmudic-ai-memory
```

Track **`main`**, enable **Talmudic AI Memory**, then start a new Agent chat.

Updates: Dashboard → Plugins → **Refresh**.

### Claude Code

```bash
claude plugin marketplace add AI4AI-Labs/talmudic-ai-memory
claude plugin install talmudic-memory@talmudic-ai-memory
```

Start/restart Claude Code after installation.

### Enable Talmudic in a Cursor project

> **Required for Cursor:** installing the plugin does not automatically activate Talmudic in every repository.

Cursor currently loads an installed plugin beyond a single-project scope. Talmudic therefore uses a small project-level activation marker so its hooks **no-op in repositories that did not explicitly enable it**. This is a Cursor scoping safeguard, not part of the Gemara storage format.

In each Cursor project where you want Talmudic active, create:

```text
.cursor/talmudic.json
```

with:

```json
{"enabled": true}
```

Then start a **new Cursor Agent session** and run:

```text
/talmudic-init
```

Init creates/manages the local `.talmudic/` runtime state, maps the project/workstream through pointers, and asks before seeding project reasoning. It does **not** ingest the repository as a giant memory dump.

**Do not create `.talmudic/` manually.** Existing `.talmudic/` also activates Talmudic for compatibility with already-initialized projects; an explicit `{"enabled": false}` marker disables it.

This activation marker is **Cursor-specific**. Claude Code does not require `.cursor/talmudic.json`.

Do not run `/talmudic-init` on the Talmudic plugin repository itself.

## Daily commands

| Command | Purpose |
|---|---|
| `/talmudic-remember` | Preserve something a replacement agent must not rediscover |
| `/talmudic-recall` | Retrieve prior project reasoning |
| `/talmudic-status` | Inspect current workstream state |
| `/talmudic-doctor` | Diagnose/repair disposable local machinery |
| `/talmudic-init` | Initialize Talmudic for a project/workstream |

A useful test before Remembering something:

> **Would a competent replacement agent otherwise waste meaningful work or make the wrong move?**

If not, don't preserve it.

## Design invariants

1. **The Gemara is not a transcript.**
2. Systems of record remain authoritative.
3. Resume describes now; history explains why.
4. **Why-not is first-class memory.**
5. Unknown is not safe; applied is not verified.
6. Old reasoning is superseded, not silently erased.
7. No agent, model, or IDE owns the Gemara.
8. Doctor and indexing never rewrite canonical history.
9. Material writes require an explicit In-Flight operation.
10. The next agent gets a **map, then relevant memory — not the whole past.**

## Documentation

- **[User Guide](USER_GUIDE.md)** — install, opt-in, daily workflow, commands.
- **[Thesis](docs/THESIS.md)** — why the name, origin, and what we are not calling this.
- **[Cursor adapter](.cursor-plugin/README.md)** — Cursor-specific hooks and cloud behavior.
- **[Claude Code adapter](.claude-plugin/README.md)** — Claude-specific installation and hook mapping.

## Status

Talmudic AI Memory is an **open beta**.

The core continuity mechanics, cross-agent retrieval path, bounded-fetch architecture, and host integrations are tested. The broader question — how much Gemara reduces real-world repeated mistakes and operator correction across heterogeneous agents — is the next benchmark layer.

We would rather publish the boundary of the evidence than turn a smoke test into a marketing number.

## License

Apache 2.0. See [LICENSE](LICENSE).
