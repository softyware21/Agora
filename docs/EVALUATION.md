# Comparing answers

The evaluation runner compares Codex's independent first answer, Claude's
independent first answer, and the final debate summary on the same fixed question.
The first answers are reused as the baselines; they are not extra model calls.
They use Agora's initial-answer instructions, including the debate framing and
evidence declarations. They are not samples from the providers' web chat products.

## Run a comparison

List the cases without calling either model:

```sh
python evaluate.py
```

Run one case, a selection, or the full set:

```sh
python evaluate.py --case discount-premise
python evaluate.py --case converse-error --case missing-denominator
python evaluate.py --all
```

There are six cases. At the default one review round, each case uses five model
calls and the full set uses 30. `--rounds 2` uses seven calls per case; `--rounds 3`
uses nine. The runner prints the remaining call count before generation and stops
on the first failed case. It never retries automatically or falls back to an API.

`--timeout` sets the per-generation timeout (default 180 seconds). `--deadline`
sets the generation deadline for each case attempt (default 600 seconds), not the
whole batch. Authentication and cleanup add overhead. All calls consume subscription
allowance, and failed calls may consume allowance too.

Results are saved under `runs/evaluation-<time>-<id>/`:

- `evaluation.json`: frozen questions, answer contracts, keys, versions, and settings.
- `scores.json`: per-field answers and scores, paired totals, and changes from each baseline.
- `comparison.md`: comparison table, answer keys, and links to full responses.
- A directory per case containing the ordinary debate report and transcript.

Run files stay local and are excluded from Git. The fixed case definitions and
answer keys in `evals/cases.json` are public; generated responses are not committed.

## Resume or recheck

```sh
python evaluate.py --resume runs/evaluation-<time>-<id>
python evaluate.py --report runs/evaluation-<time>-<id>
```

Resume preserves completed cases and completed turns within a stopped case. It
uses the saved case definitions and rejects changed settings, incompatible prompt
or grading versions, and transcripts that belong to another question. Timeout and
deadline options apply to the new attempt. An already completed batch requires no
provider installation or login. `--report` rebuilds scores without model calls.

## What the score means

Each answer includes an `agora-evaluation` JSON object with the fields requested
by the case. The model receives the question and field contract, including possible
choices, but not the answer key or grading rationale. The CLIs run in a temporary
directory with tools disabled, as in ordinary debates.

The grader compares those fields against a fixed key. Numbers are compared exactly
as fractions: `96`, `96.0`, and `192/2` are equivalent. Rounded approximations are
not accepted. Choice values must match exactly. A missing denominator has a separate
case where the correct result is `unknown`; abstaining on a solvable case does not
earn credit.

- `pass`: every requested field is correct.
- `fail`: the block is valid but at least one field is wrong.
- `format_error`: a missing, duplicate, malformed, or invalid answer block.
- `pending`: no saved response exists for that method yet.

A case must be completed before it enters paired totals. Format errors count as
non-passes and remain separately labeled. Stopped and unstarted cases remain in
the table so that missing results are visible. An improvement is non-pass to pass;
a regression is pass to non-pass. These transitions are counted against each
baseline independently, without selecting whichever baseline happened to do worse.

The checks cover arithmetic, a false numerical premise, missing information,
converse reasoning, and overgeneralization from a fictional study. They use no
live source retrieval, external facts, or model-based grader.

## Interpreting the result

The score covers the declared answer fields only. Read the full responses to check
that the explanation agrees with those fields, that the reasoning is valid, and
that the answer does not invent facts. A correct field alongside misleading prose
can still pass. The report links to each case for this review.

The debate gets more calls, peer context, and local evidence checks than a single
initial answer. Codex also writes every final summary. This is a comparison of the
current workflow, not an equal-budget experiment or an unbiased model ranking.
Each transcript retains CLI versions and any reported model names, but neither a
fixed model build nor deterministic generation is guaranteed.

Six simple, public cases can reveal wiring errors and obvious regressions. They
cannot establish general accuracy gains. They may be too easy, and knowledge of
public cases can contaminate future evaluation. Run a new batch for a repeat;
resuming a completed batch does not create an independent sample. Broader held-out
cases, repeated runs, human review, and equal-budget single-model controls remain
future work.
