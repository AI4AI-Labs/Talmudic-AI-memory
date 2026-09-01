# Production promotion — PROD pulls QA

## Trust model

```text
DEV:  feature branches in gilav2/Talmudic-AI-memory
QA:   gilav2/Talmudic-AI-memory:main
PROD: AI4AI-Labs/talmudic-ai-memory:main
```

**PROD pulls from QA. QA never writes to PROD.**

- QA is qualification truth.
- PROD is release truth **and owns the promotion policy**. A QA commit must never be allowed to replace the builder/allowlist that decides what enters PROD.
- Promotion copies an **allowlisted** tree from one **exact QA main SHA** plus one **exact version**.
- Promotion opens a **PROD PR only**. It never merges, never force-pushes `main`, never auto-merges.

## Direction of trust

```text
DEV branch
  ↓ PR + CI
QA main  (gilav2/Talmudic-AI-memory)
  ↓ human records exact SHA + version
PROD workflow  (AI4AI-Labs/talmudic-ai-memory)
  ↓ checkout that SHA with contents:read
  ↓ allowlisted export + public URL rewrite
PROD promotion PR
  ↓ independent PROD CI + human review
PROD main
```

Do **not** run a QA workflow that mints a token and pushes a PROD branch. That inverts the trust boundary.

## Security invariants

1. Exact-SHA only. The operator types the approved QA `main` SHA; the workflow refuses any other commit.
2. That SHA must be an ancestor of QA `origin/main`.
3. Allowlist, never denylist. Only paths in the **PROD-owned** `release/production-files.txt` plus the documented PROD overlay enter the tree. QA supplies product files, not promotion policy.
4. No Gemara/runtime leakage. `.talmudic/`, workstreams, caches, keys, `.env`, sqlite/db, and private-key formats are rejected.
5. Public install surfaces on PROD point at `AI4AI-Labs/talmudic-ai-memory`. QA is named only in provenance and this document.
6. Version lock. `pyproject.toml`, `plugin.json`, `.claude-plugin/plugin.json`, and `.cursor-plugin/plugin.json` must equal the requested version.
7. SHA-256 provenance in `RELEASE_PROVENANCE.json`.
8. Least privilege. PROD reads QA with `contents:read`. No personal PAT if a GitHub App or fine-grained token can do the job.
9. Human merge gate. The workflow never merges the PR.
10. No force-push of `main`. Promotion branches are pushed without `--force`.
11. Independent PROD CI. QA green is necessary, not sufficient.
12. Keep PROD **private** until a human explicitly approves making it public.

## What is promoted (allowlist)

Runtime plugin + CLI only:

- `.claude-plugin`, `.cursor-plugin`, `plugin.json`
- `src`, `talmudic`, `talmudic.cmd`, listed `scripts/cursor_*` and `scripts/talmudic_*`
- `agents`, `commands`, `hooks`, `hooks.json`, `host`, `skills`
- `README.md`, `USER_GUIDE.md`, `LICENSE`, `pyproject.toml`
- `.github/workflows/ci.yml`

Overlay that is not a marketplace runtime file:

- `docs/PRODUCTION_PROMOTION.md`
- `.github/workflows/promote-from-qa.yml` (PROD-owned; authored under `release/prod-owned/` on QA)

## What never belongs in PROD

- `.talmudic/` or this plugin repo's own Gemara
- `tests/`, `examples/`, bench dashboards, experiment branches
- local caches / SQLite indexes
- credentials, `.env`, keys
- transcripts or private context
- a workflow on **QA** that pushes to PROD

## PROD repository settings

For `AI4AI-Labs/talmudic-ai-memory`:

- default branch `main`
- private until explicit public approval
- require pull request before merge
- at least one human approval
- require production CI
- dismiss stale reviews; require conversation resolution
- block force-push and deletion of `main`
- Actions default: read for `GITHUB_TOKEN` except this promotion workflow's documented write
- do not let the promotion identity bypass branch protection

## Secrets

Store on **PROD**, in a protected `production` Environment with a required reviewer:

| Secret | Purpose | Privilege |
|---|---|---|
| `QA_READ_TOKEN` | Checkout `gilav2/Talmudic-AI-memory` at the exact SHA | `contents:read` on that repo only |

Preferred: a GitHub App installed on the QA repo with **Contents: Read**, minting a token in the PROD workflow. A fine-grained PAT scoped to that one private repo is acceptable if an App is not ready. Do not use a classic user PAT with org-wide or unrelated scope.

PROD's own `GITHUB_TOKEN` needs `contents:write` and `pull-requests:write` **on this repository** so it can push a promotion branch and open a PR. It must not have write access to QA.

## Promotion procedure

1. Merge the product change to QA `main` through PR. Wait for QA CI.
2. Record the exact SHA and the exact version (`0.3.0b1`, not a moving tag).
3. On **PROD**: Actions → **promote-from-qa** → Run workflow.
4. Enter `expected_sha` and `version`.
5. Approve the PROD `production` Environment if prompted.
6. Review the PROD PR: `RELEASE_PROVENANCE.json`, allowlisted diff, rewritten install URLs, production CI.
7. Merge manually only when that review passes.
8. Smoke Claude Code + Cursor from the **PROD** URL after merge.
9. Stay private until a human explicitly approves publication.

## Bootstrap (first populate)

If PROD only has GitHub's README commit:

1. Build the allowlisted tree from the approved QA SHA using `scripts/build_production_tree.py`.
2. Overlay `release/prod-owned/` plus the initial builder/allowlist so `promote-from-qa.yml` and the PROD-owned promotion policy exist on PROD.
3. Push branch `promote/v<version>-<shortsha>` and open a PR against PROD `main`.
4. Do not merge from automation. Do not force-push `main`.

This Cloud Agent cannot clone or write `AI4AI-Labs/talmudic-ai-memory` until the Cursor GitHub App (or an equivalent collaborator) is installed on **AI4AI-Labs** with access to that private repository.

## Rollback

Do not rewrite PROD history. Revert through a PR, or promote the last known-good QA SHA as a new promotion. Fix in DEV/QA, then pull again.

## Trust-boundary note

The long-running PROD workflow must execute the builder and allowlist already present on PROD `main`. It may read product files from the approved QA SHA, but it must **not execute promotion code from QA**. Otherwise a compromised or mistaken QA release candidate could redefine the export policy while the workflow holds PROD write permission.
