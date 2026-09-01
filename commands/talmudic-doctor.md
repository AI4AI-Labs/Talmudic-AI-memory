---
name: talmudic-doctor
description: Diagnose Talmudic continuity machinery and repair only the local index/cache. Never rewrite Gemara.
argument-hint: "[optional symptom]"
---

# /talmudic-doctor

The operator invoked **Talmudic Doctor**. This is a health check of project-continuity machinery, not Claude Memory / MEMORY.md.

Do **not** use Claude Memory. Do **not** rewrite canonical Gemara. Doctor may rebuild only disposable local cache/index.

Operator note (optional):

$ARGUMENTS

## Runtime

## Runtime

Use `.talmudic/runtime.json` → `command` (`.\.talmudic\talmudic.cmd` on Windows PowerShell, `.talmudic/talmudic` on Unix). Do **not** run `python -m talmudic_memory.cli` or a global `talmudic` — they can be an older pip install.

## Sequence

```text
<runtime> doctor
```

Report runtime, shared branch/mirror, canonical store, actor, index freshness, and open In-Flight/recovery. If the index is stale or broken, rebuild the index only. Never hand-edit files on the `talmudic-memory` branch to "fix" Doctor.
