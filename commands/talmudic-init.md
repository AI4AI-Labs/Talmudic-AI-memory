---
name: talmudic-init
description: Initialize Talmudic for an existing project/workstream. Survey pointers first, then question the operator before seeding Sugyot. Not Claude Memory / MEMORY.md.
argument-hint: "[optional workstream id]"
---

# /talmudic-init

The operator invoked **Talmudic Init** — initialize this running project/workstream for Gemara. This is not Claude Memory / MEMORY.md.

This command uses `talmudic init` to establish the workstream and project map.

The old operator name `/talmudic-origin` was retired: it sounded like git remotes and did not name the purpose (initialize). If you see Origin in old Gemara, chats, or PRs, use `/talmudic-init`. Do not teach or repeat Origin as the slash command. `origin.json` is the internal pointer-map file. Git remotes named `origin` are unrelated.

Operator argument (optional workstream id):

$ARGUMENTS

## Cursor activation notice

Before initialization, determine whether this command is running in Cursor.

If it is Cursor, check `.cursor/talmudic.json` before continuing:

- If it contains `{"enabled": true}`, continue with Init.
- If it is missing, explain that Cursor currently cannot scope the installed plugin to individual projects, so Talmudic uses this project-level activation marker. Ask the operator for permission to create `.cursor/talmudic.json` with `{"enabled": true}`.
- If it explicitly contains `{"enabled": false}`, tell the operator Talmudic is disabled for this project and ask permission to change it to `{"enabled": true}`.

Never create or modify the activation marker without explicit operator approval.

If the operator approves, create or update the marker, tell the operator to start a **new Cursor Agent session** so the project hooks activate, then stop Init. The operator should rerun `/talmudic-init` in the new session.

If the operator declines, stop Init without changing the project.

Do **not** ask the operator to create `.talmudic/` manually. Talmudic creates and manages that runtime directory itself.

This activation check is Cursor-specific. Do not require `.cursor/talmudic.json` when running under Claude Code or another host.

## Runtime

Use `.talmudic/runtime.json` → `command` (`.\.talmudic\talmudic.cmd` on Windows PowerShell, `.talmudic/talmudic` on Unix). Do **not** run `python -m talmudic_memory.cli` or a global `talmudic` — they can be an older pip install.

When `GIT_SHARED`, `sync` immediately before any canonical write.

## A — survey (mechanical, always)

This command creates a workstream. **Survey runs automatically as part of `init`.** Do not treat survey as a separate operator step. `talmudic survey` is a read-only debug map of the same pointers. The CLI must **not** parse changelog into Sugyot.

```text
<runtime> sync
<runtime> status <workstream>   # if Resume already exists: show origin pointers and epoch; do not rewrite origin.json; skip to B only if Gemara still has no seed Sugyot
<runtime> init <workstream-id> --task "Map existing project" --next "Ask the operator before seeding Sugyot"
```

Workstream id: `$ARGUMENTS` if it looks like an id, else a namespaced id such as `<project>/init`.

`init` writes `origin.json`: pointer paths, kinds, first headings, git head/branch/sanitized remote, manifest name, `surveyed_at`. **Do not dump document bodies into Gemara.** Epoch is this init moment: Gemara remembers from `surveyed_at` at `git.head`.

Show the operator the pointer list (paths + headings) and the epoch. Then go to B. Do not invent git history.

## B — question the operator, then maybe seed Sugyot

The operator is the mastermind. Mechanical survey cannot recover the aim. **Ask. Do not skip these questions:**

1. What is the **aim** of this project / this workstream?
2. Is the **current** changelog section plus current designs an accurate picture of **now**? What is wrong or missing?
3. What must a future agent **not** redo?
4. Which of those items should become Sugyot, and which should stay as pointers?

If the operator is silent or does not answer, **stop after A**. Do not invent aim or current status. Digest still shows pointers and the remembering-from line.

### Current slice (what to read)

Read **only**:

- Project-map pointers of kind `changelog`: the **latest** version section only (first version heading until the next, or the top of the file if unversioned). Older changelog versions stay pointers (pre-memory).
- Current designs: `prd`, `thesis`, `architecture`, `product`, plus README heading.

Do not copy those bodies into Sugya text. Use them to ask better questions, then cite **paths** as `--evidence`.

### What to write (only after the operator is willing to seed)

Write through `talmudic sugya` only. Evidence refs are paths. Cap **six** seed Sugyot unless the operator explicitly asks for more. Prefer fewer. Same subject may get more Sugyot later via `--supersedes`.

| Order | When |
|---|---|
| Remembering from this point | Always, once the operator is willing to seed |
| Aim | Only if the operator stated it |
| Current status | After the operator confirms or corrects the current slice |
| Extra | Only for decisions the operator says a future agent would miss |

Optional: one breadcrumb that project initialization was seeded. Do not dump changelog into breadcrumbs.

If `origin.json` already exists, do not rewrite it. If seed Sugyot already exist, do not re-seed; use `/talmudic-status` / `/talmudic-recall`.
