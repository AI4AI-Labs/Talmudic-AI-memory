# Contributing

Thanks for helping improve Talmudic AI Memory.

## Ground rules

- Keep Gemara semantics separate from host-specific behavior.
- Do not treat transcripts, caches, or indexes as canonical project history.
- Preserve provenance and supersession semantics.
- Avoid silently broadening what the plugin reads, stores, transmits, or writes.
- Do not add telemetry or hosted dependencies without explicit design review and privacy documentation.

## Development flow

This repository is the production/public tree.

Day-to-day development and qualification happen upstream, and production changes should arrive through reviewed pull requests.

For changes made directly against this repository:

1. Create a branch.
2. Keep the change narrowly scoped.
3. Run the relevant tests and plugin smoke checks.
4. Open a pull request against `main`.
5. Do not force-push or bypass review on `main`.

## Tests

At minimum for runtime changes:

```bash
python -m pip install -e . --no-build-isolation
python -m compileall -q src
talmudic --help
```

Claude- and Cursor-specific changes should also be tested through their respective plugin install paths.

## Security

Do not disclose vulnerabilities in public issues. See [SECURITY.md](SECURITY.md).

## Pull requests

A good pull request explains:

- what changed;
- why it changed;
- what behavior is intentionally unchanged;
- tests performed;
- security/privacy implications, if any.

## License

By contributing, you agree that your contributions are licensed under the repository's MIT License.
