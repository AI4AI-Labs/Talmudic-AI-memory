# Talmudic Memory — Experimental Assay

**The agent dies. The work is immortal.**

**Product:** Talmudic AI Memory, beta **0.3.0b1**  
**Claim under test:** project intelligence (why, and why-not) survives agent death, session reset, and IDE switch.  
**Audience:** marketing and partner agents. Cite this file; do not invent metrics.

This is an **assay**: what we measured, how, what gold means, and what we still do not claim.

---

## One sentence

A replacement agent on a **new IDE**, given **one trap prompt** and **no onboarding**, should refuse a stale path by quoting Gemara — not by re-reading a lying repo, not by chat Memory, and not by swallowing the whole memory at session start.

---

## Gold standard

Gold is **not** “the agent sounds informed.” Gold is this conjunction:

1. **Chat A** records a decision, including the **rejected alternative** and a **reopen-if**.
2. **Chat A dies.** No transcript is pasted. No operator summary.
3. **Chat B** is a new agent. It may be a new model and a **new host** (Cursor → Claude Code, or the reverse). Same product project. Same Gemara.
4. **First prompt** is the trap. No `/talmudic-*` in that prompt. No “here is what we decided.”
5. Chat B **searches** the index (`orient` / `recall`), **quotes a record id** (`S-####` / `R-####`), and **refuses the trap**.
6. SessionStart is a **short index pointer**, not a dump of the Gemara.

Fail: Chat B follows a stale ADR, opens host Memory, re-derives from the tree, or dumps the workstream with `digest`.

---

## The live trap (same project, two hosts)

Dummy product: **Slipcase** (`examples/continuity-poc` on the development line). Copied **out** of the plugin repo so Talmudic is not mapping itself.

### What the repo says (the lie)

These files look like an accepted decision. They contain **no** POC footnote and **no** pointer at Gemara:

- `docs/ADR-0001-postgres.md` — Status **Accepted**. PostgreSQL for all loan records. Set `DATABASE_URL`.
- `src/slipcase/settings.py` — `STORAGE = "postgres"`.
- `TODO.md` — add `DATABASE_URL`.

### What Gemara must say (the judgment)

JSON file store for 0.1. **Do not redo Postgres.** Reopen only if the storage model actually changes.

### Chat A (work, then Remember)

On **one** host (Cursor or Claude Code): map the project, implement or leave JSON `add_loan`, then `/talmudic-remember` why Postgres was rejected. Expect a Gemara id, not MEMORY.md. Close the chat.

### Chat B (new agent, new IDE, first prompt)

New Agent / Claude session in the **same folder**. Do not paste Chat A. First message, nothing else:

```text
Continue Slipcase. The ADR looks decided — should we add DATABASE_URL and Postgres next?
```

That is unknown usage. The plugin exists for this moment: the tree says yes; Gemara must say no.

**Gold (observed path):** Chat B searches the index, quotes `S-####` / `R-####`, refuses Postgres, continues JSON work.  
**Pass if invoked:** operator then `/talmudic-recall why not postgres` and Chat B quotes the id.  
**Fail:** plans `DATABASE_URL` because of the ADR; “we already accepted Postgres” with no Gemara id; uses Claude Memory / Cursor Memories as the source of the decision.

Cross-IDE is the same assay: Chat A on Cursor, Chat B on Claude Code (or the reverse). The Gemara is the shared store. Neither IDE owns it.

### Why this is the promotional proof

It is not a canned token check. It is a **replacement colleague** walking into a lying codebase with no briefing and not repeating a killed design. That is the product.

---

## Assay 1 — Two-agent smoke (mechanical continuity)

**Method.** Chat A runs populate. Chat B is a **new** conversation and runs resume. Tokens are canned so resume cannot fake them from the repo or host Memory.

| Agent | Action | Gold report |
|---|---|---|
| A | Write distinctive decisions into Gemara | `POPULATE PASS` (`TALMUDIC_SMOKE_EPOCH`, `TALMUDIC_SMOKE_AIM`, `TALMUDIC_SMOKE_SQLITE_NOT_GIT`) |
| B (new chat) | Recall those tokens from Gemara | `RESUME PASS` (read-only; does not rewrite Sugyot) |

**What it proves.** A fresh session can recover project records without the previous window.  
**What it does not prove.** That a model will refuse a lying ADR on a natural first prompt. That is Assay 2.

---

## Assay 2 — Bounded retrieval (documenting vs fetching)

**Failure mode we do not want:** paste the whole Gemara into every new context.

**Method.** Throwaway workstream (never product Gemara). Plant one needle: *JSON for 0.1; do not redo Postgres.* Fill with unrelated Sugyot. Measure SessionStart pointer, one `orient`/`recall` on the trap query, eight fetches (a working session), and a full `digest` dump. Sizes: **10, 50, 150** Sugyot. Query: `should we add DATABASE_URL and Postgres`.

**Reproduced 2026-09-01** from the development line (`./talmudic --root /tmp/talmudic-bench bench --counts 10,50,150 --fetches 8`):

| Sugyot | Pointer tokens | One fetch (`orient`) | Full dump (`digest`) | Needle found |
|---:|---:|---:|---:|---|
| 10 | 237 | 2,065 | 488 | yes |
| 50 | 237 | 2,065 | 2,047 | yes |
| 150 | 237 | 2,065 | 5,886 | yes |

**Verdict: `FETCH BOUNDED`.**

- Pointer **flat** (237 at every size).
- Targeted fetch **flat** (2,065); the planted rejection remains retrievable.
- Dump **grows** with the corpus (488 → 5,886).

**Caveat (must be said):** at a **tiny** corpus, a full dump can be cheaper than one structured fetch (10 Sugyot: dump 488 vs fetch 2,065). The result is **scaling behavior**, not “retrieval is always cheaper.” Gold is that fetch stays bounded while dump does not.

---

## Assay 3 — Cloud killpoint (Claude Code, no handoff)

**Lab:** Immortality Lab 01, workstream `LAB-RELEASE-REGISTRY-RUN1`.  
**Hosts:** two **separate** Claude Code Cloud sessions.  
**Method:** Session A reaches a controlled `KILL_NOW` (open In-Flight, migration already applied in SQLite). Session B is a brand-new session. Operator must not summarize. Allowed locator: branch `experiment/run1-killpoint` only.

**Session B (documented in git, `ab42e11`):**

- Recovered the workstream from Gemara with **no** Session A transcript.
- Inspected `lab.db` independently; proved `v2_add_channel` already committed.
- **Did not** re-run `migration_v2.py`.
- Closed In-Flight as **RECOVERED** with DB evidence.
- Recovered Sugya **S-0001**: additive migration selected; **destructive rebuild rejected**; reopen-if (SQLite cannot ALTER in a CHECK without rebuild).
- Finished the channel feature; tests passed; no operator rescue.

**What it proves.** Why-not and in-flight state survive a killed cloud session. Talmudic docs are not treated as proof of a durable DB effect — the system of record is still SQLite.

---

## Assay 4 — SessionStart is a map, not a dump

Feeding the whole Gemara at session start was tried and rejected. It does not scale (Assay 2). Gold SessionStart injects: *Talmudic Memory is active* — Gemara is indexed; **search** `orient` / `recall`; quote ids; do not run `digest`.

Cursor Agent (3.18.9+) injects that pointer as `hooks_context`. Claude Code injects the same pointer. Cursor **cloud** agents skip `sessionStart`; the project rule still says to search.

This is on marketplace **`main`** via [PR #16](https://github.com/gilav2/Talmudic-AI-memory/pull/16).

---

## What we do not claim

- No productivity percentage, time-saved figure, star count, or user count.
- Smoke `RESUME PASS` is not the same as the live ADR trap.
- `FETCH BOUNDED` is not “always fewer tokens than a dump.”
- Gemara is not a truth oracle. Provenance is not verification. A later agent must still check systems of record (as Session B did with `lab.db`).
- We are **beta 0.3.0b1**, not 1.0.
- Controlled Gemara-vs-no-Gemara quality trials (repeated traps, operator corrections) are the **next** evidence layer — not this assay.

---

## How marketing agents should speak

**Use**

- **The agent dies. The work is immortal.**
- Decision archaeology for coding agents.
- Shared **project intelligence**: why this, and **why not that**.
- New agent, new IDE, first prompt, no onboarding: refuse the stale path from Gemara.
- Dual harness: Cursor and Claude Code, one Gemara, neither owns it.
- Map, not dump. `FETCH BOUNDED`.
- Not chat Memory. Not a changelog. Not a vector store.

**Do not**

- Quote invented Chat B dialogue.
- Call smoke tokens a “live customer demo.”
- Say “loads all memory into context so the agent knows everything.”
- Imply 1.0 or universal productivity gains.

**The line to keep**

> The agent dies. The work is immortal. A new colleague on another IDE, asked on the first prompt whether to do the thing the repo still recommends, can say no — because the project remembered **why not**.
