# Summary attribution checks

Agreeing on a conclusion is not the same as accepting another speaker's new
argument. In particular, two reviews in the same round cannot respond to each
other. Both receive the previous round, even though their calls run sequentially.

Agora supplies a turn map with stable IDs such as T001 and T002. The map lists
which full answers were available to each speaker. Initial answers receive no
peer answers; reviews receive the previous round's two full answers; summaries
receive every earlier answer. Older arithmetic and source-check snippets may also
reach reviewers, but those snippets are not the complete earlier answers.

Summaries are asked to cite turn IDs in their prose and append up to five records:

```agora-attributions
[{"claim":"The reviewer retained the original conclusion.","turn_id":"T003","quote":"I agree with the initial conclusion.","responds_to":"T002"}]
```

`turn_id` identifies the speaker's answer. `responds_to` identifies the answer it
is claimed to address; use null for a simple quotation with no response claim.
Quotes must contain 8–400 characters, and claim text is limited to 500 characters.

The report and transcript rebuild checks from saved answers:

- `quote_found`: the quote occurs in the cited answer after whitespace normalization.
- `quote_and_context_match`: the quote occurs and the declared response target was
  among that speaker's full answers.
- `quote_not_found`: the words do not occur in the cited answer.
- `context_not_available`: the declared response target was not a full answer
  available to that speaker. This includes either direction of a same-round review.
- `unverified`: the declaration is invalid or refers to an unknown turn.

Missing and malformed blocks are shown as `not_declared` and `invalid`. They do
not become passes. Plain prose without a declaration remains unchecked. A summary
with a failed check is saved with the failure visible; it is not silently rewritten
or regenerated. No additional model calls are used by the checker.

## Limits

These checks establish quotation presence and full-answer availability only. A
speaker may have received a claim but never agreed with it. A real quotation can
be taken out of context. A model can also omit a response relationship or choose a
different quotation. The checker cannot establish that a paraphrase or a claim of
agreement is semantically justified. All such interpretations still need review.

The context map is derived from the orchestration rules, not a model's account of
what it saw. Resume preserves the previous-round boundary, including when the
first reviewer has already completed and the second one is resumed later.

This feature changes the generation prompt version. Existing Markdown reports
and JSON transcripts remain readable as files. Older runs cannot be resumed or
regraded through commands that require the current prompt version; start a new
run for the new behavior. Historical generated answers are not modified.
