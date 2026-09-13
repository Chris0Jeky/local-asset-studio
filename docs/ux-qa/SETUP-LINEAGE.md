# Named setups after an unavailable reference check

## Scope and decision — 13 September 2026

This is the narrow follow-up to #117, on main `06bd93aed2f019cb978eb5795e9f116cfb7ff749`.
It is independent of #199's asset metadata revision/receipt work. Both use existing state owners.

The actual workbench restore handler correctly distinguishes a failed availability request from
proof that a file is missing: it clears the unverified attachment and retains its source claim in
memory. Previously, **Save setup** persisted that claim even though its input held no file. On the
next load, the input mapping disappeared while the parent asset survived as unattributed history.

The decision here is to **block that inconsistent named save, not silently delete the user's source
history or invent a new pending-reference persistence format**. The message identifies Reference /
first frame, Last frame, or both, and asks for reattachment or a different source file. The draft,
wording and setup name remain unchanged. The user can still use the existing draft export to keep
an unresolved task. No availability retry, upload or generation is initiated by the blocked save.

## Implementation plan and delivered behavior

1. Reproduce the old Save handler emitting `/api/setups` for an empty but attributed input. Extend
   the real-script Node handoff contracts with first/last-frame cases and exact restore/swap checks.
2. Add a synchronous `checkedSetupControls()` projection/guard immediately before the existing
   named-setup POST. It reads `values()` once and checks the two known input mappings against that
   exact controls snapshot and declared parents. It returns the unchanged controls or raises a
   recovery message. It does not mutate the draft, parents, references or generation readiness.
3. Present named-save feedback beside Save in `#setupStatus`, a polite status region, as well as the
   existing legacy status. Empty names, rejected saves and confirmed success use the same surface.
4. Exercise the real restore/import handler in a complete Studio browser fixture. Let reference
   observation fail, assert that no setup reaches a real temporary SQLite store, reattach through
   the existing library picker, save, load in a fresh browser page, and replace the source again.
5. Keep confirmed-missing, fully attached, two-input and unattributed historical cases working.
   Run full-suite validation, then publish native HTTP browser CI separately from local inert tests.

### Existing contracts preserved

- A confirmed missing file still uses the existing claim-release path. Its now-source-free setup
  remains savable. This PR does not change availability semantics or silently retry failed reads.
- A parent shared by another attachment is never automatically removed. The guard refuses the
  incomplete mapping rather than guessing which relationship the user intended to preserve.
- Historical/unattributed parents are not assigned to an input or discarded by this guard.
- Reattaching through the library uses its actual parent mapping. Choosing a replacement follows
  the existing source-release handlers. Recipe reload followed by replacement still releases only
  the replaced input's source; the other frame's source remains.
- Named setups remain stored by the existing Workspace service. There is no schema migration,
  secondary store, queue, execution adapter or browser autosave rewrite.

## Additional QA finding: covered saved-setup buttons

The end-to-end test exposed a separate but adjacent interaction defect. At the desktop viewport,
when the full-width saved-setup row was scrolled into view, the sticky recipe picker painted above
its saved setup buttons and intercepted normal pointer clicks. The test failed on an actual click;
it did not force the click through or replace it with a direct function call.

The saved row now forms a positioned layer above that sticky picker. The regression checks the
actual hit target at the button's center and then performs a normal Playwright click before
continuing with source replacement. A screenshot is retained alongside the receipt. This change
is confined to the full-width named-setup row, not a global z-index or navigation rewrite.

## Evidence and commands

The original Node regression failed with `1 !== 0`: the old Save handler issued one setup POST
where zero was required. The extended browser pass also reproduced the pointer obstruction and
absence of adjacent save feedback. Logs of those failures are retained under the ignored runtime
output, not reclassified as successful runs.

The final local browser driver records **17 passing expectations**, using actual HTML/JS/CSS and
real temporary SQLite setup persistence. The original reference/handoff Node suite passes with
new first/last-input regression scenarios. The full-suite outcome and source identities are in
`SETUP-LINEAGE-RESULTS.json`.

Local navigation is policy-blocked (`ERR_BLOCKED_BY_ADMINISTRATOR` in this environment). Successful
local browser checks therefore explicitly use **inert storage/API transport**, via the existing
asset-detail test helper. They still exercise real restore handlers and save actual setup records
through the Python fixture; references and unrelated services are synthetic. This does not prove
native browser storage/origin behavior, local Comfy uploads, generated art or owner-PC acceptance.
The standalone Actions lane runs native HTTP and supplies separate evidence; its status at initial
publication must be read from the actual run.

```sh
node tests/frontend_handoffs.cjs
python -m unittest discover -s tests
python scripts/validate-repo.py
# In development/CI Python, never the managed model environment:
python -m pip install playwright==1.57.0
python -m playwright install chromium
python tests/setup_lineage_browser.py --out .runtime/setup-lineage
# Explicit component mode only when native navigation is unavailable:
python tests/setup_lineage_browser.py --inert --out .runtime/setup-lineage-component
```

The driver defaults to failing an unmet expectation; `--baseline` only records assertions instead
of stopping immediately, and does not hide runtime errors. Compare equivalent modes and source
identities. Fixtures never connect to the user's running Studio or ComfyUI.

## Boundaries and next work

This closes the browser restore → save gap, not a universal proof of imported recipe provenance.
Arbitrary external setup JSON and older already-corrupted/unattributed history are not repaired or
reinterpreted. Full metadata concurrency remains #199/#188; pending browser drafts across reload
still need a separate decision. A future pending-reference setup schema must preserve explicit
unknown/missing distinctions and asset/input attribution on round-trip, rather than treating the
absence of an attachment as proof that a source existed.

No artwork, model/runtime configuration, original media, human approval, or generation budget was
changed. Existing creative decisions in `HUMAN_TODO.md` remain open.
