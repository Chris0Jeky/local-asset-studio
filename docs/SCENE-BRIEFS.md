# Scene briefs

Open **Scene briefs** in the Workspace navigation. A brief keeps one shared
direction and six typed slots together: background, sprite sheet, icon,
video/scene, audio/ambience and 3D asset. Each slot has intent, acceptance notes,
one selected candidate and one previous candidate.

1. Create a brief, name it and write the shared direction.
2. Optionally choose a Regular collection. Its active assets become the candidate
   pool. Changing collection clears the selections into each slot's previous
   candidate; restoring one checks that it belongs to the new collection.
3. Open a slot and choose a candidate. Search and page through real Workspace
   records, then use **Save brief**. Browser Back restores the previous picker
   page. If the catalogue changes, refresh from the first page explicitly.
4. Replace a candidate, clear the slot, or restore its previous candidate.
   A changed, archived, trashed, missing or reclassified source must be chosen
   again from its current record. Existing snapshots remain visible while you
   edit the wording.
5. Prepare a supported next step from the saved brief. The return link brings
   you back to the same brief and slot, where you explicitly choose and save a
   real asset. The link never asserts that an asset was generated from the brief.

## Preparation

| Slot | Supported handoff | Boundary |
| --- | --- | --- |
| Background, icon | A current saved look composes shared direction and slot wording into Full editor using the existing guarded look application | Combined wording must fit the look owner's 1,000-character scene limit. Missing recipe controls or installed choices can refuse preparation. Generate remains explicit. |
| Video/scene | Open Scene editor with the selected background, video and audio source IDs | Select **New scene** there to see those sources preselected. Scene creation validates media and tools; Render remains explicit. PNG, MP4 and 48 kHz PCM WAV are the supported scene formats. |
| Sprite sheet | Select an existing image | Directional sheet preparation is unavailable. |
| Audio/ambience | Select an existing audio asset | Ambience generation is unavailable here. Voice takes needs its own speaker, lines and pinned bundle. |
| 3D asset | Select an existing 3D record | Reference-driven 3D preparation requires its own supported recipe and inputs. |

Selection and preparation grant no art, licence, runtime, render or export
acceptance. In particular, acceptance notes describe checks to perform; they do
not record those checks as passed. A metadata fixture of a media type does not
prove that its bytes are usable by a renderer.

## Saving and recovery

**Save brief** writes the existing Workspace card store. It survives navigation,
tab closure and Studio restarts. Each change compares the revision that the tab
read; a newer revision wins without overwriting the losing tab's draft. Download
that draft if you need both, then reload the saved brief.

Unsaved browser recovery is scoped to the Workspace, brief and browser tab.
Recovered new briefs appear in **Open brief** as browser drafts. It survives a
reload in that tab, but is not a backup across tab closure. Save or download
before closing. If browser storage is denied or full, the editor retains its
in-memory draft and exposes a download. Unreadable recovery remains intact until
you explicitly discard it; it can be downloaded first. A lost save response is
not retried automatically. Reload compares the current saved record with the
retained draft before another write.

The initial integration is **Regular only**. Both view scope and creation intent
must be Regular. Private and All views show an unavailable state, and the server
rejects brief writes and preparation in those scopes. Changing privacy clears
brief content from the view while preserving the Regular draft.

## Ownership and verification

`app/scene_briefs.py` validates `studio.scene-brief/v1` bodies and routes
preparation to existing owners. `app/workspace.py` stores `kind=brief` in its
existing `cards` table and validates candidate ID, SHA-256, metadata revision,
type, privacy and collection membership within its existing write transaction.
There is no new asset database or job queue. Unknown body versions are preserved
and refused, never reinterpreted as empty briefs.

Focused checks: `python -m unittest discover -s tests -p 'test_scene_brief*.py'`.
The native isolated journey is `python tests/scene_briefs_browser.py --out <dir>`;
it uses production brief/card/asset owners, shipped frontend code, synthetic
records and fixture startup responses. Run it under the applicable shared
resource lease. Full repository qualification remains the unittest discovery
suite and `python scripts/validate-repo.py`.

Owner art and workstation decisions remain in [HUMAN_TODO.md](../HUMAN_TODO.md).
