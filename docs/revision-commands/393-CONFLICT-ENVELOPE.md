# Asset recovery: qualify revision-conflict observations

Refs #393 and #204. Child of #722; the existing journal, shelf and command API
remain the owners. This correction changes only when a single-asset conflict may
release its pending command for explicit comparison.

## Defect and admission rule

The previous branch accepted a 409 with the expected code and Workspace and no
truthy `missing_ids.length`. A wrong request ID, absent target accounting, null or
malformed snapshot, or an error from a GET status read could therefore clear the
exact pending command. Malformed snapshots could also poison the reload record
or leave the editor locked with no valid comparison or original pending identity.

A conflict now requires a POST response with all of:

- exact request ID and Workspace, one exact conflict ID and an explicit empty
  missing-ID array;
- exactly one metadata row for that asset and Workspace;
- a newer safe-integer revision and the complete typed metadata field set;
- the server's Unicode code-point limits: 200 title, 8,000 notes, 30 tags of 60
  characters each, plus valid review/favorite/lifecycle types.

Only whitelisted metadata enters the conflict journal. Extra media/source fields
are ignored, not exported or rendered. A malformed response retains the original
command/body/target/revisions and newer text; no conflict-resolution authority is
created. GET errors cannot discharge pending evidence even with a matching shape.
Older or equal revision observations require explicit inspection rather than
silently rebasing backwards. No response shape authenticates a server: this is
protocol consistency checking on the existing trusted loopback transport.

## Unchanged interaction

A valid scoped POST conflict still shows both views and requires an explicit
Keep my edits / Use saved snapshot choice. Neither choice sends a save. A later
reviewed save gets a new request ID and the reviewed current expected revision.
Missing targets, mixed library selections and generic refusals keep #722's
conservative evidence retention. Loading, status and comparison never retry.

## Verification

```
python -m unittest discover -s tests -p test_asset_conflict_envelope.py -v
node tests/asset_metadata_frontend.cjs
node tests/asset_detail_contracts.cjs
node tests/asset_recovery_contracts.cjs
python tests/asset_conflict_envelope_browser.py --out .runtime/asset-conflict-envelope
```

The 31 new editor scenarios produced 29 failures on the unchanged, SHA-matched
#722 editor/journal modules; all pass after correction. Real HTTP/SQLite responses
are passed to the JavaScript qualifier without rewriting request or target IDs.
They verify Unicode boundaries, missing-target refusal and receipt-before-conflict
replay. Ten browser assertions cover wrong-request data, GET conflicts, retained
exact bytes, explicit rebase/new identity and later historical confirmation.
Three existing synthetic conflict fixtures now include the server's actual
request/target fields; malformed snapshots are expected to retain pending recovery.

The dedicated Ubuntu/Windows workflow checks out the exact PR head. Local
`--inert` browser results substitute transport/storage and are not native-origin
proof. The local checkout is the uploaded ZIP plus SHA-matched parent modules;
only hosted CI establishes whole-parent stack integration.

## Remaining scope

No durable refusal annotation, general error-envelope authentication, storage
schema change, new journal, collection command, generation or background polling.
#393's complete focus/zoom/screen-reader qualification remains open. #394 selected
File staging and #395 reviewed-setup history/forks remain separate. HUMAN_TODO
creative, model/licensing and workstation acceptance decisions are unchanged.
