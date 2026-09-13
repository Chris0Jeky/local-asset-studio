# Complete workflow HTTP replies before projecting JSON results

Fixes #231. Related #123 remains open for its broader agent acceptance.

## Reproduced mechanism

The shared Client called `HTTPResponse.read(limit + 1)`. CPython's bounded read
can reach EOF before the advertised Content-Length without raising
IncompleteRead. A syntactically valid JSON prefix was consequently accepted as
complete. Duplicate error-body readers had the same blind spot.

A real workflow HTTP fixture prepares a ticket and accepts its explicit run.
Only the reply's Content-Length is increased by eleven bytes. The old CLI
exports the shorter reply and exits successfully; the corrected CLI reports an
uncertain outcome, retains the original ticket bytes and creates no success
output file. Explicit recovery with that **same ticket** returns the original
job; the existing shared executor is called exactly once. This is not evidence
of duplicate generation in the old implementation.

## Shared response boundary

`studio_workflow.client.read_response(response, limit)` owns the bounded read
and framing checks; callers still own decoding and error projection.

- Validate all Content-Length fields and comma-separated values as nonnegative
  decimal integers; identical repeated values are permitted, conflicting or
  oversized values rejected.
- Accept only one supported chunked Transfer-Encoding field, without a competing
  Content-Length. Unsupported/duplicated codings are rejected visibly.
- Read at most the existing caller limit plus one byte. Reject excess bytes and
  require exact length when advertised. Short bodies raise IncompleteRead.
- Preserve complete length-delimited, close-delimited and valid chunked replies;
  the underlying HTTP library still checks chunk framing and the terminal chunk.

The same helper is used for document errors, saved-run errors, agent errors and
shortlist errors. Raw legacy Client HTTP errors remain unconsumed for callers;
there is no change to their public exception contract. No second transport,
server endpoint, job journal, request identity or retry owner is introduced.

## Error and compatibility behavior

An incomplete successful write reply follows the existing unknown-outcome
path: CLI run exit 3 and agent `outcome_unknown`, with the original ticket or
request identity. No automatic retry, rebase or replacement ticket is created.

Document errors cannot become ClientError from an incomplete body. SavedRuns
and AgentBridge retain the known HTTP status but discard the unverified body
and return their existing generic `http_error`; mutating agent calls retain
recovery guidance. Shortlist observation propagates transport incompleteness
rather than presenting a truncated diagnostic as authoritative.

Normal JSON objects, full-width integers, complete conflicts and existing
per-caller limits remain. Byte limits are still 16 MiB for Client success,
1 MiB for document/saved-run/agent error bodies and 64 KiB for shortlist errors.
This checks declared HTTP framing, not a signed server identity or model
execution outcome. Close-delimited framing uses EOF; without a declared length
it cannot distinguish intentional EOF from a lost suffix that happens to leave
valid JSON. Existing socket timeouts remain, not a new total-operation deadline.

## Regression procedure

`tests/test_workflow_response_framing.py` contains sixteen methods. Actual
loopback HTTP covers successful/error truncation, CLI accepted-run recovery,
malformed/conflicting/equal duplicate lengths, duplicated transfer headers,
chunk endings, advertised and actual size limits, integer preservation and raw
legacy HTTP-error compatibility. The first thirteen methods reproduced eleven
failing assertions/subtests and two differing exception outcomes on unchanged
code. Review added a duplicate-transfer case, which failed twice before its
correction. All sixteen final methods pass.

```sh
python -m unittest discover -s tests -p test_workflow_response_framing.py -v
python -m unittest discover -s tests -p 'test_workflow*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
git diff --check
```

The existing Workflow MCP contracts lane now runs framing tests on Linux and
Windows alongside required official-SDK protocol tests. Local optional-MCP
skips remain distinct from that hosted gate. Final full-suite/hosted outcomes
are recorded on the PR separately. No browser or live-MCP-host acceptance is
inferred from these transport tests.

## Rollback and primary references

No persisted data or ticket format changes. Reverting restores the former
read behavior and duplicated caller reads.

- [CPython 3.12 HTTP client source](https://github.com/python/cpython/blob/3.12/Lib/http/client.py), HTTPResponse.read: bounded-read short-body behavior is explicitly retained for compatibility.
- [Python HTTP client response documentation](https://docs.python.org/3.12/library/http.client.html#httpresponse-objects).

## Reconciliation and operating boundary

Inspected main `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3`, tree
`5e920817385cf6c6d4aef2154267eb6c0d0c4511`. The downloaded tracked-source
archive reproduced that tree before edits. No PR was open at the initial
check. The untouched offline suite ran **1,674 tests, 16 skipped, no failures**.
Optional/live cases were not executed. Existing Pillow deprecations, deliberate
storage-fault diagnostics and the exit-time socket ResourceWarning were retained.

This is a software-only maintenance slice. No owner database, source media,
configuration, model, runtime process or HUMAN_TODO decision was changed.
No generation, upload, download or new artistic/rights acceptance follows from
the fixtures. Independent review and owner-runtime acceptance remain separate.
