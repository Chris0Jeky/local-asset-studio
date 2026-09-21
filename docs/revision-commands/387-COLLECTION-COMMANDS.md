# Transactional collection commands

Issue #387, following #642 / #314 and #645 / #120. Authority remains the existing `AssetWorkspace` SQLite database. `studio_workflow.collection_commands` owns the typed collection domain and SQL; the shared revision toolkit owns only canonical bytes, exact-byte integrity, request classification, revision comparison and byte-budget facts.

## Contract and migration

`AssetWorkspace` boot adds `collections.revision INTEGER NOT NULL DEFAULT 1`, a separate `collection_commands_v1` journal and `collection_command_schema` version 1. Discovery, ALTER, journal creation and marker insertion run inside the existing `BEGIN IMMEDIATE`. Existing IDs, names, timestamps, snapshots, media and memberships are retained. Reopen is idempotent. An unknown/incomplete schema is refused rather than guessed, rewritten or repaired.

A collection revision binds metadata/lifecycle, not an asset-owned membership set. The existing asset metadata commands continue owning membership edits and their own revisions/receipts. Delete deliberately removes the memberships present at its transaction boundary, as before; its expected collection revision is not an assertion that no asset membership changed since the editor opened.

A create starts at revision 1. Every accepted rename, including a no-op rename, increments once. Delete records the next revision in its retained tombstone receipt; it does not retain an empty collection row. All revisions must remain positive integers within `2**53 - 1` (asset metadata revisions may start at zero). Boolean, nonintegral, corrupt or overflowing revisions are never coerced or repaired.

## HTTP and Python APIs

```json
{
  "format": "studio.collection-command/v1",
  "workspace_id": "0123456789abcdef0123456789abcdef",
  "request_id": "caller-create-0001",
  "action": "create",
  "name": "Character studies",
  "description": "Reviewed grouping"
}
```

POST this JSON object to `/api/collections`, or call `workspace.collection(command)`. Create omits `id` and `expected_revision`. Rename supplies both plus name/description. Delete supplies both but omits name/description. V1 uses exact allowed fields; descriptions are explicit, even when empty. Request IDs contain 16–128 ASCII letters, digits, underscores or hyphens. Workspace identity is the existing 32-character lowercase hexadecimal ID from the library snapshot.

Command identity is canonical UTF-8 JSON of the submitted typed envelope. Key ordering and transport whitespace do not create new commands, but a changed string value does, including whitespace that the mutation later trims. Both command and receipt are capped at 16 KiB. The strict JSON reader refuses duplicate/reserved keys, nonfinite numbers, excessive nesting and non-UTF-8 transport. The global JSON ceiling is not widened.

Read status without writing or reserving an ID:

```text
GET /api/collections/commands/caller-create-0001?workspace_id=0123456789abcdef0123456789abcdef
workspace.collection_status(request_id, expected_workspace_id)
```

Exactly one nonempty Workspace parameter is required. Status is read-only and works when SQLite `query_only` forbids all writes. The handler is composed onto the existing Studio handler, not a second server or queue. Existing Host/same-origin checks remain in force. Fixed-length bounded JSON framing is required. Early rejection closes the connection; a fully consumed malformed JSON body is not drained a second time into the next pipelined request.

## Transaction order and receipts

Within a single `BEGIN IMMEDIATE`, verify the live Workspace identity; inspect the typed receipt; classify absent/replay/conflict before allocating an ID or reading current entity state; validate the expected head; mutate; check retained journal bounds; write and validate the receipt; commit. The connection context commits before a successful value is returned. A journal insertion/quota failure rolls back the collection and all member-asset increments together.

A response uses `studio.collection-result/v1`:

```text
status: committed | unknown
workspace_id / request_id: exact scope and request
receipt: immutable studio.collection-receipt/v1, or null for unknown
receipt_json: exact retained UTF-8 receipt text, or null
receipt_sha256: digest of those exact retained bytes, or null
current: independently observed collection metadata/revision, or null
replayed: true for historical replay/status (absent on unknown)
```

The historical receipt contains the action, canonical request digest, original result (`id`, `name`, `description`, `revision`, `deleted`) and `affected_asset_count`. Replaying the original create after subsequent rename/delete returns the original ID/result/receipt bytes, not a new ID and not current metadata disguised as the original result. A valid receipt survives invalid current metadata: `current` becomes null and `current_error` explains the failed observation without erasing the confirmed commit.

A missing receipt means **unknown in that read snapshot**. An already-running writer can still commit afterwards. A response lost after commit, or an exception after commit, is not permission to allocate a replacement request. Preserve the original request identity/content and inspect status in the original Workspace. No automatic retry, cancellation claim, filesystem transaction claim or model execution is introduced.

Deletion preserves original files, immutable snapshots, asset rows and other memberships. Each member asset's metadata revision advances exactly once, including trashed members. Replaying delete does not increment again. Any member asset revision overflow or invalid state refuses the entire operation before the first membership/asset write.

## Integrity, retention and public errors

The journal stores independent exact-byte digests and actual retained byte counts. Lookup checks lengths before loading the stored text into Python, then strict decoding, canonical form, version, scope, request identity, command/result correspondence and safe typed values. Whitespace alteration, rehashed invalid JSON, unknown versions, incorrect counters or semantic receipt corruption fail closed. No evidence is repaired, normalized in storage or removed.

The journal retains at most 4,096 committed requests and 32 MiB of combined command/result bytes. Bounds are inclusive for bytes; the next new command refuses at exhaustion. Accounting uses actual SQL byte lengths, not a trusted counter alone. Valid existing receipts remain replayable at quota. There is no pruning, request-ID reuse, background cleanup or rotation endpoint. Reaching the cap currently requires deliberate export/retention design; this slice does not pretend an automatic recovery tool exists. Digests detect integrity changes; they are not authentication against someone who can rewrite the database and all bindings.

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | `collection_invalid_command` | Invalid typed envelope/body |
| 404 | `collection_not_found` | Existing collection absent, before mutation |
| 409 | `collection_workspace_conflict` | Wrong live Workspace identity |
| 409 | `collection_request_conflict` | Committed request ID used with changed bytes |
| 409 | `collection_revision_conflict` | Stale expected head; response includes current metadata |
| 409 | `collection_revision_limit` / `collection_asset_revision_limit` | Safe revision ceiling prevents the mutation |
| 428 | `collection_precondition_required` | Scoped/versioned contract incomplete |
| 503 | `collection_storage_corrupt` / `collection_schema_unsupported` | Retain evidence for inspection; do not repair or retry as a new command |
| 503 | `collection_storage_unconfirmed` | Storage/commit outcome cannot be confirmed by transport; inspect the original ID |
| 507 | `collection_journal_full` | New command refused; existing receipts retained |

Errors use `studio.collection-error/v1`. Existing asset receipt tables and their public response/error shapes are unchanged. Collection failures are not relabeled as asset-command receipts.

## Compatibility and editor migration

Only an entirely **unscoped legacy** call, containing none of `format`, `workspace_id`, `request_id` or `expected_revision`, retains the old unversioned result shape. It has no CAS/idempotency promise; it still increments collection revisions and enforces deletion/overflow safeguards. Presence of any protected field selects the strict contract. A scoped old client receives 428, never a silent legacy downgrade.

The existing collection editor now captures the opened revision, creates a UUID per explicit submitted snapshot, sends v1 preconditions and adopts only the associated historical result. A confirmed create supplies the ID/revision for the next rename. Stale errors preserve the draft and do not automatically rebase it. Missing revisions or missing secure request identity refuse before dispatch. Newer typing and library selection remain untouched. The pending request is retained in the current session on uncertainty and its ID is displayed; no repeat is sent automatically.

**This is not browser recovery #388.** Closing/reloading still discards transient collection state. There is no persisted pending-command envelope, status/retry panel or automatic resolution across tabs. The earlier `docs/ux-qa/COLLECTION-EDITOR.md` describes the dated pre-v1 checkpoint; its no-migration/scoped-v0/receipt-gap statements are superseded by this contract, not requalified as current behavior.

## Rollout and rollback

Merge the explicit stack in order: #642, then #645, then this collection change. Keep the server and editor update together: the old scoped editor is intentionally refused by v1. Preserve a full SQLite-consistent Workspace backup before rollout. There is no automatic downgrade migration. **Do not roll back only the Python code against the migrated database**: the old four-column positional collection insert is incompatible with the new revision column. Restore a consistent pre-migration backup only after accounting for all later changes, or use a forward fix. Never drop receipt tables merely to make request IDs reusable.

`HUMAN_TODO.md`, media, runtimes, jobs, queues, installed models, arbitrary graph execution and owner acceptance are unchanged. See `387-VERIFICATION.md` for measured checks and the selected-source/full-app boundary.
