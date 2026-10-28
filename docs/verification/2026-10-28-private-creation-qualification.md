# Private creation qualification — 28 October 2026

Refs #1673 and PR #1677; the larger creation-effort programme remains #772.
This resumes the published feature head `901e9ae30ee7e1eb10814ca273f073c17cf5409e`
and preserves current main `4e753e3e9c1f5f1ac2cb2ed918e5ae6469edd74d`.

## Causal findings and corrections

| Boundary | Retained failure | Correction and regression |
| --- | --- | --- |
| Job GET identity | The guard checked the first ID but the generic fallback returned the last; `/api/jobs/<regular>/<private>` disclosed private controls. | A generic job read accepts exactly four path components and returns that same `_scoped_job`. Real loopback controls cover mixed IDs, extra segments, duplicate separators, all three scopes, and valid regular/private/recipe reads. |
| Composed HTTP admission | An absolute-form target skipped the raw `/api/` guard but reached the document owner's normalized route. A valid private-header request created a regular SQLite document. | Reject non-origin-form and fragment-bearing targets before composed dispatch. Valid canonical document routes retain their existing behavior and private refusal. The new native HTTP cases fail on unchanged production and pass after correction. |
| Make migration | A quota exception or silently dropped private write was followed by removal of the regular recovery bytes and clearing of the visible draft. | Verify destination bytes before retiring the old copy. Unpersisted drafts stay in a bounded page-local map, remain available across scope changes and display an actionable warning. A later successful edit persists them. Shipped-function Node controls fail in four refusal scenarios before correction; the unchanged successful migration control passes. |
| Finder intent | The finder wrote regular `localStorage` and reloaded; older recovered goal state overrode the explicit destination. | Same-page choices go through the Make owner without reload. Cross-page choices use a single-use tab-local catalog intent. No private preference is written into regular persistent state. |
| Windows diagnostics | Six unreadable-record cases expected portable `experiments/runs/<id>/`, but received mixed separators. | Render the relative display path with `as_posix()`. Existing tests retain their exact message assertions. |
| Windows test isolation | Global worker-thread suppression also stopped subprocess pipe-reader threads; short temporary paths differed from the Workspace's resolved paths. | The independent Node health test has no worker fixture. The temporary Workspace root is resolved before path assertions. |
| Setup-lineage fixture | Synthetic `asset-0`/`asset-1` existed only in the browser fixture, not in the real SQLite setup owner. | Seed the same synthetic identities through the existing real-Workspace fixture and return structured storage errors. The source-classification guard is unchanged. |
| Retired source attachment | The browser driver waited for an error notice belonging to a retired draft. The production owner correctly withheld stale feedback. | Await the actual async click handler and assert unchanged replacement recipe, feedback and readiness. Existing live-draft failure/attachment assertions remain. |
| Workshop refresh fixture | Its sliced production function referenced newly introduced ownership variables absent from the fixture. | Include the real privacy projection functions and refresh ownership bindings. The original failure was reproduced locally; all 54 renderer cases pass after correction. |

The selective-key controls additionally reproduced scene loss and two tuning-loss
cases (throwing and silently dropped writes). Scene values now retain page-local
state; tuning copies are verified before either regular recovery record is retired.
Unpersisted private tuning remains page-local with the same warning. The tests
assert that regular recovery and another namespace remain untouched on refusal.

## Executed local evidence

- The expanded real-loopback HTTP module ran **9 tests** successfully after the
  two admission fixes. Before correction, the new cases expose both disclosure
  and an unintended document write using valid payloads.
- All **106 privacy contract tests** passed in **22.517 seconds**, no skips.
- Make's existing follow-up contracts plus the new migration/navigation contracts
  passed **27 Node tests**, including four causal persistence-refusal cases and
  the unchanged successful migration control.
- All **54 Workshop renderer tests** passed in **50.247 seconds**.
- The repository validator passed: **94 preset graphs/bindings, 189 pinned
  assets and 164 LoRA names**. The tracked-path count belongs to the checked
  snapshot, not a claim about the eventual merged tree.

Local execution uses Python 3.13 and system Chromium. Loopback *browser*
navigation is blocked by this environment (`ERR_BLOCKED_BY_ADMINISTRATOR`).
Ordinary Python HTTP/socket tests and renderer-only `set_content` tests work.
No transport bypass or simulated substitute is counted as a native HTTP browser
pass. `tests/make_privacy_transitions_browser.py` uses the actual privacy controls
and Make owner; its Linux/Windows hosted run is required, along with existing
creation/recovery, setup, Restyle and Workshop gates. Its receipt records
trusted UI event counts and automated wall time, never human completion time.

The complete suite and fresh final-head hosted checks are separate gates;
publication of this note is not a passing claim for unfinished CI. Exact run links
and final disposition belong in the PR qualification comment.

## Integration and limits

The exact current-main documentation was fetched with a read-only GitHub Actions
artifact and all 21 main/base document blobs were checked against Git identities.
A surplus final blank line in the inherited closeout note was removed; its
content is unchanged. Only `CURRENT_STATE.md` had a three-way conflict: both independent dated additions
were retained. No generated historical measurement was relabeled as current.

No installed runtime, model, GPU queue or owner media was accessed. Unknown
submissions are not retried. Privacy is organizational separation and explicit
read scope, not encryption, an authentication boundary, secure erasure or deletion
of ComfyUI copies. On storage refusal the earlier regular recovery copy remains
intentionally intact and the UI says so. Completed-run conversion, distinct
archive state and the first-hand adult-character/art-quality trial remain separate
acceptance; `HUMAN_TODO.md` is unchanged.
