# Calculation checks

Each answer can end with one `agora-calculations` block:

````text
The monthly cost would be 501 USD.

```agora-calculations
[
  {
    "claim": "Cost at 16.7 percent of maximum usage",
    "expression": "3000 * 16.7 / 100",
    "expected": "501",
    "unit": "USD"
  }
]
```
````

`claim`, `expression`, and `expected` are required strings. `unit` is optional.
There can be at most ten entries. An empty array means there are no declared
calculations; it does not mean that the rest of the answer has been verified.

## What is checked

Agora parses arithmetic rather than running generated code. It accepts decimal
numbers, parentheses, and `+`, `-`, `*`, `/`. Expressions are limited to 256 characters
and 64 syntax nodes; a numeric literal may have at most 50 characters. Calls,
variables, powers, scientific notation, and other operators are rejected.

Values are compared as exact fractions. `0.1 + 0.2` matches `0.3`; `1 / 3` matches
`1/3`, but not `0.333`. An expected value must be a single decimal or a fraction.
There is no rounding tolerance or unit conversion. Displayed results may be fractions.

| Status | Meaning |
| --- | --- |
| `arithmetic_match` | The expression equals the declared expected value. |
| `arithmetic_mismatch` | The expression and declared expected value differ. |
| `unverified` | An entry could not be evaluated or validated. |

If the block is missing or malformed, the turn is marked `not_declared` or `invalid`.
Malformed JSON, duplicate fields, extra blocks, and excessive entries do not produce
a passing result. Other valid entries in a well-formed block can still be checked.

## What is not checked

The claim text, inputs, units, sources, and relevance of the expression are not
verified. A model can declare a correct expression next to an unrelated or false
claim. A model can also omit a calculation. These checks do not measure overall
answer accuracy or coverage, and the summary is still model-generated.

## Records and review

Checks have IDs such as `T002-C01`: the first declared calculation in the second
turn. They are stored in `calculation_checks` in the transcript and shown in the
report. Earlier errors stay visible if a later turn corrects them.

Both reviewers receive checks from completed earlier rounds. A partial review
does not leak the first reviewer's new answer or checks to the second reviewer.
The final summary receives all prior checks and its own declarations are checked
afterward. A mismatch in the summary is reported; it does not trigger an extra call.

On resume, checks are rebuilt from the saved answers instead of trusting a cached
verdict. Runs made with earlier prompts cannot resume under this prompt version.
