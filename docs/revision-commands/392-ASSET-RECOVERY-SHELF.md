# Asset review: device recovery shelf

Refs #392 and #204. The server Workspace remains authoritative. This feature is
an optional extension of the existing `asset-recovery.js` detail/library journal,
not a task queue, a replacement journal or a new server metadata store.

## Operator flow

Open **Local recovery shelf** from the library or asset detail dialog. Enable
**Keep detail and library recovery on this device for this tab** to checkpoint
existing and future tab recovery. The setting survives a reload of that tab; a
new tab starts with persistence disabled and discovers existing shelf records on
request. Wait for **Device recovery checkpoint verified** before closing the tab.
Until that acknowledgement, a just-typed draft may exist only in the current tab.

A metadata command is first retained in the existing session journal. When device
persistence is enabled, its POST additionally waits for a verified shelf checkpoint.
A storage/quota/lock/digest/CAS failure sends zero dependent POSTs. Changing the
Workspace or editor session while waiting also refuses dispatch. GET receipt
inspection does not depend on the optional shelf and never retries automatically.

After a browser restart, inspect a record, then explicitly restore it to an empty
or identical local slot. This does not open the editor, rebase revisions or send a
save. **Review retained draft**, **Check save status**, and **Retry exact save**
remain separate actions. A different occupied local slot is never overwritten.
Unknown or foreign Workspace records are inspect/export/discard only. Exported
JSON contains private review text; keep it somewhere appropriate for that text.

Import selects a bounded JSON file and displays summaries first. **Import
inspected records locally** writes only the local shelf. It does not restore a
draft, query receipts, apply metadata, copy inputs or start generation.

## Persistence and concurrency contract

One versioned `localStorage` value is serialized under an origin-wide Web Lock.
Each change validates existing records under that lock, checks the chosen record's
expected SHA-256 and generation, validates all limits/identities, and verifies exact
readback. Lock acquisition is bounded to five seconds. There is no unlocked
fallback. Secure loopback WebCrypto, Web Locks and browser storage must be available
for the opt-in guarantee. Disabled mode retains the existing session-only behavior.

Records retain creation/update time, monotonically increasing local generation,
Workspace identity and separate baseline, draft and immutable pending command.
The exact `operation.body` string is preserved, including whitespace. SHA-256
covers the canonical envelope and detects corruption; it is not authentication or
proof of server execution. Foreign browser scripts are outside this trust boundary.

Multiple tabs use digest compare-and-swap, not last-writer-wins. Different views of
the same pending request cannot be imported as ambiguous duplicates. Coalescing
keeps only the latest scheduled draft per journal slot; it does not accumulate one
queued record per keystroke. A pending command cannot be replaced or cleared by a
shelf update. After resolution or new intent, a new record is used. Prior evidence
remains until explicit discard, even when its receipt is already confirmed.

Clearing a session slot, closing an editor or disabling the shelf never deletes
persistent evidence. There is no silent eviction/expiry. A full shelf refuses new
checkpoints and dependent writes; explicitly export/discard a chosen old record.
Discard remains available after a capacity failure. It is local only and never
cancels, undoes or promises to prevent an in-flight server operation.

## Bounds and format

- At most 20 records; at most 256 KiB UTF-8 per record and 2 MiB per shelf/import.
- At most 200 command targets and selection IDs, 128 characters per ID, 64 KiB per
  free-text field, 200-character titles, 16 JSON levels and 20,000 object keys.
- A 32,000-character inspection preview; export retains complete accepted data.
- Import decodes the bounded file bytes as fatal UTF-8 before JSON parsing; malformed
  byte sequences are refused rather than replacement-normalized. Strict JSON rejects duplicate
  keys, including escaped duplicates, non-finite numbers, unknown versions/fields, invalid
  identities and mismatched digests.
- Import is all-or-nothing; duplicate record or scoped request IDs are refused.

Only whitelisted metadata is projected from server observations. Source paths,
URLs, media, models and arbitrary extra structures are not exported. User-authored
text can contain literal markup or paths and is displayed as text, never executed.
Invalid retained storage is not overwritten; bounded raw evidence can be exported
for inspection. Unsupported/future formats require explicit external recovery or
browser-data management rather than an invented migration.

## Verification and boundaries

`python -m unittest discover -s tests -p test_asset_recovery_shelf.py -v` executes
Node contracts for codecs, quotas/readback faults, count pressure, concurrent CAS,
coalescing, occupied/foreign recovery, exact-body round trips and dispatch races.
`tests/asset_recovery_shelf_browser.py` exercises the actual UI, HTTP handlers and
synthetic SQLite store. The dedicated read-only CI lane runs native Chromium on
Ubuntu and Windows. `--inert` is explicitly a local protocol/layout substitute;
it does not prove native storage, origin, WebCrypto or Web Locks behavior.

Browser data clearing, origin changes, private-mode retention policy and physical
copies of databases with the same Workspace identity remain limitations. The
existing review-queue bulk shortcut uses a separate per-asset fan-out and is not
covered by this shelf. #393 owns complete active/trash/missing/current-membership
presentation. #394 owns durable selected-File staging; #395 owns reviewed-setup
history/forks. No models were installed, jobs generated, originals changed or
HUMAN_TODO creative/acceptance decisions made by this implementation.
