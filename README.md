# Agora

Automated, rule-driven debates between Codex and Claude Code, using locally
installed official CLIs and your own subscription login.

**Status: early prototype.** Agora checks declared arithmetic and matches quotations
against supplied source snapshots. Models assess whether those quotations support
the claims. Neither a quote match nor agreement between models is proof.

## How it works

1. Give Agora a question, optional discussion rules, and optional source URLs.
2. Codex and Claude independently produce initial answers.
3. Each participant reviews the other participant's previous answer and revises
   its position. Both see the previous round and its evidence checks, not the
   other's new response.
4. After one to three rounds, the selected provider writes a final summary (Codex by default).
5. Agora saves a Markdown report and a JSON transcript after each completed turn.

Fixed review makes five calls for one round, seven for two, and nine for three.
The local interface defaults to automatic review: up to three rounds and eleven
calls, including a synthesis after each round, with early stopping when appropriate.
Each call starts a new session with explicit context. Answers follow the language
of the question unless your rules specify otherwise.

## Requirements

- Python 3.11 or later; no third-party Python dependencies.
- Official Codex CLI signed in with a ChatGPT subscription.
- Official Claude Code signed in with a personal Pro or Max subscription.
- An internet connection and remaining subscription allowance.

The live integration was tested on Windows with Codex CLI `0.162.0-alpha.2` and
Claude Code `2.1.295`. Other versions and platforms have not been integration-tested.
Unit tests do not require either CLI.

## Quick start

Install [Codex CLI](https://developers.openai.com/codex/cli) and
[Claude Code](https://code.claude.com/docs/en/setup), then:

```sh
git clone https://github.com/softyware21/Agora.git
cd Agora
codex login
claude auth login
python agora.py --check
python agora.py --question "What assumptions would invalidate this proposal?"
```

Use subscription login rather than a Console/API account. `--check` inspects the
saved authentication type; a session-refresh failure may only appear on a real call.
On Windows, you can also double-click `start.cmd` and enter a question.
Use `login-claude.cmd` to renew an expired login. Complete authentication through
the official browser/terminal flow; never paste credentials into an issue.

If needed, set `AGORA_CODEX_PATH` or `AGORA_CLAUDE_PATH` to the official executable.
On Windows, point to an `.exe`, not a shell wrapper.

## Local interface

```sh
python web_app.py
```

On Windows, double-click `start-ui.cmd`. The page opens at `http://127.0.0.1:8765`.
Enter a question and select **Think it through**. Optional settings and an offline
call preview are under **Customize this discussion**. Results lead with the
conclusion; expand the issues or open the discussion history for more detail.
The page shows saved answers, issue outcomes, and controls to stop, resume, or
continue a completed discussion. Closing the browser leaves the runner active.

Keep the local server running while a discussion is in progress. Stop waits for
the current answer before preventing the next call. See [using the local interface](docs/INTERFACE.md)
for setup, recovery, and limitations.

## Model selection

Select participant models and a summary provider before running:

```sh
python agora.py --codex-model gpt-6.1-sol --claude-model opus --summary-provider claude --plan
python agora.py --question "Review this plan" --codex-model gpt-6.1-sol --claude-model opus --summary-provider claude
```

`--summary-model` chooses a separate model for the summary. Without it, the summary
uses the selected participant model for that provider. Omit participant model
options to use the CLI defaults. Model availability depends on your account;
examples are not a list of guaranteed models. See [model settings](docs/MODELS.md).

`--plan` prints the requested models and remaining calls without contacting either
provider, retrieving sources, or creating a run. It also works with `--resume`.

## Rules and limits

```sh
python agora.py --question "Review this plan" --rules "Separate evidence from assumptions." --rounds 2
```

Defaults: one review round, 180 seconds per generation, 600-second overall generation
deadline. Set `--timeout` and `--deadline` to change them. Authentication checks and
cleanup can add overhead. Source retrieval also happens before the generation deadline.
Press Ctrl+C to stop. No automatic retries or API fallback.

To continue a stopped run:

```sh
python agora.py --resume runs/<run-id>
```

Completed turns are reused. If the second reviewer failed, it still receives the
previous round's answers, not the first reviewer's new answer. The question, rules,
round count, and requested models stay fixed; `--timeout` and `--deadline` apply to the new attempt.
A completed run returns immediately without calling either model.

Resume rejects damaged transcripts, changed settings, and a different prompt
version before making a model call. Transcripts from the initial prototype do not
have a schema version and cannot be resumed. Keep them for reference and start a
new run. Only one process can write to a run at a time; its lock is released when
the process exits.

Each attempt records CLI versions, timing, and a stop reason. Per-turn model names
are saved when the CLI reports them; an empty list means the model was not reported.
CLI versions can change between attempts, so a resumed run is not guaranteed to
use the same model build. No account identifiers are stored in this metadata.

Results are saved to `runs/<run-id>/report.md` and `transcript.json`. Failed runs
retain completed turns and are marked `stopped`. Histories are local, plaintext
files excluded from Git.

## Issue outcomes and continuation

Completed discussions can continue in a new run directory:

```sh
python continue_debate.py --from runs/<run-id> --add-rounds 1 --plan
python continue_debate.py --from runs/<run-id> --add-rounds 1 --note "Reconsider the unresolved issue with this additional information."
```

One extra round uses three calls. The original transcript is preserved. Reports
show agreed, disputed, and insufficient-information issues with the latest cited
positions and proposed next steps. These statuses are model judgments, not truth
verification. See [continuation, new sources, and changed rules](docs/CONTINUING.md).

## Calculation checks

Participants append an expression and expected result for each calculation. Agora
evaluates these locally using exact fractions, then passes the results to the next
review. The report keeps matches, mismatches, and unverified entries by turn.

For example, `3000 * 16.7 / 100` evaluates to `501`, so an expected result of `500`
is flagged. A matching result does not establish that 3,000 was the right input or
that the surrounding claim is true. Calculations not declared by the model are not
checked. See [the format and limits](docs/CALCULATIONS.md).

## Source checks

Pass a public document with `--source`; repeat the option for up to five URLs:

```sh
python agora.py --question "Which domains does this RFC reserve for examples?" --source https://www.rfc-editor.org/rfc/rfc2606.txt
```

Agora downloads each document once and gives both models the same text. It checks
whether declared quotations appear in that snapshot. Reviewers then assess whether
the quoted passages support or contradict the linked claims. The report labels
those assessments as model judgments, separately from quote matches.

Only public HTTPS HTML and plain text documents are supported. URLs cannot include
credentials, query strings, or nonstandard ports. Pages requiring login, JavaScript,
or PDF extraction are not supported. There is no automatic web search.

Snapshots are saved locally with retrieval dates and text hashes. Resume reuses them
without downloading again; start a new run to change sources or use the current
prompt version. See [source formats, limits, and privacy](docs/SOURCES.md).

## Compare answers

Summaries also cite earlier turns. Agora checks declared quotations and whether
the cited speaker could see the answer they supposedly responded to. It does not
verify that the quotation actually expresses agreement. See [summary attribution checks](docs/ATTRIBUTIONS.md).

Run a fixed evaluation case to compare each model's independent first answer with
the final debate summary:

```sh
python evaluate.py --case discount-premise
```

Run without arguments to list the six cases, or use `--all` to run all six. At one
review round, that uses five calls per case or 30 for the full set. The grader checks
declared answer fields against fixed keys and reports both improvements and
regressions. Explanations still need human review; this is not a general accuracy
score or an equal-budget comparison. See [evaluation and resume instructions](docs/EVALUATION.md).

To compare the mixed debate with five-call Codex-only and Claude-only runs:

```sh
python budget_compare.py --case conditional-projects
```

This uses 15 calls total. Four additional challenge cases are available; `--all`
runs them with 60 calls. Call counts are matched, but tokens and compute are not.
See [the comparison design and limitations](docs/BUDGET_COMPARISON.md).

Use `--suite documents` to evaluate decisions from conflicting fictional documents:

```sh
python budget_compare.py --suite documents --case dated-exception
```

The three cases cover effective dates and exceptions, unresolved instructions, and
incompatible metrics. See [document evaluation](docs/DOCUMENT_EVALUATION.md).

## Subscription usage and security

Agora consumes your subscription allowance. It does not provide unlimited usage
and cannot disable provider-side paid extra usage. Turn off extra-usage options in
your provider accounts if you need to avoid additional charges.

Before generation, Agora checks subscription authentication and removes API-key
and provider overrides from the child environment. It does not read, copy, or
publish CLI credential files. Codex uses a read-only sandbox with shell disabled
and user configuration ignored. Claude Code uses safe/restricted modes with tools
disabled. Provider-managed policies still apply.

These controls are not a billing audit or a guarantee against future CLI changes.
Review the providers' terms before deploying for others. Agora is independent and
is not affiliated with or endorsed by OpenAI or Anthropic.

## Limitations

- No web interface, automatic source discovery, or remaining-allowance dashboard.
- Quote matches do not establish source reliability or whether a claim is true.
- Arithmetic checks cover explicit declarations, not every number in the answer.
- Codex writes the summary, which can introduce summarization bias.
- CLI models and features may differ from the providers' web applications.

On October 9, 2026, a live five-call subscription-authenticated cycle completed on
a synthetic cost question. It demonstrated peer review and corrections, not a
general accuracy improvement. Billing statements were not audited. The live check
preceded the repository's English-language cleanup; prompts have since been translated.

## Development

```sh
python -m unittest discover -s tests -v
```

Tests use fake providers without consuming model usage. See
[CONTRIBUTING.md](CONTRIBUTING.md) for repository conventions and
[the roadmap](docs/ROADMAP.md) for planned work.

## License

A license has not been selected. Public visibility alone does not grant an
open-source license. License selection is a prerequisite for an open-source release.

## References

- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Claude Code programmatic execution](https://code.claude.com/docs/en/headless)
- [Claude Code legal and compliance guidance](https://code.claude.com/docs/en/legal-and-compliance)
