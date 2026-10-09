# Conflicting document evaluation

The document suite tests decisions from a fixed packet of fictional excerpts.
Every arm receives the same documents, question, and answer contract. It does not
download pages, call a search engine, or change sources between runs.

```sh
python budget_compare.py --suite documents
python budget_compare.py --suite documents --case dated-exception
python budget_compare.py --suite documents --all
```

One case uses 15 calls across mixed, Codex-only, and Claude-only arms. All three
cases use 45 calls. Resume and offline reporting use the parent directory, as
described in [the comparison guide](BUDGET_COMPARISON.md).

| Case | Decision to test |
| --- | --- |
| dated-exception | Apply the active EU exception instead of a later general announcement or an unrelated US configuration. |
| unresolved-runbooks | Recognize conflicting approved instructions without inventing a priority from an unverified chat note. |
| incompatible-metrics | Reject an improvement claim when the periods use different populations and denominators. |

Document IDs and text are frozen in the case definitions and included in the saved
question. Replacing a packet makes it incompatible with the existing transcript.
Answer keys and rationales stay out of generation prompts. Models receive only the
question, documents, and requested field types or choices.

The grader checks specific answer fields. In the date case, both the numeric
decision and governing document ID must be correct. In the other cases, inventing
a resolution or numeric rate fails the relevant fields. These checks do not score
every citation or sentence. Excerpts are embedded in the question, not registered
as retrieved HTTPS snapshots; they do not receive separate `agora-sources` quote
matching. The model is asked to cite document IDs in its explanation.

Read the prose for invented authority, silently changed rules, draft findings
presented as settled facts, and correct calculations used to justify the wrong
claim. Correct answer fields can still accompany those mistakes.

The packets are small, public, and synthetic. They exercise scope, effective dates,
unresolved conflicts, and measurement definitions; they do not establish performance
on long real documents. Blinded human review, larger packets, repeated runs, and
explicit prose-level criteria remain future work.
