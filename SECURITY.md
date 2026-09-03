# Security Policy

## Supported version

Security fixes are applied to the current public beta and newer releases.

| Version | Supported |
| --- | --- |
| 0.3.x | Yes |
| < 0.3 | No |

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a suspected vulnerability.

Use GitHub's private vulnerability reporting / Security Advisory flow for this repository when available. Include:

- affected version and host (Claude Code, Cursor, or direct CLI);
- operating system and Python version;
- reproduction steps;
- expected vs. observed behavior;
- whether project memory, Git credentials, repository contents, or material-write guards may be affected;
- any proof-of-concept needed to reproduce the issue.

If private vulnerability reporting is unavailable, contact the repository maintainers through GitHub without publishing exploit details.

## Security model

Talmudic AI Memory runs local hooks and Python code in the user's development environment. It may read and write project-local Talmudic state and, in shared mode, use the configured Git remote for canonical Gemara synchronization.

The project does not treat the local SQLite index as canonical history.

Material-write guards reduce accidental durable writes; they are not a sandbox, endpoint-security product, or replacement for repository permissions.

## Disclosure

We ask reporters to allow a reasonable remediation window before public disclosure. We will acknowledge valid reports, investigate impact, and publish fixes/advisories when appropriate.
