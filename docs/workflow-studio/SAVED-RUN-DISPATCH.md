# Execute the original saved run

This slice extends #150 / #152 for #122 and #123. A browser or agent can now review
and run a persisted preparation by its identity and two hashes. The server loads
the **original ticket**, rather than trusting a reconstructed client copy.

## Workflow

Save a workflow to Workspace, prepare its saved revision (the `runs prepare`
command from [SAVED-RUN-CLIENTS.md](SAVED-RUN-CLIENTS.md)), and retain its preparation
request ID. Review the original record:

```bash
python -m studio_workflow runs review PREPARATION_ID
```

The response names the document and immutable revision, preset, expected job, record
hash and ticket hash. `controls_json`, `ticket_json` and `record_json` are exact
UTF-8 JSON text; do not parse and reserialize them to export a ticket.
`controls_json` lists projected changes, not all fixed graph inputs.

After reviewing the request, substitute the returned hashes:

```bash
python -m studio_workflow runs run PREPARATION_ID --record-sha256 RECORD_HASH --ticket-sha256 TICKET_HASH --approve
python -m studio_workflow runs observe PREPARATION_ID
```

The SDK equivalents are `client.saved_runs.review(request_id)` and
`client.saved_runs.run(request_id, record_sha256=..., ticket_sha256=..., approved=True)`.
MCP exposes `saved_run_review` in read mode and `saved_run_execute` in execute mode.
Providing matching hashes binds the content; it is not authenticated human approval.

## HTTP and architecture

`GET /api/workflow-studio/document-runs/{request_id}/review` returns exact JSON
strings, their hashes, the source identity and current-head metadata. This is local
read-only recovery; it does not rediscover nodes or prepare another ticket.

`POST /api/workflow-studio/document-runs/{request_id}/run` requires exactly:

```json
{"approved":true,"record_sha256":"<64 lowercase hex>","ticket_sha256":"<64 lowercase hex>"}
```

The adapter checks the stored record's integrity, the two approval hashes and the
actual document database identity. It then delegates to the unchanged
`execution.run_ticket` inside the existing Studio lock. That service still owns
workspace/reference/preset checks, exclusive fsynced intent, one dispatch attempt,
retained unknown outcomes, and `Studio.create_job`. There is no raw graph proxy,
new scheduler, new database, new dispatch journal or automatic retry.

The return value has separate `source` and `dispatch` objects. A newer document
revision never replaces this ticket. Repeating the **same** saved identity and
hashes recovers the original ticket's job or reconciliation state. If no intent
exists, that explicit action can dispatch the ticket: it is not observation.

Missing records, approval conflicts and corrupt storage refuse execution. If the
adapter cannot classify an exception after entering the dispatch seam, it reports
`reconciliation_required` with `dispatch_attempted: null`; it does not say that
nothing happened. Handler errors after a potentially executing route also omit
`generation_submitted: false`. CLI exit 3 means uncertainty; exit 6 means conflict.
Original `/run` and tab-local ticket behavior remain unchanged.

## Why keep the ticket server-side?

A JSON round-trip through JavaScript can round a large integer; even `1.0` becomes
`1`. Python's existing canonical hash distinguishes their serialized forms.
Changing the ticket representation can invalidate a previously retained receipt,
not merely change an image setting. The new path transmits only textual hashes
and identifiers. Exact review JSON also allows byte-identical downloads and
browser Web Crypto verification without a cross-language canonicalizer.

Primary references, checked 13 September 2026:
- [MDN JSON.parse precision and reviver semantics](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON/parse).
- [MDN JSON lossless number serialization](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON).
- [SQLite transaction ownership](https://www.sqlite.org/lang_transaction.html).

## Verification and limits

`python -m unittest discover -s tests -p test_workflow_saved_dispatch.py` exercises
real SQLite records and the real ticket journal with a synthetic runtime, plus
actual Studio Handler/origin predicates with its worker disabled. The Node
regression demonstrates that the previous parse/stringify route changes a wide
seed's ticket hash, then proves the new route retains both bytes and original seed.
Other cases cover approval refusal, missing/corrupt context, independent concurrent
calls, newer revisions, missing job evidence, response loss, post-boundary failures,
SDK/CLI/MCP permissions and no automatic retry. `test_workflow_mcp.py` additionally
checks the official SDK's tool discovery and execution contract when installed.

The source was retrieved through an authenticated, one-day GitHub Actions artifact
containing tracked files only (no `.git`, runtime data, credentials or local config).
The extraction has all tracked source but no original Git history. The temporary
snapshot workflow is isolated on `codex/workflow-review-snapshot`, not in this PR.

This still executes only registered-compatible image workflows supported by the
existing projector. It does not enable arbitrary graphs, references, native custom
widgets, cancellation, runtime changes, or model/package pinning. No GPU or owner's
workstation was used for these tests. Human creative decisions remain unchanged.
