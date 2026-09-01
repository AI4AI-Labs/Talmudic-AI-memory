---
name: talmudic-recall
description: Search the Talmudic Gemara for prior project why and why-not. Not Claude Memory.
argument-hint: "[question about prior project work]"
---

# /talmudic-recall

The operator invoked **Talmudic project recall**, not Claude Memory.

Do **not** use Claude Memory, MEMORY.md, or conversation search as a substitute. Answer from the Gemara via the `talmudic` CLI — including why something was done and why it was not.

Operator question (may be empty — if so, ask what to recall):

$ARGUMENTS

## Runtime

Use `.talmudic/runtime.json` → `command` (`.\.talmudic\talmudic.cmd` on Windows PowerShell, `.talmudic/talmudic` on Unix). Do **not** run `python -m talmudic_memory.cli` or a global `talmudic` — they can be an older pip install.

## Sequence

```text
<runtime> sync
<runtime> recall "<question>" [--workstream <id>]
```

Skip a duplicate sync only if SessionStart just synchronized and nothing canonical could have changed. Quote the retrieved records; do not invent a Sugya. A question does not write Gemara.
