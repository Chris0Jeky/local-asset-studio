# Family navigation and deliberate recall

Frontend continuation of #1264 and #1206. The Asset dialog shows the bounded family strip and offers three separate actions: **Same recipe, new seed**, **Same seed, edit words**, and **Use as reference**. Result tiles expose the same ancestry under **Family & reuse**, with a link to the Asset dialog's recall controls. Children are fetched only on request.

The UI preserves missing and trashed steps, explicit multi-parent attribution, cycle diagnostics, and search/depth limits from the read-only service. It renders labels as text and rejects wrong identities, malformed types, over-bound collections and false authority flags.

## Existing state owners

`asset-family-adapter.js` uses the existing public `StudioSetupDraft` API. It never intercepts or replaces legacy `openAsset`, `renderJobs`, `selectPreset` or `applySaved` functions. Two bounded presentation observers decorate the existing dialog session and gallery; there is no polling loop or second asset/draft store.

Recall reads the selected output, checks the original baseline through `/api/recipe-check`, and asks explicitly before replacing the local Create draft. The selected output's actual seed and resolved wording are applied as a one-output draft through `StudioSetupDraft.adopt`. The existing owner validates supported controls, reference slots, graph identity and backend before adoption. No backend switch, source copy or generation is implicit. **Generate remains a separate press.**

The pending read/check retains the Workspace, Create stamp, Asset session/epoch, metadata fields and pending-save state. A later edit, foreign response or closed/replaced dialog invalidates adoption. Busy actions and unsaved/unconfirmed asset metadata refuse without discarding the editor. Current continuation, tile, parallax and exposed pose workflows require explicitly leaving that workflow before recall, rather than guessing whether their specialized state can be discarded.

**Use as reference** invokes the existing Pull-from-library button handler. Its current recipe, slot choice, loading guard and source-copy consent remain authoritative. The selected asset is searched and focused after the read only if the Workspace and Create stamp still match. Opening the picker copies no file; the user presses its existing attachment choice.

## Qualification

- 20 Node tests cover public-owner delegation, draft/metadata/backend refusal, source-picker ownership, identity/type/authority validation and no mutation after failure.
- The original pure recall harness covers exact large seeds, resolved wording, cancellation, stale checks, explicit confirmation and escaped markup.
- Both are invoked by the ordinary Python test discovery wrapper.
- `tests/asset_family_browser.py` serves the real frontend against actual temporary Workspace/job data and the real recipe-check implementation. It checks a four-step chain, ancestor/child navigation, unsaved metadata, both recall modes, exact selected-output seed/wording, held-response stale rejection, source-picker focus with no source copy, narrow/desktop widths, keyboard focus and 200% zoom. The independent workflow checks the exact PR head on Linux and Windows and retains synthetic screenshots.

Local Node and Python contracts passed. The local Chromium environment refused loopback navigation by administrator policy; that attempt is not a native browser pass. Hosted qualification must pass before merge.

## Remaining parent acceptance

#1206 stays open until the journey is registered in the central `tests/studio_use_cases.py` matrix and the remaining generalized result-tile/direct-recall and specialized-current-workflow cases are qualified. This PR supplies its own native journey, not a claim that the central matrix has already been extended. No owner art, model inference or runtime qualification is performed.
