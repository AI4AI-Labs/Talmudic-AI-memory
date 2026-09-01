# Claude Code adapter

> **Same Gemara. Different host.**

The Claude Code package is a thin host adapter over Talmudic's shared continuity runtime. Project judgment belongs to the workstream, not to Claude Code.

For the product model and benchmark evidence, see [../README.md](../README.md). For normal usage, see [../USER_GUIDE.md](../USER_GUIDE.md).

## Install

```bash
claude plugin marketplace add AI4AI-Labs/talmudic-ai-memory
claude plugin install talmudic-memory@talmudic-ai-memory --scope project
```

Start/restart a Claude Code session after installation. Python 3.10+ must be available as `python` / `python3` / Windows `py -3`.

Beta installs track this repo's **`main`**. Claude Code caches plugins by version string; after a version bump run `claude plugin marketplace update`, then `/plugin update`.

## Commands

| Command | Purpose |
|---|---|
| `/talmudic-init` | Map the project/workstream |
| `/talmudic-remember` | Persist continuity-critical state, operations, why and why-not |
| `/talmudic-recall` | Search shared Gemara |
| `/talmudic-status` | Current workstream state |
| `/talmudic-doctor` | Diagnose/repair disposable local machinery only |

These are project-intelligence commands. Claude's own `/remember` / Memory is a different surface.

## Hook mapping

| Claude event | Script | Behavior |
|---|---|---|
| `SessionStart` | `talmudic_hook.py` | Bootstrap + **index pointer**, not Gemara dump |
| `SessionEnd` / `PreCompact` | `talmudic_hook.py` | Bounded Remember suggestion |
| `PreToolUse Bash` | `talmudic_guard.py` + observer | Fail-closed material-write guard |
| `PostToolUse` | `talmudic_observer.py` | Observe continuity-relevant boundaries |
| `Stop` | `talmudic_stop.py` | Bounded one-line Remember discipline |

The nudge is intentionally small: `Talmudic: Remember this if a future agent would miss it.`

A successful canonical write resets the observer baseline. Talmudic should not turn documentation into a second agent conversation.

## Host boundary

Selecting Claude as a model **inside Cursor** does not load this package. Cursor's host hooks run there. Both hosts still read/write the same Gemara through the shared runtime.
