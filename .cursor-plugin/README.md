# Cursor adapter

> **Same Gemara. Different host.**

The Cursor package is a thin host adapter over Talmudic's shared continuity runtime. Selecting Claude, another model, or a new agent in Cursor does not change who owns project memory: the **workstream** does.

For the product model and benchmark evidence, see [../README.md](../README.md). For normal usage, see [../USER_GUIDE.md](../USER_GUIDE.md).

## Install / update

Import the repository, track **`main`**, and enable **Talmudic AI Memory**.

```text
https://github.com/AI4AI-Labs/talmudic-ai-memory
```

Updates: Dashboard → Plugins → **Refresh** (or Auto Refresh). Cursor caches the plugin by commit SHA.

Python 3.10+ as `python`, `python3`, or Windows `py -3`.

## Required: enable Talmudic for this project

Installing the Cursor plugin does **not** activate Talmudic in every repository. Cursor currently loads an installed plugin beyond a single-project scope, so Talmudic deliberately makes its hooks no-op unless the current project explicitly enables them.

Create this file in each Cursor project where Talmudic should run:

```text
.cursor/talmudic.json
```

```json
{"enabled": true}
```

Then open a **new Agent session** and run `/talmudic-init`.

This marker is only a **Cursor scoping safeguard**. It is not Gemara and it is not the memory store. Talmudic creates and manages `.talmudic/` itself — **do not create that directory manually**.

Already-initialized projects with `.talmudic/` remain active for compatibility. An explicit `{"enabled": false}` wins over a leftover `.talmudic/` directory.

## Commands

`/talmudic-init`, `/talmudic-remember`, `/talmudic-recall`, `/talmudic-status`, and `/talmudic-doctor` operate on project Gemara. A host `/remember` command is not the same thing.

Cursor may copy the Talmudic command templates into the opened project's `.cursor/commands/` so they remain available from the slash menu.

## Event mapping

| Cursor event | Adapter | Behavior |
|---|---|---|
| `sessionStart` | `cursor_session_start.py` | Injects env + **index pointer**, not Gemara dump |
| `workspaceOpen` | `cursor_hook.py` | Installs project command/rule surfaces |
| `sessionEnd` | `cursor_hook.py` | Fire-and-forget boundary |
| `beforeShellExecution` | `cursor_guard.py` | Fail-closed material-write guard |
| `preToolUse` / `postToolUse` | `cursor_observer.py` | Observe continuity-relevant boundaries |
| `afterFileEdit` / `afterShellExecution` | `cursor_observer.py` | Observer input |
| `preCompact` | `cursor_hook.py` | Bounded Remember suggestion |
| `subagentStop` | `cursor_observer.py` | One-line follow-up suggestion |
| `stop` | `cursor_stop.py` | Bounded stop handling; loop limit 5 |

Cursor's manifest must use `hooks/hooks-cursor.json`. Claude Code's manifest must use `hooks/hooks-claude.json`. Do not ship root `hooks.json` or a default `hooks/hooks.json` — marketplace scanners treat those as Cursor bait.

## Cloud agents

Cursor cloud agents skip `sessionStart` / `sessionEnd`. They still run the available shell/tool/file/compact/stop hooks. The installed `.cursor/rules/talmudic-orient.mdc` tells the agent to search the index when the SessionStart pointer is absent.

**Do not compensate by dumping Gemara.** The tested scaling path is map → targeted fetch, not history → context.

## Why the Cursor smoke matters

The Cursor development line supplied the replacement-agent example used in the main README: Chat A records a distinctive decision, a fresh Chat B must recover it from Gemara, and the gold path is to quote the relevant record id rather than re-derive the answer from the repository or host Memory.

The same line added the 10/50/150-record stress harness that checks the SessionStart pointer remains small while targeted retrieval still finds the planted decision.
