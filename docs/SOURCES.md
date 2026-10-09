# Source checks

Use `--source URL` to supply a document. Agora retrieves it before the first model
call, saves the extracted text, and includes the same snapshot in both participants'
prompts. Failed downloads remain visible as unavailable sources.

## What is checked

Participants declare up to five source claims per turn:

```agora-sources
[{"claim":"The domain is reserved for examples.","source_id":"S01","quote":"example.com","relation":"supports"}]
```

The quote must contain 8–400 characters. Agora normalizes whitespace and performs
a case-sensitive substring check against the captured text. The result is
`quote_found`, `quote_not_found`, or `unverified`. The declared relation is the
authoring model's judgment, not a verified conclusion.

Reviewers can assess up to five earlier claims per turn:

```agora-source-reviews
[{"target":"T001-S01","relation":"unclear","reason":"The quotation omits the sentence that states the reservation."}]
```

Relations are `supports`, `contradicts`, or `unclear`. Reviews must reference an
earlier round's claim whose quotation was found; the summary may review any prior
turn. Valid reviews are labeled `model_assessment`. Invalid references and reviews
of unmatched quotations remain unverified. Missing or malformed declarations do
not become evidence. A passage can appear verbatim and still fail to support a claim.

## Retrieval limits

- At most five supplied URLs; identical URLs are fetched once.
- Public HTTPS on port 443 only, without credentials or query strings.
- Every redirect is checked again; at most four requests per source.
- HTML or plain text only, without compressed responses.
- Maximum download: 512,000 bytes. Larger responses are rejected.
- Maximum captured text: 12,000 characters. Longer text is marked truncated.
- A 10-second request budget per source. System DNS resolution can exceed it.

The HTML parser removes script, style, noscript, and template content. It does not
run JavaScript, inspect CSS visibility, or reproduce browser layout. Navigation
and other page text can remain. A quotation outside the captured portion cannot
be confirmed. There is no automatic search, PDF reader, or authenticated browsing.

## Privacy and replay

Requests send no browser cookies, API keys, or CLI credentials. DNS answers must
all be public addresses; the connection uses a checked address while TLS verifies
the original hostname. The destination still sees the request and source URL.
Do not supply private information in URL paths.

Captured text is sent to both model providers as part of the debate context. It
is also stored in the local transcript with the original URL, final URL, retrieval
time, truncation flag, and SHA-256 hash. The hash identifies the captured text; it
does not authenticate the publisher. Run files are plaintext and excluded from Git.

Resume reuses the stored snapshots. Changed snapshots or incompatible prompt
versions are rejected. Start a new run to refresh sources. External text is
presented as untrusted material, but prompt instructions cannot guarantee that a
model will ignore every malicious instruction embedded in a document.

## Remaining work

Agora does not establish that a publisher is reliable, a document is current, or
a claim follows from its quotation. It records model judgments about that last
question so they can be inspected and evaluated. Source discovery, reliability
checks, and comparisons with single-model answers remain separate work.
