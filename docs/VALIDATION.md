# Validation register

## First review: acceptance criteria

Review three cases: the saved complete-information laptop choice, a missing
denominator, and a commute preference tradeoff. The two new synthetic cases and
their acceptance checks are in `evals/ux-review.json`. They use the current UI
rules, including the optional result card, with at most two automatic rounds
(eight calls) and a 600-second generation deadline per case. Do not retry a failed
case automatically. This is a manual review protocol, not an `evaluate.py` fixture.

Record the tested commit, actual call count, model metadata, termination reason,
and a pass, fail, or inconclusive verdict for each dimension. Keep transcripts and
local record identifiers out of Git.

| Dimension | Pass criterion | Failure or limitation |
| --- | --- | --- |
| Summary fidelity | Card preserves the decision, material conditions, and unresolved qualifications from the full synthesis and participant reviews. | A condition that changes the decision disappears or the card implies stronger certainty. A valid JSON shape alone is insufficient. |
| Stopping | A usable conditional answer or an essential information gap ends the review without forcing agreement. | Peripheral wording drives extra calls, missing preferences become invented facts, or a material unresolved issue disappears. Assess policy correctness separately from whether its labels describe the situation well. |
| Answer quality | Required facts and calculations are correct; constraints and uncertainty are respected; advice can be acted on. | Unsupported claims, arithmetic mistakes, or unconditional advice on an underdetermined choice. |
| Added value | Identify a specific corrected error or useful addition relative to each initial answer. | Longer wording or more caveats alone do not establish improvement. A tie is a valid result. |

Compare each provider's independent initial answer with the final synthesis.
This reuses responses and costs no separate baseline calls, but the initial prompt
is debate-oriented and the synthesis gets more context and calls. Record that
confound. A reviewer who already saw the source cannot claim a blinded comparison.
An anonymized packet may support a later independent review; it does not make this
review blind. One run per case cannot establish reliability or general superiority.

## Review findings, 2026-10-10

Application revision: `112d79c`. Criteria were recorded in `6cc4873` before the
new results were reviewed. Evaluation and documentation did not change application
behavior. The existing 132 offline tests passed. They check implementation
behavior, not the semantic quality of a stopping decision.

### Saved complete-information choice

The concise card retained the recommendation and material assumptions: adequate
performance, equal screen and warranty conditions, comparable battery estimates,
and the user's stated priorities. Qualifications about an unprovided essential
feature or a reversal of real-world battery advantage remained visible. The card
did not repeat the disagreement about assumptions; the separate unresolved-issue
section and full synthesis retained it. This case passed the material-fidelity
check, not a claim that the card captures every discussion detail.

Both initial answers already chose the supported option with correct arithmetic.
The review clarified that adequate performance does not imply identical performance,
and that unspecified attributes need not all be equal. The final answer improved
the scope of assumptions, but did not correct the selected option or arithmetic.

This saved run used fixed rounds. An offline replay of its issue board with a
two-round automatic limit returned `running`: one recommendation issue was agreed,
while an assumption-scope issue remained disputed. This demonstrates that the
current policy cannot distinguish a usable conclusion with a secondary disagreement
from a disagreement that requires another round. It does not demonstrate an actual
extra live call or prove that every such disagreement is safe to ignore.

### Missing denominator

The new run stopped after five calls with `needs_information`. Both initial answers
and the final answer refused to invent an actual failure percentage. The final
answer requested the total request count using the same period and counting rules,
including both successful and failed requests. The card retained the missing
denominator and the counting condition. Fidelity and stopping passed this case.

The initial answers already had the correct conclusion. The final explanation
combined useful counting details and removed hypothetical percentages from the
main response. That is a presentation improvement, not demonstrated accuracy gain.
The conditional formula remains in the full synthesis rather than the concise
card; including it would make the short answer more useful without another call.

### Preference tradeoff

The run stopped after five calls with `needs_information`. Monthly costs of
160,000 and 40,000 KRW, the 1,000-minute monthly difference, and the 7,200 KRW per
hour tradeoff matched an independently calculated exact answer key. Both initial
answers already had these values and avoided an unconditional winner.

The card preserved the user's unresolved preference, both choices, budget
feasibility, and the condition that the hourly threshold assumes a constant value
of time. The full synthesis clarified that extra benefits outside the fictional
premise must not be assigned to one route. Fidelity and conditional-answer quality
passed this case. Improvements were qualifications and scope, not corrected core
arithmetic or a better selected route.

Stopping was appropriate, but `needs_information` is an incomplete description of
the outcome. The user asked for conditional guidance, which was delivered; choosing
a personal preference is not the same as supplying a missing factual denominator.
The current issue schema and stop message collapse these two situations. Outcome
classification needs improvement even though further calls were correctly avoided.

### Results and limits

| Check | Outcome in this review |
| --- | --- |
| Material conditions preserved in cards | Pass in all three reviewed examples; not a general fidelity guarantee. |
| Missing factual input | Pass: no invented denominator; stopped after five calls. |
| Unresolved preference | Conditional answer and stopping pass; outcome label needs improvement. |
| Secondary disagreement after a usable recommendation | Offline replay exposes unnecessary-continuation risk; no extra live round was run for this case. |
| Debate versus initial answers | Core conclusions and arithmetic were already correct. Some assumptions were refined; general superiority remains inconclusive. |
| Language | Both new final answers and cards were Korean. Longer and repeated runs remain untested here. |

The two new cases used ten successful calls in total, with no retries or extra
rounds. Recorded generation attempts lasted about 74 and 130 seconds. The saved
laptop case added no new calls. Reported models were `gpt-6.1-sol` and
`claude-opus-5-5`, with Codex producing the summaries. Time and call counts do not
measure token consumption or remaining allowance.

Next, define separate outcomes for missing facts, an answer awaiting user preference,
and an actionable recommendation with residual disagreement. Before changing the
automatic policy, test those distinctions against cases with material unresolved
risks so that reducing unnecessary calls does not hide an important objection.
Retain the original issue board and full synthesis during that evaluation.
Follow-up: [outcome classification](https://github.com/softyware21/Agora/issues/13).

## Remaining coverage

### Outcome distinctions: next bounded review

Use the existing denominator and commute examples as controls, without new calls.
Add the two cases in `evals/outcome-review.json`, at most two automatic rounds and
600 seconds per case (sixteen calls total, no automatic retries). Do not send the
acceptance checks to participants. Keep current prompts and stopping behavior.

Review against these distinctions before implementing any new outcome classifier:

| Situation | Required interpretation |
| --- | --- |
| Missing denominator | A fact blocks the requested numeric answer. Ask for that fact. |
| Complete commute comparison | The requested conditional guidance is complete; personal preference remains with the user. |
| Conflicting capacity reports | Equal-authority evidence conflicts on a mandatory prerequisite. Do not convert that conflict into an optional preference or average it away. |
| Price preference with unknown retention | A known violation rules out one option; an unknown mandatory specification blocks unconditional selection of the other. |

Inspect the full synthesis, concise card, issue board, and actual stop reason
separately. A safe answer may have a misleading outcome label. Agreement about
uncertainty does not resolve that uncertainty. These cases test conflicting input
evidence; they do not guarantee that the two models will disagree with each other.
Their agreement cannot validate detection of a material model-to-model disagreement.

- Repeat representative cases and use independent blinded reviewers.
- Compare with a single-model workflow given a similar call and time budget.
- Test shared false premises, conflicting evidence, and instructions embedded in sources.
- Exercise quota failures, provider errors, process restarts, and saved-state recovery.
- Check language consistency across longer discussions and mixed-language sources.
- Observe first-time users, narrow screens, and unusually long or damaged records.

Add new failures here or in a linked issue. A passing case becomes a regression
example when related behavior changes; it does not close the whole category.
