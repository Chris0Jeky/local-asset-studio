# Reviewed-setup history MCP reader parity — 26 October 2026

Refs #395. This is the bounded reader integration; the broader history and editing
UX acceptance remains open.

## Delivered behavior

Read mode now exposes `setup_draft_history`, `setup_draft_compare` and
`setup_draft_export_revision`. They call the existing `SetupDraftClient` readers
through the bridge's configured Studio transport. The history service still owns
SQLite snapshots, revision integrity, typed comparison sections, redaction and
export projection. The shared raw transport reuses the existing strict JSON
decoder for these reads. No new store, cursor owner, decoder or write command was
added.

Schemas require the original Workspace identity, bound revisions to the existing
256-revision limit and history pages to 20 summaries. Continuation requires the
observed head. Each invocation makes one GET, with no automatic continuation or
retry. The client verifies the existing response flags and 1 MiB history bound,
and checks the export's outer identity and nested draft digest. The MCP envelope
retains all supplied read arguments, including on Workspace/head refusals.

The malformed-response exercise also found an existing client wording defect:
a failed GET with an unreadable HTTP error body instructed the caller to inspect
a write receipt. The shared client's fallback now distinguishes a read from a
command by its existing request body. The original command receipt guidance,
transport behavior, refusal status and retry behavior are unchanged.

## Causal checks

The work started from local integration commit
`7530dfb6d770729d09f23ae6506dac1aba167af1`. Before adding the tools, the new
13-test bridge/protocol module failed because the three readers were unavailable:
54 assertion/subtest failures and two official-SDK exception groups wrapping the
same missing-tool assertions. The first fixture draft used a numeric wide seed;
the existing reviewed-setup owner correctly refused it. That fixture was corrected
to retain the seed as text before the missing-tool run and implementation.

After adding the adapters, those 13 tests passed. The subsequent malformed-GET
wording test failed for all three readers while the POST receipt-guidance control
passed. After the two-line owner correction, all **15 tests passed**, including
both optional official-SDK cases without skips. The isolated tools environment
uses the repository-pinned **mcp 1.30.0**, Python 3.12, Pillow 13.0.0 and psutil 7.2.2.

The new tests exercise:

- 100 real SQLite revisions read through five explicit 20-record calls;
- exact read arguments and Workspace/head evidence in MCP context;
- SDK parity, typed comparisons and canonical export with a declared wide seed;
- invalid arguments and unguarded continuation before transport;
- stale heads, foreign Workspaces and corrupt retained records without mutation;
- malformed identity/authority, actual escaped-byte bounds and nested export
  digest corruption;
- lost/truncated reads, closed bounded error streams, and no retries or unknown
  write outcomes;
- unchanged command receipt guidance for a malformed POST response;
- official MCP tool schemas/annotations and a real stdio → loopback HTTP → SQLite
  journey, including an intervening head change and a forbidden command control.

## Independent review corrections

Review of commit `9818a0d654062be4dc828b715fcf36f78a331e76` reproduced two inherited
typed-client gaps. Both were also reproduced against the unchanged shared-client
source at baseline `7530dfb6d770729d09f23ae6506dac1aba167af1`:

- A head-three page with no revisions and no continuation was accepted. The
  client checked descending order but did not require the complete expected page.
- The generic raw transport parsed up to 16 MiB before the typed reader checked
  its reserialized value. A **1,050,070-byte** whitespace-padded response passed,
  as did duplicate `head_revision` keys with the final value matching the guard.

The server's existing history-route classifier is now shared with `Client`.
Only bodyless history/compare/export requests select the history owner's raw byte
limit and `core.decode`; existing callback transport signatures, POST behavior
and HTTP error handling are preserved. Receipt IDs named `history`, `compare` or
`export` are explicitly excluded. The typed reader now requires the complete
contiguous descending sequence and an explicit, exact continuation value.

New shared-client tests produced **15 failures** before the correction, and two
new MCP bridge tests reproduced successful acceptance of the invalid replies.
The corrected client module passes **20 tests** and the MCP reader module passes
**17 tests**, including the two official-SDK cases without skips. Controls retain
valid full pages, partial last pages, the legitimate `before_revision=1` empty
page, refusal of a zero head, and the original transport contract for unrelated
GETs and POSTs. Declared oversize responses are rejected without reading their
body; unframed responses are read at most to the history bound plus one byte.

The reviewer's original probe now rejects all three invalid cases for both SDK
and MCP and accepts the valid control. Streams close in every case. Independent
re-review found no remaining blocker in the corrected production diff.

## Verification

| Command | Executed result |
| --- | --- |
| `python -m unittest discover -s tests -p test_workflow_setup_history_mcp.py -v` | 17 passed, 0 skipped |
| `python -m unittest discover -s tests -p 'test_reviewed_setup_history*.py' -v` | 71 passed |
| `python -m unittest discover -s tests -p 'test_workflow_*.py' -v` | 436 passed, official SDK installed; includes the 17 reader tests |
| `python -m unittest discover -s tests -p test_recipe_shortlist_apply.py -v` | 31 passed |
| `python scripts/validate-repo.py` | Passed: 93 graph bindings, 187 pinned assets, 160 LoRA names |
| `git diff --check` | Passed |

The default sandbox initially blocked a baseline loopback fixture and dependency
installation. The same fixture passed with narrowly scoped local-test permission;
the pinned SDK was installed in a separate tools environment. Those environment
refusals were not treated as product defects. Causal logs and the full-suite
qualification log are retained under `.runtime/setup-history-mcp/`.

The initial complete resource-lifetime run used the existing 1,200-second hosted
budget. It was deliberately interrupted before the review corrections; its
KeyboardInterrupt and temporary-directory cleanup warning remain in the retained
log. It is not a completed suite or a pass. A fresh full-suite result awaits the
final parent integration, which is undergoing separate corrections; exact
published-head hosted checks also remain pending. The Workflow MCP contracts lane now explicitly runs
the new module on Ubuntu and Windows after requiring the pinned SDK. No hosted
qualification, Windows result or merge is asserted by this local checkpoint.

## Remaining acceptance

#395 remains open for browser history/accessibility, operation/proposal receipt
associations, fork/import and explicit history commands, contention/persistence
acceptance, strict import validation, and retention/compaction review. Inspection
exports carry no import authority or portable media. No staging, generation,
installation, backend change or creative acceptance was performed. Existing
owner decisions and actions in `HUMAN_TODO.md` remain unchanged.
