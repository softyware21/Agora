# Comparing equal call counts

`budget_compare.py` runs the same case under three provider assignments:

| Arm | Independent answers | Reviews | Summary |
| --- | --- | --- | --- |
| mixed | One Codex, one Claude | One each | Codex |
| codex-only | Two Codex answers | Two Codex reviews | Codex |
| claude-only | Two Claude answers | Two Claude reviews | Claude |

Every arm uses five calls per case. Each call starts a fresh CLI session with
explicit context. Single-model arms use the same debate structure: two independent
answers, mutual review of those answers, and synthesis. They are not a single long
answer or repeated calls with no feedback. Arithmetic checks are available to every
arm through the same runner. Arms do not receive one another's responses or scores.

Only call counts are matched. Token counts, latency, internal reasoning effort,
compute, and provider-specific subscription consumption can differ. The mixed
arm always uses Codex to summarize, while Claude-only uses Claude. This does not
isolate the effect of provider diversity from the effect of the summarizer.

## Commands

```sh
python budget_compare.py
python budget_compare.py --case conditional-projects
python budget_compare.py --all
python budget_compare.py --suite basic --all
```

Without a selection, the command lists the challenge cases without model calls.
One case uses 15 calls across three arms. The four-case challenge set uses 60;
the six-case basic set uses 90. `--case` can be repeated. All calls use the existing
subscription authentication checks and consume allowance. No automatic retries
or API fallback are added.

The challenge cases cover different case mixes, perfectly dependent observations,
project dependencies with a cost tie-break, and inconsistent mandatory constraints.
They are intended to be harder than the basic cases; measured difficulty is not
yet established. Answer keys are fixed before live generation and withheld from
model prompts. Tests derive the numeric keys using exact fractions and enumerate
all project subsets. The cases are public and are not a held-out benchmark.

Results are stored locally under `runs/budget-<time>-<id>/`. The root
`comparison.md` compares final answers across arms; `scores.json` contains field
scores. Each arm also has its own evaluation directory and complete transcripts.
Generated answers stay excluded from Git.

## Resume and reporting

```sh
python budget_compare.py --resume runs/budget-<time>-<id>
python budget_compare.py --report runs/budget-<time>-<id>
```

Always resume at the parent comparison directory through `budget_compare.py`.
Do not run `evaluate.py --resume` on an arm directory: that command uses ordinary
mixed-model routing. The comparison runner rejects saved responses whose recorded
routing does not match the arm. Transcripts retain legacy `provider` role labels;
`metadata.actual_provider` identifies the provider used for each response.

New comparisons use routing prompt version 2. Structured prompt history uses
`participant_A` and `participant_B`, with explicit actual-provider assignments.
Case report headings also show the participant and actual provider. Generated
prose is preserved verbatim, so these instructions cannot guarantee correct
attribution in every sentence.

Version 1 comparisons remain readable and completed batches need no new calls.
An unfinished version 1 comparison cannot resume with version 2 prompts; start a
new batch to avoid mixing experimental conditions. Old responses are not rewritten.

The [document suite](DOCUMENT_EVALUATION.md) adds three cases based on fixed,
conflicting fictional excerpts. Use `--suite documents` to select it.

Completed turns and arms are reused. A failure stops the experiment; the report
keeps available answers and pending results visible. Only cases completed in all
three arms enter paired totals. Missing or invalid answer blocks are non-passes,
not silently excluded. `--report` needs no model calls or provider installation.

`--timeout` and `--deadline` apply per generation and per case attempt respectively,
as in the ordinary evaluation runner. The execution order is fixed: mixed, then
Codex-only, then Claude-only. Time-dependent model changes and order effects are
not controlled. Resume can cross version changes reported by the provider CLIs.

## Reading the results

Scores check the requested answer fields, not all prose. Read the responses for
invalid reasoning, invented assumptions, missed qualifications, and errors added
during review. A correct final field does not erase earlier errors.

One case or one run cannot establish an accuracy advantage. Keep all outcomes,
including ties and regressions. Broader cases, counterbalanced order, repeated
runs, and blinded human review remain needed before making general claims.
