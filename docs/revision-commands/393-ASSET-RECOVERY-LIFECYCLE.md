# Inspect asset recovery without replaying it

Refs #393 / #204. Stacked on #698's opt-in device shelf. This slice adds a
read-only lifecycle inspector; it does not add a journal, metadata writer, retry
queue, migration, background polling or a second authoritative asset store.

## Operator flow

Open **Local recovery shelf**. Choose **Inspect this tab's asset recovery** or
**Inspect this tab's library recovery** to inspect existing session evidence,
even when device persistence is disabled. A stored shelf record also has
**Inspect receipt and current state**. These actions do not restore a draft or
replace the editor; they take an inspection snapshot.

The inspector separates the retained baseline, editable local text, immutable
pending request body, matching historical server receipt, and current lifecycle
observation. Missing and trashed targets remain visible. A mixed bulk command
retains every ID in authored order; it never drops missing IDs or treats the
receipt's ten-row preview as the complete current selection.

**Read receipt and current state again** is an explicit refresh, not polling.
**Export this inspection** exports private review text and observations as
`studio.asset-recovery-inspection/v1`. This is an evidence export, not an
importable shelf bundle. Use the shelf's ordinary Export for that separate purpose.
Inspection, export and closing the dialog send zero mutations. Only the existing
save/retry owners can dispatch a command, and this inspector provides no such
control. Local discard remains the shelf's explicitly warned local-only action.

Unknown outcomes remain unknown. Foreign/unknown Workspace records permit local
text inspection/export/discard but not a scoped server read from this inspector.
A historical membership receipt cannot recreate a deleted collection. An active
asset at a newer revision is described as restored only when a retained Trash
state or matching Trash receipt supplies the earlier state. Other unseen
lifecycle history is not inferred from a revision number.

## Read contract and bounds

`GET /api/assets/recovery-observation` takes exactly one `workspace_id`, one
JSON `ids` array, and an optional `collection_id`. It uses the existing Studio
loopback Host gate, `Cache-Control: no-store`, Workspace connection and identity
checks. POST is refused without entering the metadata writer.

One SQLite read transaction checks the Workspace and observes all targets and
collections consistently. A concurrent writer cannot mix old and new states
within that response. The existing command receipt is a separate GET; the UI
explicitly does not claim those two requests are one atomic snapshot.

Limits are 1–200 unique IDs, 128 code points per ID, 200 code points per title,
100 per collection name, 20 displayed memberships per target with a complete
count, 64,000 query UTF-8 bytes and 2 MiB encoded response bytes. The byte bound
matches the server's ASCII-escaped JSON encoder, not an optimistic Unicode
encoding. Malformed stored revisions/lifecycle timestamps or oversized summaries
refuse the entire observation rather than returning misleading partial rows.

Missing targets return only identity and `state: missing`. Existing rows expose
bounded title/revision/lifecycle and current collection summaries, not notes,
source metadata, filesystem paths, URLs or original media. All SQL reads use
bound parameters. Nothing decodes or opens an asset file.

## UI and race boundaries

The existing shelf dialog owns focus return. A keyboard inspection focuses its
heading once; late receipt/current-state results do not focus an input, reopen
the dialog or replace the editor. Cancellation, replacement inspections and
Workspace changes invalidate outstanding responses. The current target list and
refresh/export controls have stable containers. User text is rendered through
`textContent`, with 32,000-character text previews and wrapping for long IDs.

A failed current observation does not erase a valid historical receipt. A failed
receipt read does not convert observed asset existence into evidence of command
success. The unmodified pending body remains in both the local journal and the
inspection export.

## Verification

Run the following without a model or workstation runtime:

```text
python -m unittest discover -s tests -p test_asset_recovery_observation.py -v
python -m unittest discover -s tests -p test_asset_recovery_lifecycle.py -v
node tests/asset_recovery_contracts.cjs
node tests/asset_detail_contracts.cjs
python tests/asset_recovery_lifecycle_browser.py --out .runtime/asset-recovery-lifecycle
```

The browser fixture commits synthetic historical setup mutations through the
existing Workspace service, then requires zero browser metadata/model writes.
It exercises a 12-target mixed lifecycle, a missing asset with a surviving
receipt, deleted collection, restored target, unknown outcome, two page-local
drafts, held reads, keyboard focus, literal markup and inspection export.
Python also covers the full 200-target bound, an interleaved SQLite writer,
HTTP Workspace replacement, malformed state, no-store and wire-byte refusal.

The dedicated read-only CI checks out the exact PR head on Ubuntu and Windows.
Local `--inert` mode explicitly substitutes origin, storage, crypto/locks and
transport; it proves component/protocol behavior, not native browser guarantees.
The responsive case uses 390px with CSS 200% zoom, not browser-menu zoom or a
screen-reader usability certification. Only synthetic text and media enter CI.

## Remaining issue-level acceptance

This is a bounded inspection slice, not closure of all #393. The existing editor
still owns conflict/rebase and exact-retry decisions; broader retry-refusal
presentation, focus after every asset/filter removal, browser-menu 200% zoom and
screen-reader review remain to qualify. This PR does not rewrite the existing
save/refusal state machine or grant retry permission based only on an observation.

#388 remains the separate collection editor PR. #394 owns durable browser-File
staging and #395 owns shared setup history/forks/import commit; neither is
implemented here. No server receipt expiry, cleanup, generation, installation,
backend switching, original-media change or HUMAN_TODO decision is added.
