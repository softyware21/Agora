# Evaluating decision support

Related: #14. Agora should help the user make a feasible, informed choice. Agreement
is not the objective or a scoring criterion. A useful answer can be conditional,
identify a missing fact, or explain why none of the offered options fits.

## What to score

Report each dimension separately on a 0/1/2 scale: fails, partially meets, meets.
Do not hide a hard-constraint failure inside a good average score.

| Dimension | A score of 2 requires |
| --- | --- |
| Factual support | Correct checkable claims; assumptions and user reports identified; no invented verification |
| Constraint fidelity | Every stated mandatory constraint respected; preferences never override feasibility |
| Personal fit | Recommendations use stated priorities without inventing missing preferences |
| Useful clarification | No redundant question; any question has plausible answers that change the recommendation or next action |
| Conditional usefulness | Actionable branches, tradeoffs, and remaining uncertainty when a single choice is not justified |
| Revision | New information changes the relevant branch without erasing unrelated conditions |
| Effort for the user | Plain language, one focused question at a time, usable guidance even if the user declines to answer |

Also count unsupported factual claims, infeasible recommendations, unnecessary
questions, omitted prerequisites, and confident errors. Report answer/abstention
coverage so a system cannot improve apparent accuracy by refusing everything.
Evaluate clarification relevance by testing alternative answers, not by trusting
the model's explanation of why it asked. A schema check cannot establish that
a sentence contains only one useful question.

## Development cases

`evals/decision_quality.json` defines six fictional cases and answer branches:
missing budget, complete budget, an explicit conditional-advice request, conflicting
capacity evidence, a mandatory fact before a preference, and an updated constraint.
Keys and branches are for evaluators; do not include them in initial model prompts.
These are development cases, not a held-out benchmark. They have not all been run.

For each branch, start from the same saved base conversation, supply only that
branch's user answer, and preserve the rest of the context. Do not feed one branch
into the next. Check both recommendation changes and conditions that must remain.

## Fair comparison

Compare GPT alone, Claude alone, a single model with review opportunities, and
Agora. Every arm gets the same factual context, maximum call/time budget, source
tools, and access to the same scripted user clarifications. Charge clarification
and summary calls to that budget. Record actual calls and elapsed time; equal
call counts are not equal token or reasoning budgets. Report tokens only when
available, and do not invent subscription allowance measurements.

Randomize presentation order and hide the producing workflow from evaluators.
Use fixed facts or independently checked references for factual claims. Use
predeclared constraints and preference branches for open-ended decisions, where
there may be several acceptable answers. Repeat runs and report paired outcomes
and uncertainty, not just selected wins. Have independent people review the rubric
and reserve new cases that were not used to tune prompts. A model judge can assist
but cannot be the only authority for a claim that Agora is better.

Use first-time-user sessions to check whether people understand the recommendation,
conditions, and optional question without an explanation of debate mechanics.
Measure completion, errors, unnecessary steps, and time to a usable decision.
Offline DOM tests cannot replace these sessions or visual/accessibility checks.

## Current implementation and evidence

New UI discussions request an optional `clarification` field containing one question
and its purpose. Existing records without it still render. The result offers one
answer box; its button opens the existing follow-up editor with the question and
answer. It makes no model call. The user can edit the note and review the next
discussion's usage before starting. Drafts stay in browser memory by record and
question, including language changes; they do not persist after a reload.

The UI does not automatically request another round or replace the original
record. Default model and round settings remain optional. Parser and DOM tests
cover malformed fields, old records, draft separation, blocked actions during an
active job, and transfer into the continuation note. These checks establish
interaction behavior, not whether model questions are helpful.

Two subscription calls reviewed the design. The main accepted points were to
allow no question, prioritize factual prerequisites, preserve unrelated conditions
after an answer, and give single-model controls the same clarification opportunity.
Numeric success targets proposed by a reviewer were not adopted without a baseline.

Two further subscription calls used the new summary instructions on the same
authored room-budget discussion. Both reported models (`gpt-6.1-sol` and
`claude-opus-5-5`) produced a valid Korean question about maximum budget and
retained all three branches: A, B, or neither. This is a format and single-case
semantic check, not a full debate or a completed follow-up. The six-case comparison
and counterfactual follow-up runs remain outstanding. All 147 offline tests passed.
Visual browser inspection remains unverified after the earlier browser-tool policy
block; DOM tests are not a substitute for first-time-user or narrow-screen checks.

This change does not establish lower hallucination or error rates than a single
model. A useful first version is feasible; a guaranteed optimal answer for an
unknown user is not. Missing facts, conflicting preferences, and shared model
errors remain real limits.
