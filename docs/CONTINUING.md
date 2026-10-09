# Issue outcomes and continued discussions

The final report separates three model-reported outcomes for each material issue:

- `agreed`: the summarizer considers the participants' latest positions aligned.
- `disputed`: the latest positions still conflict.
- `insufficient_information`: evidence needed to answer is missing, even if both
  participants agree that it is missing.

Each entry includes both positions, quotations from each participant's latest
answer, the reason for the status, and a proposed next step. Agora checks that the
quotes occur in the correct latest answers. Missing, malformed, fabricated, or
outdated citations leave the entry `unverified`; absent issue declarations do not
mean agreement. At most five material issues are requested, so the list need not
cover every detail in a discussion.

These are the summarizer's interpretations. Matching quotations do not prove that
the positions agree or that the answer is true. Arithmetic, source, and attribution
checks stay separate. An issue can be labeled agreed while its factual basis still
needs verification. The runner does not add rounds automatically to force consensus.

## Add review rounds

Preview the extra calls without generation, downloads, or a new run directory:

```sh
python continue_debate.py --from runs/<completed-run> --add-rounds 1 --plan
```

Continue after reviewing the plan:

```sh
python continue_debate.py --from runs/<completed-run> --add-rounds 1
```

One added round uses three calls: one review from each model and a new Codex
summary. Two added rounds use five calls; three use seven. The existing initial
answers and reviews are not regenerated. The CLI prints the count before calling
models. Subscription allowance is still consumed, and token usage is not predicted.

You can also supplement the discussion:

```sh
python continue_debate.py --from runs/<completed-run> --note "The deadline is now fixed; reconsider the unresolved options."
python continue_debate.py --from runs/<completed-run> --rules "Prioritize reliability and state the remaining tradeoffs."
python continue_debate.py --from runs/<completed-run> --source https://www.rfc-editor.org/rfc/rfc2606.txt
```

`--note` adds information or a focus for the next review. Notes are preserved in
order across later continuations. `--rules` replaces the rules for new rounds;
omitting it keeps the current rules. Earlier answers keep their historical text,
and both models are instructed to reassess rather than assume old conclusions
still apply. The original question remains unchanged; use a note to explain the
updated conditions, or start a new discussion for a different question.

`--source` appends snapshots while preserving old IDs and captured text. Previously
unavailable or omitted sources do not retroactively verify old declarations.
There is no automatic refresh of an existing URL. Start a new discussion to replace
or refresh sources. The combined source limit is five.

## History and recovery

The command creates `runs/continued-<time>-<id>/` with a new report and transcript.
Its `parent.json` is a byte-for-byte snapshot of the completed parent's transcript,
including the old summary, rules, source snapshots, and issue outcomes. The parent
transcript and report are not rewritten. New reports show the previous rules and
issue outcomes alongside the current ones. Issue IDs are local to each report;
topics may be regrouped, so IDs are not an automatic semantic change mapping.

Each child inherits the earlier non-summary answers. Historical source availability
is recorded per turn. The old summary is supplied separately as historical context,
not as a fresh participant answer. Snapshot hashes and inherited-answer checks
reject accidental changes before resuming; they are integrity checks, not signatures.

If generation stops, use the new directory printed by the command:

```sh
python agora.py --resume runs/continued-<time>-<id>
```

This reuses completed new reviews too. Both reviewers still see the previous
round, even if the first review completed before interruption. To add more rounds
after completion, point `continue_debate.py --from` at the latest child directory.
Rerunning the original continuation command creates a separate branch and consumes
new calls; it is not a retry of the existing child.

## Limits

- Add 1–3 rounds per continuation, with at most 12 rounds in a chain.
- Notes and replacement rules each allow 8,000 characters. Accumulated notes allow
  16,000 characters. Long histories can still exceed a provider's context capacity.
- An incomplete parent must be resumed before extension.
- Valid schema-1 completed transcripts can be extended under the current prompt,
  even when their old prompt cannot be resumed. The change is recorded in the
  parent snapshot and the child's prompt version. This is not a controlled repeat
  of the original evaluation.
- Single-model comparison arms are rejected to avoid silently changing their
  provider assignment. This command uses the normal mixed Codex/Claude routing.
- Continuations are local CLI operations. Model selection and a local graphical
  interface remain future work.
