# Model settings

Agora passes model choices to the installed official subscription CLIs. It does
not keep a catalog of models or check account access before generation. An unknown
or unavailable model can fail on its first call. Agora stops and preserves completed
answers; it does not select a replacement or fall back to API billing.

## Participants and summary

| Option | Purpose | When omitted on a new run |
| --- | --- | --- |
| `--codex-model` | Codex participant model ID | CLI default |
| `--claude-model` | Claude participant model ID or alias | CLI default |
| `--summary-provider` | `codex` or `claude` | `codex` |
| `--summary-model` | Model used for the summary only | The selected model of the summary provider |

```sh
python agora.py --question "Review this plan" --codex-model gpt-6.1-sol --claude-model opus --summary-provider claude --summary-model sonnet
```

This requests Opus for Claude's initial answer and reviews, and Sonnet for its
summary. These names are examples, not an account availability guarantee. Use
model IDs or aliases accepted by your installed CLI and subscription. Agora
accepts identifiers up to 128 characters containing letters, digits, dots,
underscores, or hyphens. Provider-specific compound expressions are not supported.

Both adapters use `--model`. Codex's interactive `/model` picker shows account
availability; see the [official Codex commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
Claude accepts model IDs and aliases through its
[official CLI option](https://code.claude.com/docs/en/cli-reference).
Agora's isolated execution settings still apply, including disabled tools and
subscription authentication checks. A CLI default is not a promise to load your
usual interactive settings: the adapters ignore or restrict user configuration.

## Preview and recording

```sh
python agora.py --rounds 2 --summary-provider claude --plan
python agora.py --resume runs/<run-id> --plan
```

Two review rounds with a Claude summary use seven calls: three Codex and four
Claude. The total is unchanged by the summary provider. A resume preview counts
only unfinished turns. A preview makes no model calls, login checks, or source
downloads and does not validate model availability. Counts are not token budgets
or remaining subscription allowance.

Transcripts save the requested selection in `model_selection`. Each new turn
records `metadata.requested_model` separately from `metadata.models`, the IDs
reported by the CLI. Reports display both. Missing reported IDs are shown as
unavailable, never filled with the requested value. Defaults and aliases can
resolve differently over time; even a specific ID does not freeze a provider's
implementation. Older transcripts lack explicit requested settings.

## Resume and follow-up discussions

`--resume` loads the saved model selection automatically and rejects model options.
After a usage limit resets, resume the saved directory to avoid repeating completed
answers. The same requested selection is used even if the local CLI default has
changed; a saved default still resolves through the current CLI.

Completed discussions can change models in a new continuation:

```sh
python continue_debate.py --from runs/<completed-run> --summary-provider claude --summary-model sonnet --plan
python continue_debate.py --from runs/<completed-run> --summary-provider claude --summary-model sonnet
```

Omitted options inherit the parent's selection. Changing the summary provider
clears its previous explicit summary model unless you also supply a new one.
Use `--codex-model default` or `--claude-model default` to return to a CLI default;
`--summary-model default` returns to following the selected participant model.
Inherited answers retain their original model metadata, and the parent snapshot
preserves the old configuration. Model changes apply only to new calls.

The evaluation commands currently use CLI defaults and their existing fixed
routing. These model options apply to `agora.py` and `continue_debate.py`.

## Interface choices

The local interface offers a default option, named suggestions, and a custom ID
field. GPT suggestions use explicit IDs; Claude suggestions use the `sonnet`,
`opus`, and `haiku` aliases. Changing the summary provider resets its separate
model to follow the participant. Saved custom IDs survive continuation and
language changes.

The suggestions are maintained in `web/app.js`, based on the
[OpenAI model catalog](https://developers.openai.com/api/docs/models) and
[Claude Code model configuration](https://code.claude.com/docs/en/model-config),
reviewed on 2026-10-10. Inclusion does not guarantee access through a particular
subscription or CLI version. These choices do not query account entitlements,
measure remaining allowance, or enable API billing. Use the default option if
unsure; an unavailable selection reports the provider error without silently
switching models.
