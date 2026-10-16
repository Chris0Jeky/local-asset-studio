# Parallax stage recovery: implementation and handoff

Refs #1234 (stage-card recall only). The issue remains open for saved-plan acceptance (#1285), EXIF acceptance (#1288), finishing-worker scheduling and the optional stage-wording policy.

## Behavior

Every completed raw stage card offers both the clean plate and isolate edits, including after a split. Existing status text and the existing next-stage action are retained without duplicate buttons. Finished layer outputs and non-completed jobs do not gain reload controls.

The module asks before replacing Create, makes exactly one explicit `/api/parallax/stage` request and passes the verified response to the existing `beginParallax` writer. It never submits `/api/jobs`. In-flight uploads, continuations and modals hold the action. A newer draft, prepared plan, source job or backend invalidates the response. Returned plan/source identity, stage, geometry and words are checked before mutation. Failed and duplicate requests cannot leak or compete for the pending guard.

The shell loads a dedicated feature module; there is no rewrite of app.js or studio-workbench.js. Capture of stage-button clicks prevents the legacy bubble handler from issuing a second request. Existing gallery rendering preserves focus and playing media.

## Local evidence

The supplied archive identifies base 81c7f8479c77937e44a0d721249c498d866d484f. These are archive-based focused tests, not a full checkout of current main. The only edited production preimage, studio-shell.js, was checked against main accc8604311d2fd2f7a9e0278d3b05c0e2e96ba1 as blob 1d4bda1760c7d2e4fbb694092f8a6bf5d85cbf80. Both published production output blobs match tested bytes: shell 9a3bf115bb1c6e6168090342d5ab7299dac89fb9; feature 8c4152a43904fa5a0ca470bdd6bbe0081da75e0d.

- Node regression groups: 1 pass / 7 fail before implementation; 8 pass after. Two rendered-card failures reproduce the original missing actions; controller expectations require the new module.
- Python wrapper and actual SQLite-backed stage/Studio.prepare contract: 2 pass.
- Existing parallax route suite: 22 pass.
- Existing frontend_handoffs.cjs: pass.
- Desktop 1440px and mobile 390px fixture browser: six scenarios pass, no JavaScript exceptions, exactly six explicit stage requests, no generation. Real native controls and handlers, but inert API/storage mode.
- Native HTTP attempt: blocked before page load by net::ERR_BLOCKED_BY_ADMINISTRATOR. No native-origin, dynamic-loader or local-storage qualification is claimed.
- Python compilation, Node syntax and git diff checks pass. Repository validation passes 92 preset graphs, 176 pins and 158 LoRA names.

## Repeatable checks

```
node --test tests/parallax_stage_recovery.cjs
python -m unittest discover -s tests -p test_parallax_stage_recovery.py -v
python -m unittest discover -s tests -p test_parallax.py -v
node tests/frontend_handoffs.cjs
python tests/parallax_stage_recovery_browser.py --out .runtime/parallax-stage-recovery
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

`--inert` is an explicit test-only fallback for the browser, not a substitute for the native command. The new read-only Linux/Windows workflow uses native HTTP and retains its report even on failure. The canonical full-suite command, deadline and failure policy are unchanged. Final exact-source hosted checks, clean process exit and integration review remain merge gates.

## Interrupted-session qualification correction

#1286 is merged at accc8604311d2fd2f7a9e0278d3b05c0e2e96ba1. The maintenance qualification on its thread was corrected: a retrieved CI worker hash did not match the immutable source read. Treat that log's 5,419-test count as reported, not independently reconciled proof. A later log naming an unavailable registry test/revision was likewise not used to justify a source patch. #1285 and #1288 are not certified by this local work. Do not rerun until green, weaken the scanner or infer that the tracked shutdown defect #1270 is fixed.
