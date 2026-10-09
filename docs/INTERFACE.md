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

1. Enter a question. Default models and one review round are ready to use.
   Open **Models & rounds** to choose named participant models, review rounds,
   or a summary provider. The summary follows that participant unless you choose
   another model under **Advanced model selection**.
2. Open **Rules, sources & timing** for discussion rules, public HTTPS sources,
   and execution limits. Choose **Custom…** in a model menu to enter another ID
   or alias. The menus are curated suggestions, not a live account catalog; the
   provider checks account availability when a call is made.
3. Select **Review setup**. The preview makes no model calls or source downloads.
   It shows the planned calls for each provider. Remaining subscription allowance
   is shown as unavailable; call counts do not estimate it.
4. Select **Start discussion**. One discussion can run at a time in this server.

Changing a setting clears the preview so the next start uses reviewed settings.
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
review the remaining calls, and resume. Requested models and previous settings
stay fixed. A server restart may leave an unfinished record labelled **Unfinished**;
it can be resumed when the transcript is compatible and no other writer owns it.

Authentication and model-availability errors appear in the discussion view.
If setup fails before a transcript exists, **Back to setup** preserves the form.
Renew an expired login in the official CLI, then resume. Agora never switches to
an API account or automatically retries a generation.

## Results and follow-up rounds

The result shows agreed, disputed, insufficient-information, and unverified issue
counts. Expand cited positions, the final summary, or individual answers. Quote
checks and model judgments remain separate; neither establishes factual truth.
Download the Markdown report from the discussion view.

**Revisit this issue** and **Add evidence** open a follow-up form with that
issue's topic, reason, and next step in the editable note. The latter also opens
the source field. Review the note and additional call count before starting.

**Continue discussion** opens a follow-up form. Add information, new sources, or
different rules and models, then preview the additional calls. The original
question remains fixed. A new directory preserves the original transcript and
inherits earlier answers. Existing source snapshots are retained. The existing
limits of five sources and twelve total review rounds still apply.

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
