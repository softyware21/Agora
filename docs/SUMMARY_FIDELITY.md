# Summary fidelity experiment

Related: #13. This checks whether a separate model can compare a summary with
participant statements. It does not check whether those statements are true,
change automatic stopping, or add calls to normal discussions.

## Cases and scoring

`evals/summary_fidelity.py` contains four synthetic pairs: opposing choices within
the same `ready` category, a mandatory restore-test prerequisite, total versus
additional monthly cost, and a choice that depends on user preferences. Each pair
has a faithful paraphrase and a materially distorted summary. Keys were defined
before the live calls and excluded from the prompt. The order is fixed and mixed;
paired content remains recognizable, so this is not a blinded benchmark.

Each model receives all eight cases in one call. This saves calls but allows
cross-case cues. Cases are short English examples, not full discussion histories.
The grader counts correct labels, false alarms on faithful summaries, missed
distortions, and abstentions separately. Missing IDs, duplicate IDs or fields,
extra fields, and invalid responses cannot pass. Reasons are inspected separately;
the grader does not verify their meaning.

Print the prompt or grade a saved response without calling a model:

```sh
python -m evals.summary_fidelity --prompt
python -m evals.summary_fidelity --response path/to/response.txt
```

## Observed results, 2026-10-11

Two subscription CLI calls ran through Agora's existing Provider adapter, one per
provider, with a 240-second timeout each and no retry or API fallback. Each used
an isolated temporary working directory without answer keys and disabled tools.
Provider metadata reported `gpt-6.1-sol` and `claude-opus-5-5`.

GPT returned valid plain JSON and scored 8/8. Claude put its JSON inside a Markdown
code fence despite the plain-JSON instruction, so the original strict parser
rejected the entire response. Reading the saved response showed all eight labels
and explanations were substantively correct. This format failure is part of the
original result, not a failed semantic judgment.

The parser was then changed to accept either plain JSON or one complete `json`
fence, without surrounding prose. Replaying the same saved outputs scored 8/8 for
each provider, with zero false alarms, missed distortions, or abstentions. No new
model call was used for this replay. Regression tests reject extra fences and
surrounding text. Raw outputs remain outside Git.

## Decision and remaining work

Keep this as an evaluation tool for now. Eight easy, paired examples in one batch
per model do not establish reliability for an always-on summary judge. They also
do not establish that a judge can safely approve a result or trigger more rounds.

Before integrating an optional audit, test longer and Korean histories, subtle
omissions, uncertainty that requires abstention, legitimate changes of opinion,
and instructions embedded in source material. Use separate calls and unseen cases
to reduce pair cues; measure added latency and allowance use. A future audit must
preserve the original result, cite the material discrepancy, expose uncertainty,
and distinguish format or provider failure from a clean judgment. Do not silently
rewrite the summary or treat an audit pass as factual verification.
