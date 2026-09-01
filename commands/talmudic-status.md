---
name: talmudic-status
description: Show the active workstream Resume — current task, next action, blockers, in-flight. Not Claude Memory / MEMORY.md.
argument-hint: "[optional workstream id]"
---

# /talmudic-status

The operator invoked **Talmudic Status**. This is project Resume, not Claude Memory / MEMORY.md.

Do **not** use Claude Memory or reconstruct status only from the working tree when Resume exists.

Operator argument (optional workstream id):

$ARGUMENTS

## Runtime

## Runtime

Use `.talmudic/runtime.json` → `command` (`.\.talmudic\talmudic.cmd` on Windows PowerShell, `.talmudic/talmudic` on Unix). Do **not** run `python -m talmudic_memory.cli` or a global `talmudic` — they can be an older pip install.

## Sequence

```text
<runtime> sync
<runtime> status <workstream>
```

If `$ARGUMENTS` is a workstream id, use it. Otherwise use the active workstream from `.talmudic/cache/active_workstream.json` or ask. Present: task, lifecycle, checkpoint, blockers, open In-Flight, last verified, next exact action, current actor. Do not write Gemara.
