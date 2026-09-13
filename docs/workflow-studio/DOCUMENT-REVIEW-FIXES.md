# Shared-document review corrections

Follow-up to the source implementation in PR #130; read with SHARED-DOCUMENTS.md.

The first hosted full-suite run caught a compatibility regression: the extracted
Client changed HTTPError into ClientError for legacy Workflow Studio endpoints.
The transport now preserves the original exception object outside document routes.
Document routes retain structured ClientError codes. A dedicated test covers both
contracts; the existing malformed-import test was not weakened. Hosted full-suite
and repository validation passed at 573426e after this correction.

Two reviewed storage issues are also corrected:

- History still returns every revision, but each added/removed/changed-node preview
  and changed-fields list contains at most 16 identifiers, with a corresponding
  `<field>_count` and explicit `truncated` boolean. The full stored summaries and
  revision documents are untouched. Read exact revisions for a complete comparison.
  A 1,024-revision maximum-length-ID response fixture fits below 8 MiB, leaving room
  under the client's 16 MiB bound. This is a bounded preview, not pagination or loss
  of revision history.
- Corrupt stored documents, origin JSON or history summaries report HTTP 503
  `storage_unavailable`, not a 400 client-command error. The original request should
  be retained while the stored evidence is inspected. No corruption repair is guessed.

Tests: test_workflow_transport_compat.py (2) and test_workflow_history_limits.py (3).
Along with 28 document contracts and 6 parent ticket tests, the local isolated suite
runs 39 tests, with the one real-AssetWorkspace integration skipped until full-checkout
CI. This correction does not constitute model execution or native-browser validation.
The subsequent current-head CI result belongs in the PR conversation; the earlier
573426e result is not evidence for untested later source.
