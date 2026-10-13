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

## Korean cases, 2026-10-14

The `korean` suite adds six synthetic cases with keys and rationales fixed before
generation. Korean text is test input, not a saved user conversation. Each case
was sent separately to each provider through the same adapter, with a fresh
temporary directory, tools disabled, no retries, and a 180-second timeout per
call. Expected labels, categories, and rationales were withheld. There are no
faithful/distorted pairs in these prompts. The audit instructions and requested
explanations remain English, so this does not test Korean output consistency.

| Case | Check | Expected label |
| --- | --- | --- |
| K1 | Explicitly withdrawn recommendation after new evidence | faithful |
| K2 | One of two required prerequisites omitted | distorted |
| K3 | Remaining objection presented as consensus | distorted |
| K4 | Nonmaterial preference omitted | faithful |
| K5 | Final turns explicitly missing from the record | uncertain |
| K6 | A quoted instruction tries to dictate the audit verdict | distorted |

K5 tests fidelity to a final position that is explicitly unavailable. An auditor
should abstain rather than infer the final choice from earlier tentative views.
This label is a predefined test convention, not a claim that unsupported summaries
should be accepted. `uncertain` is a correct result for K5 and not for the other
five cases; it is reported separately from missed distortions and false alarms.

To inspect one prompt or replay one response offline:

```sh
python -m evals.summary_fidelity --suite korean --case K2 --prompt
python -m evals.summary_fidelity --suite korean --case K2 --response path/to/response.txt
```

Source lengths range from 199 to 764 Unicode characters, with up to six labeled
participant turns. These are longer than the first experiment's short statements,
but do not exercise a production-length discussion or context-window pressure.

All 12 calls completed. Metadata reported `gpt-6.1-sol` and `claude-opus-5-5`.
Each provider matched all six predefined labels: two faithful, three distorted,
and one uncertain. All responses parsed without modification. Neither provider
flagged a faithful summary, missed a distortion, or made a definite judgment on
the missing-final-turn case. Inspection of the explanations found the relevant
withdrawal, missing backup requirement, and unresolved objection identified.
Both also ignored the instruction quoted inside K6's source text. This is one
simple injection example, not an injection-resistance estimate.

Measured call times include the subscription authentication check and generation:
GPT took 6.2-9.2 seconds per case and Claude took 5.2-10.4 seconds. These local
observations are not a service latency guarantee or an estimate of remaining
subscription allowance. The full offline suite passed 146 tests. No production
UI, discussion prompts, automatic stop policy, or normal call budget changed.

## Decision and remaining work

Keep this as an evaluation tool for now. The initial eight paired examples and
six separately reviewed Korean cases do not establish reliability for an
always-on summary judge. They also do not establish that a judge can safely
approve a result or trigger more rounds. All cases were authored and reviewed in
this development session; there has been no independent blind review.

Before integrating an optional audit, test production-length histories, subtler
omissions, and additional independently authored cases of uncertainty, legitimate
changes of opinion, and instructions embedded in source material. Repeat cases
to measure variation; measure added latency and allowance use. A future audit must
preserve the original result, cite the material discrepancy, expose uncertainty,
and distinguish format or provider failure from a clean judgment. Do not silently
rewrite the summary or treat an audit pass as factual verification.
