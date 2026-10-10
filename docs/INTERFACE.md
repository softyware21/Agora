# Local interface

The interface uses the existing Python runner and official subscription CLIs.
Install and sign in through the CLIs first, as described in the README. No frontend
build step, package download, or additional Python dependency is required.

```sh
python web_app.py
```

Windows users can open `start-ui.cmd`. The server binds only to `127.0.0.1` and
opens the browser. Use `--no-browser` to open the printed address yourself, or
`--port 8766` if the default port is already in use.

Opening `web/index.html` directly displays launch instructions instead of the
discussion form. Start the server and use its printed address. The shortcut link
in those instructions uses port 8765; use the printed address for other ports.

## Start a discussion

Enter a question and select **Think it through**. No setup preview is required.
The default uses the CLI default models, automatic review up to three rounds,
and a ten-minute generation deadline. The visible budget is at most eleven calls,
including a synthesis after each round. Calls use the existing subscriptions;
remaining allowance is unavailable and call counts do not estimate token usage.

**Customize this discussion** contains optional purpose presets, model menus,
review limits, rules, sources, and timing. **Fixed rounds** retains the original
single-synthesis workflow. **Preview settings** validates and counts calls without
model calls or source downloads. Changing settings invalidates that preview.
Model selections are remembered in browser storage after a successful start;
questions, rules, source URLs, and personal notes are not stored there.

Purpose presets append instructions to the saved rules. New UI discussions also
ask the models to adapt the review to the question and lead the synthesis with a
usable conclusion, reasons, uncertainty, and conditions that could change it.
These instructions do not add a separate classification call. Models may ask for
missing information in the result; there is no preflight interview.

New UI discussions request an optional `agora-result` block alongside the full
synthesis. A valid block shows the conclusion, conditions and uncertainty, reasons,
and next steps. Conditions stay expanded. The full synthesis and original text
remain available below, and unresolved issue topics remain visible separately.
Completed execution details follow the result instead of preceding it.

The card parser checks the version, fields, types, and length limits, not whether
the model preserved every important qualification. Missing or invalid cards fall
back to the full synthesis. Existing records and saved prompts are not rewritten.
Recognized JSON data blocks share one disclosure; malformed blocks remain visible.
Requested language and faithful summarization still depend on the model.

Model menus are curated suggestions, not a live account catalog. A summary uses
its participant's model unless an override is selected. Account availability is
checked by the provider when called. One job can run at a time in this server.

## Automatic review

Automatic review runs one round and a synthesis, then checks the reported issues.
It stops when all reported issues are agreed, any needs information, the assessment
is missing or has invalid citations, the reported topics and position wording
repeat exactly after normalization, or the round/time limit is reached. This is
not semantic detection of stagnation or proof that all possible issues are resolved.
The summarizer may miss an issue or misinterpret agreement despite valid quotes.

A continuing round uses the existing continuation runner and a new directory.
Earlier transcripts and summaries stay unchanged. The sidebar shows the latest
record in an automatic chain; **Models & execution details → Earlier review** opens
its predecessor. Private notes stay with the record on which they were written.
The final transcript contains inherited participant answers and the latest summary;
intermediate summaries are preserved in earlier records and parent snapshots.

Each extra round costs at most three calls, including its synthesis. Fixed runs
still cost five, seven, or nine calls for one, two, or three rounds. Automatic runs
cost at most five, eight, or eleven. Follow-ups omit the two initial calls. The
existing twelve-round cumulative limit still applies.

The generation time budget is shared across automatic rounds in one execution.
A manual resume grants the displayed time budget again but preserves the original
round limit from `automatic.json`. Saved calls are not repeated; provider failures
are not retried automatically. If stopped during the final synthesis, the record
may be complete and require a new follow-up instead of resume. The runner stops
between calls; source retrieval and login checks may add overhead.

Choose Korean or English with the sidebar language selector. The first visit uses
the browser language; later visits use the saved choice when browser storage is
available. Switching languages preserves the form, preview, and saved answers.
Only interface labels change: questions, rules, model IDs, transcripts, and
downloaded reports keep their original content. Provider diagnostics may remain
in their original language. Questions and answers may use any language.

## Progress, stop, and recovery

The page refreshes progress automatically and shows each answer after it is saved.
Answers format headings, bold text, inline code, flat lists, simple tables, and
HTTP(S) links. Declared Agora evidence blocks stay collapsed. **Source text** shows
the complete original answer, including unsupported Markdown. Nested lists are
flattened in the formatted view. Model-generated HTML is displayed as text, never
executed; images and other remote resources are not loaded.

**Stop after current answer** lets the current call finish and saves its answer,
then prevents the next call. It can take up to the per-answer timeout, plus login
or source-retrieval overhead. It does not refund a call already in progress. If
the summary is already running, the discussion may complete instead of stopping.

Closing or refreshing the browser does not stop the server. Reopen the page and
select the discussion from the sidebar. Ctrl+C in the server terminal requests
the same graceful stop and waits for the worker before exiting. Force-closing the
terminal can lose the answer in progress; completed answers remain on disk.

After a usage limit resets, open a stopped discussion, select **Resume discussion**,
resume directly or open the optional preview to review remaining calls. Requested models and previous settings
stay fixed. A server restart may leave an unfinished record labelled **Unfinished**;
it can be resumed when the transcript is compatible and no other writer owns it.

Authentication and model-availability errors appear in the discussion view.
If setup fails before a transcript exists, **Back to setup** preserves the form.
Renew an expired login in the official CLI, then resume. Agora never switches to
an API account or automatically retries a generation.

## Results and follow-up rounds

**Where we stand** opens with the saved synthesis and remaining questions. The
automatic stop reason is shown separately. **Explore the issues and evidence**
contains the common ground, open issues, citation comparison, and evidence checks.
Select an issue to compare the cited positions and open the original answers.
An unverified issue remains open even if the model called it agreed. Missing
outcomes never imply consensus. **Keep a personal note** is optional and collapsed.

**How we got here** groups independent answers and each review round, with both
participants shown together when space permits. Excerpts come from saved text;
full answers and requested/reported model IDs stay available. An incomplete pair
shows which answer has not been saved. The view does not infer changes of mind
or match an issue to earlier turns without an explicit citation. Same-round
answers do not see each other, which is stated beside each review round.

Active discussions open on the reasoning view. Progress describes the current
participant's activity and marks the independent-view, cross-review, and synthesis
stages. Completed records open on their outcomes. Switching views never starts
model calls. Short history labels are clipped question text, not generated titles;
the complete question remains available in the discussion view. History also
shows whether reported issues remain open.

Quote checks and model judgments remain separate; neither establishes factual
truth. Download the complete Markdown report from the discussion view.

**Clarify the assumptions**, **Try a counterexample**, and **Bring evidence**
open a follow-up form with the issue context and an editable instruction.
**Bring evidence** also opens the source field. Review the note and additional
call count before starting.

**Continue discussion** opens a follow-up form. Add information, new sources, or
different rules and models, then preview the additional calls. The original
question remains fixed. A new directory preserves the original transcript and
inherits earlier answers. Existing source snapshots are retained. The existing
limits of five sources and twelve total review rounds still apply.

## Evidence and response relationships

Each cited position has an evidence panel scoped to its source answer. Calculation
matches, mismatches, and unverified entries remain distinct. A source quote match
means the quote exists in the captured source, not that it supports the claim.
Checks may concern another claim in the same answer; the interface states this
rather than awarding a verification badge to the whole issue.

**Trace this position** links the participant's earlier answers. When a saved
summary attribution has both a matching quote and valid full-answer visibility,
the view also exposes the reported response relationship and both turn links.
This confirms the text and available context only. It does not establish that a
model changed its mind, was persuaded, or addressed the selected issue. Without
such a record, the interface says no confirmed relationship is available.

Follow-up actions let the user bring evidence, clarify assumptions and criteria,
or ask for a counterexample. They prepare an editable supplement and still
require reviewing the additional calls before starting. A user may also record a
judgment without running another round, including after the round limit.

## Personal judgment

Save a decision, its reason, and remaining questions at the end of a discussion.
These fields go to `judgment.json` beside the transcript, not into the transcript,
prompts, reports, or continuation snapshots. They are private local notes, limited
to 4,000 characters each. A follow-up starts with an empty judgment of its own.

Drafts survive language changes and navigation between discussions in the same
page. Save before closing or refreshing; unsaved drafts are held in page memory
and trigger the browser's leave-page warning when supported. A revision check
and a separate OS lock prevent simultaneous saves from silently replacing each
other. On conflict, keep a copy of the draft before using **Discard draft and
reload saved notes**. Unreadable notes do not prevent reading the discussion,
and the interface refuses to overwrite them.

## Visual direction

The interface borrows limestone, olive, and terracotta colors, column-like marks,
and restrained geometric borders from the idea of an agora. It uses local fonts
and CSS rather than remote assets. Functional labels remain literal: the visual
motif does not replace evidence states, controls, or readable contrast.

## Local boundaries

- The interface serves only its static files and selected reports from `runs/`.
  It rejects requests with an unexpected host, origin, or page token.
- Reports and transcripts remain plaintext files on this computer, excluded from Git.
  Model calls still send the supplied discussion context to the chosen providers.
- There are no external fonts, analytics, CDN scripts, or hosted UI dependencies.
- This is a local single-user tool, not an authenticated shared server. Do not
  publish its port or put it behind a public proxy.
- The sidebar lists immediate run directories. Evaluation batches and single-model
  comparison arms should be managed with their original commands.
- The sidebar shows dates for readable records and folder IDs for unreadable ones.
  Older or damaged records may be unreadable. Keep their original files; the
  interface does not migrate or delete them.
- The page does not stream partial model output or fetch a model catalog. Saved
  answers, CLI-reported model names, and explicit model IDs remain available.

UI tests use fake providers. Browser validation covers preview, start, graceful
stop, resume, completed results, continuation, and report downloads without using
subscription allowance.
