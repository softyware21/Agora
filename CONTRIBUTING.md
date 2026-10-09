# Contributing

Agora is an early prototype. Open an issue describing the problem and proposed
scope before starting a substantial change.

## Language

Use English for tracked documentation, code comments, interface strings, commit
messages, issues, pull requests, and release notes. User questions and model
answers may use any language and should not be committed by default.

## Commit history

- Keep each commit focused on one meaningful change.
- Use an imperative subject, optionally prefixed with `feat:`, `fix:`, `docs:`,
  `test:`, or `chore:`. Example: `fix: preserve completed turns after a timeout`.
- Explain the reason and relevant validation when the subject is not enough.
- Do not fabricate earlier development history or backdate commits.
- Preserve public history; avoid rewriting commits others may already use.

The initial commit imports the existing prototype. Subsequent commits should
record real changes as they happen, not a fictional sequence of the initial work.

## Validation and privacy

Run `python -m unittest discover -s tests -v` before submitting behavior changes.
Use fake providers for tests. Live checks consume subscription allowance; describe
them explicitly and do not run them in CI.

Never commit authentication files, tokens, local transcripts, account identifiers,
provider binaries, private configuration, or machine-specific absolute paths.
Use synthetic examples and inspect the staged diff before committing.

## Pull requests

Describe the problem and resulting behavior, relevant validation, and remaining
limitations. Link an associated issue when available.

License selection is pending. Do not submit third-party code unless its provenance
and intended licensing can be reviewed.
