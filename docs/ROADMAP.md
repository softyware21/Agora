# Roadmap

## Completed: local proof of concept

- Independent answers from Codex and Claude Code.
- Configurable rules and bounded review rounds.
- Subscription authentication checks without API fallback.
- Reports, transcripts, and partial-run preservation.
- Unit tests and a successful live five-call debate.
- Resume from the first missing turn, with transcript checks and one-writer locking.
- Per-attempt CLI versions, reported model names, and stop reasons.

## Next: reproducibility

- Select an open-source license before accepting external contributions.
- Test compatibility with supported CLI versions.
- Separate provider adapters from orchestration.
- Improve cancellation, deadlines, and cross-platform support.

## Evidence and evaluation

- Track claims, assumptions, objections, and sources.
- Add deterministic calculations and source retrieval.
- Keep agreement separate from evidence status.
- Compare against individual models using fixed evaluation cases.
- Include false premises and questions that cannot be resolved.

## User experience

- Local interface for questions, rules, progress, and results.
- Reusable debate configurations.
- Clear presentation of uncertainty and unresolved disagreements.

## Later

- Optional explicit API mode with separate billing controls.
- Additional providers and configurable summarization roles.
- Authentication, privacy, and provider-terms review before hosted deployment.
