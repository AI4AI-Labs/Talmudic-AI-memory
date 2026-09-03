# Privacy Policy

_Last updated: 2026-09-03_

Talmudic AI Memory is local-first project-memory software.

## What Talmudic AI Memory stores

Depending on how you use it, Talmudic may store:

- project decisions and rationale;
- rejected alternatives and reopen conditions;
- workstream state, checkpoints, and unresolved operations;
- provenance such as agent, model, role, and session identifiers;
- local runtime configuration;
- a disposable local SQLite retrieval index.

Local runtime and cache data are stored under the project's `.talmudic/` directory.

In shared Git mode, canonical Gemara records are synchronized through the Git remote configured for that project.

## What AI4AI Labs collects

The current open-source plugin does **not** operate a Talmudic-hosted cloud service, analytics service, or telemetry pipeline.

The current runtime does not intentionally transmit project memory, source code, prompts, or usage analytics to AI4AI Labs.

## Third-party services

Talmudic runs inside third-party developer environments such as Claude Code and Cursor and may use a Git hosting provider selected by the user.

Those services may process data under their own terms and privacy policies. Talmudic AI Memory does not control their collection or retention practices.

## Network activity

The core runtime has no dependency on a Talmudic-hosted API.

When shared Git synchronization is enabled, Git operations may communicate with the configured Git provider using the user's existing Git credentials and permissions.

## Data control and deletion

Users control the repositories and local files in which Talmudic data is stored.

Deleting local `.talmudic/` state removes local runtime/cache data. Deleting canonical shared Gemara history requires deleting the corresponding records or Git-backed canonical storage under the user's control.

## Future hosted services

If AI4AI Labs introduces hosted synchronization, enterprise indexing, telemetry, accounts, or other cloud services, this policy will be updated before those services process user data.

## Contact

For privacy questions, contact the maintainers through the GitHub repository.
