# Asset recovery shelf (#392; parent #204)

The existing two-slot session journal remains the reload owner. Add an optional,
origin-local shelf containing bounded snapshots of that journal, not server state.
A pending command's exact JSON body and request identity remain independent of
newer editable text. No import, list, restore, export or discard sends a mutation.

## Storage and ownership

Use one versioned localStorage value, serialized under one origin-wide Web Lock.
Read and validate it while holding the lock, apply an expected-digest comparison,
then write and verify the exact bytes. Unsupported storage, Web Locks or WebCrypto
refuses shelf-dependent commands; there is no unsafe unlocked fallback. The
existing per-tab journal still works when the shelf is disabled. Browser-data
clearing and physically copied databases with the same Workspace identity remain
outside the guarantee. The digest detects corruption, not malicious tampering.

Opt-in is per tab and survives that tab's reload. Enabling discloses retained review
text and checkpoints existing records. Subsequent journal writes queue shelf
checkpoints; a metadata POST waits for its exact pending checkpoint. A later input
event cannot change that command. Clearing session recovery never deletes shelf
evidence. A new pending identity or a resolved pending record starts a new shelf
record rather than erasing the previous command. Capacity requires explicit local
discard/export. Existing records are never silently evicted or expired.

## Reconciliation and import

Restoration is explicit, same-Workspace and closed-editor only. An occupied session
slot that differs is not replaced: both viewpoints remain available. Imported
bundles are validated and displayed before explicit local import; unknown/foreign
Workspaces permit inspection/export/discard but not restoration or receipt reads.
Restoring can resume the selected shelf record using its exact digest as a CAS
precondition; another tab's change refuses rather than silently overwriting it.

The format admits only review metadata, baselines, drafts, scoped conflict
observations and exact metadata commands. Structured filesystem paths, media,
model data and arbitrary extra fields are excluded. User text is rendered as text.
Limits: 20 records, 256 KiB UTF-8 and characters per record, 2 MiB shelf/import,
JSON depth 16, 20,000 keys, 200 target/selection IDs, 128-character IDs and 64 KiB
individual strings. Strict JSON rejects duplicate keys, non-finite numbers,
unsupported versions and duplicate request identities. No implicit migration.

## UI and proof

Add a local recovery dialog with opt-in, bounded summaries, inspect, restore,
export, import inspection and explicitly warned discard. Focus stays in inputs
while asynchronous checkpoints complete; dialogs return focus to their launcher.
Test pure codecs/storage faults/CAS with Node, the actual editor dispatch barrier,
and native Chromium storage/locks/tab-close/reopen against temporary SQLite.
Synthetic fixtures only. #393 owns the remaining source lifecycle presentation;
#394 and #395 own durable File staging and shared setup history respectively.
