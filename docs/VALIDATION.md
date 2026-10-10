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

## Remaining coverage

- Repeat representative cases and use independent blinded reviewers.
- Compare with a single-model workflow given a similar call and time budget.
- Test shared false premises, conflicting evidence, and instructions embedded in sources.
- Exercise quota failures, provider errors, process restarts, and saved-state recovery.
- Check language consistency across longer discussions and mixed-language sources.
- Observe first-time users, narrow screens, and unusually long or damaged records.

Add new failures here or in a linked issue. A passing case becomes a regression
example when related behavior changes; it does not close the whole category.
