# Studio UX QA — 13 September 2026

## Review reload recovery

[RELOAD-RECOVERY.md](RELOAD-RECOVERY.md) adds explicit per-tab draft and unconfirmed-save
recovery over the existing metadata revision/receipt service. It distinguishes local drafts,
confirmed server fields and exact earlier requests; #204 remains open for broader durability.


## What this pass changes

A practical review session should let someone inspect an output, write specific repair notes, mark a preference, look at its source, save, and choose the next operation without losing their place or their work. This pass makes that one connected workflow dependable before adding another launcher or tour.

The implementation is in `app/static/workspace.js` with narrow-screen treatments in `style.css`. It preserves the existing Workspace API, immutable media, continuation flow and execution owner. It fixes the delayed diagnostic context defect in #183 and advances #16; it does not close the wider task-oriented UI programme.

The asset details dialog now:

- Keeps unsaved title, tags, review and notes when Favorite changes. That action submits only the favorite bit.
- Offers the same explicit discard choice on Close, Escape and source-lineage navigation. A missing navigation target preserves the current editor; opening the same asset does not redraw it.
- Keeps the asset open after Save. A save commits its click-time snapshot, not whatever happens to be in the form when the response arrives. Newer typing stays visible and unsaved.
- Shows dirty, saving, saved and unconfirmed-save messages beside the fields in a polite status region. Duplicate mutations and leaving for a continuation are held during a write. A metadata request aborts after 15 seconds without automatic retry; timeout does not prove that the server made no change.
- Keeps Favorite and Trash errors inside the dialog. Trash/restore pauses editing while its outcome is pending, so typing cannot be discarded by a later close. Trash retains the existing recoverable-media semantics.
- Binds diagnostic success AND failure to the asset, dialog session and request. A→B→A and close/reopen do not make an older response current again. Reports remain explicitly requested, read-only and restricted to recorded Wan I2V jobs.
- Bounds narrow-screen media previews, including video and model preview containers, so the form is not pushed behind an almost full-screen preview. This is layout work, not a promise of reduced model or GPU memory use.

## Source and concurrent work reconciliation

The uploaded ZIP identifies `6dbcaa7b8be5acc600a991aab520dd6b30639f0e`. GitHub main had additionally merged #179. Its exact five-file delta was applied and every file identity checked; the entire reconstructed Git tree equals main's tree `bf8474bf33636db7501daa98189f66d2367566f0`, at commit `2bf0efb0da12c28d6767b8092544baab26c1c6cc`. That is the baseline for this pass, not the older archive alone.

Open work inspected: #169 (evidence-aware guides), #171 (resource-scoped bundle explanations), #180 (Wan decode admission), and #182 (read scheduling/resource profiling). This change adds no competing guide, recommendation evaluator, readiness gate or polling system. It intentionally leaves #117's failed-reference-check lineage save gap and #181's T2V readiness gap with their existing owners. Main was rechecked before publication.

## Evidence, not a blanket quality score

The initial real-Chromium, synthetic-API driver recorded **17 explicit expectations: 7 passed and 10 failed**. With this patch, the same 17 pass. The driver was then expanded to **30 expectations, all passing**, including A→B→A races, missing targets, all edited fields, in-flight navigation, keyboard Save, status semantics, Trash failure and preview bounds. Ten failing expectations are not ten independent root causes, and 30 passes do not certify every Studio workflow.

`RESULTS.json` records each original expectation, its before/after observation and the added coverage. `SCENARIOS.md` records the broader practical baseline, including unexecuted and still-open work. Screenshots, raw browser receipts, mutation logs and test output are emitted under the chosen ignored output directory. A downloadable handoff includes the local receipts; GitHub's dedicated native browser workflow publishes fresh run artifacts with seven-day retention.

**Execution boundary:** native browser navigation in this environment failed with `ERR_BLOCKED_BY_ADMINISTRATOR`. The successful local browser run uses explicit `--inert` mode: the real Studio HTML, JavaScript and CSS are rendered in Chromium, while storage and API transport are test doubles. API responses still come from the Python fixture server. This is not a native-origin/storage/network test, nor evidence from the Windows workstation. The default driver and added CI workflow use native HTTP; their outcome must be read from actual CI, not inferred from the local run. Synthetic video placeholders are not valid generated videos and their decoding is not assessed.

The regular offline suite and validation results are in `RESULTS.json`. Seventeen additional Node state contracts run inside one unittest wrapper and are counted as one test there, not added again to the suite count. They include actual abort-signal delivery, explicit-only retry, held handoffs, and independence from a stalled library refresh. Full-shell browser tests are separate opt-in checks.

A second, real temporary SQLite experiment confirmed a remaining defect: A saves a correction; B submits an older form with a different title and stale notes; A's correction disappears. This is #188. The browser session counter in this patch is **not** a server revision and cannot solve cross-tab or agent conflicts.

## Run and compare

```sh
python -m unittest discover -s tests
python scripts/validate-repo.py
node tests/asset_detail_contracts.cjs
# Development/CI environment only; never install this in managed model Python.
python -m pip install playwright==1.57.0
python -m playwright install chromium
python tests/asset_detail_browser.py --out .runtime/asset-detail-proof
# Only when native browser navigation is policy-blocked:
python tests/asset_detail_browser.py --inert --out .runtime/asset-detail-component-proof
```

Use `--baseline` to retain unmet expectations without failing the comparison run. This does not suppress runtime exceptions. Receipts identify the transport mode and source hashes. Compare matching scenario IDs and equal modes; never substitute an inert result for a native result. Tests serve a synthetic Workspace and must not point at a running Studio. No command above authorizes inference, an installation in ComfyUI, a backend switch or a generation retry.

For a workstation acceptance check, open a real existing asset; type notes; Favorite; cancel Escape; save; choose Continue with this. Confirm the exact source and notes remain, and stop before Generate unless a separate bounded generation is explicitly authorized. Repeat with the runtime offline and with a second client once #188 lands. Real screen-reader behavior, 200% browser zoom, browser refresh/crash recovery and native media remain unverified by this local pass.

## What to do next

The highest-priority next work is #188's metadata concurrency plus #117's source-availability/lineage save contract. After these, join existing guide evidence and continuation records into one contextual task summary as described in `ARCHITECTURE.md`. Keep that summary observational: it should explain what is preserved, what changes and what still needs action, without taking over execution.

No new human creative decision is required for these changes. Existing artwork selection, model-specific permissions and output acceptance remain with the owner and `HUMAN_TODO.md`; this pass changes none of them.

## Continuation: conditional metadata and recovery

The follow-on implementation for #188 is recorded in [METADATA-CONCURRENCY.md](METADATA-CONCURRENCY.md).
It adds actual Workspace revision checks and durable command receipts, a draft-preserving
conflict comparison, and explicit exact-request recovery. [METADATA-RESULTS.json](METADATA-RESULTS.json)
records this pass separately from the original local before/after checkpoint. The
metadata browser fixture uses the production metadata HTTP handler and temporary real
SQLite storage, with synthetic non-generation endpoints. #117 remains a separate
reference-lineage task; neither browser session epochs nor metadata revisions solve it.
