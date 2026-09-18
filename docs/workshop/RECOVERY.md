# Workshop recovery and integration qualification

18 September 2026. Continuation of the interrupted Create redesign delivery.

## Published stack

- #540: Focus foundation, existing-control reparenting, recipe picker and Generate dock.
- #541: Studio layout, independent Atelier / Arcade / Sakura skins, original decorative SVGs and the offline prototype. Based on #540; merge the foundation first.
- #539: real-machine and owner UX acceptance. This work does not close it or any HUMAN_TODO decision.

The recovery found #540 published and the Studio branch present but unpublished. The second PR now exists, includes its parent in history, and no longer contains the temporary write-enabled transfer workflow. Workshop CI is read-only.

## Integration fixes

1. **Disclosure navigation race.** The native `details` toggle event is deferred. Navigating immediately after expanding the negative prompt could persist the old collapsed preference. The workshop flushes the visible state on `pagehide` through the existing `rememberNegativeCollapse` owner. It does not create another prompt or disclosure store.
2. **Nested modal handoffs.** Bundle and reviewed-setup success now call `finishRecipeSelection(target)` after their original guarded application succeeds. Both dialogs close and the deferred parent close event restores editor focus. Cancel, a changed draft, an unknown response and a refused application do not take this success path.
3. **Discovery deep links.** An explicit `recipe_goal` entry opens the picker, rather than leaving its requested shortlist behind a closed modal.
4. **Existing browser journeys.** Tests now open Saved setups / Under the hood / Change recipe before operating their moved controls, close the picker before editing the prompt, and assert successful reviewed-setup handoffs without manually dismissing the trapped modal. Storage, lineage, readiness, mutation and hit-target assertions remain in place.

## Fresh local evidence

Production JavaScript syntax checks, `git diff --check`, and repository validation pass (80 preset graphs/bindings and 136 pinned assets).

| Command / scope | Result |
| --- | --- |
| `node --test tests/workshop_contracts.cjs` | Focus: 3 pass; Studio: 4 pass |
| `python tests/workshop_browser.py --output <folder>` | Both layouts pass the 6 presentation check groups; original controls, guarded recipe changes, explicit Generate handler and responsive geometry |
| `python tests/workshop_handoffs.py --inert --output <folder>` | 4 pass: disclosure flush, bundle cancel, stale-draft refusal, successful editable handoff |
| `python tests/setup_apply_browser.py --inert --out <folder>` | 24 pass, including actual temporary SQLite storage, source copies, Undo, response-loss recovery and both dialogs closed |
| `python tests/setup_lineage_browser.py --inert --out <folder>` | 21 pass, including failed source observation, saved setup lineage and source replacement |
| `python tests/recipe_shortlist_browser.py --inert --out <folder>` | 72 pass, including ordered references, cancellation, stale responses and proposal export |
| `python tests/workshop_prototype.py --output <folder>` | 7 pass; embedded artwork, recipe guard, local reference retention, adapter feedback and mobile geometry; zero network requests or page errors |
| Targeted Python tests | Workshop frontend: 1 pass; setup application: 28 run / 1 skipped; preset model readiness: 23 pass |
| `node tests/frontend_handoffs.cjs` | Pass |

Regression-first checks reproduced the disclosure race and both bundle / reviewed-setup trapped-modal failures before their fixes. The same interaction assertions pass after the fixes.

### Evidence boundaries

Native localhost browser navigation is blocked in the recovery container. The explicitly named `--inert` runs use the repository's existing storage / transport / crypto component doubles; they are not native-origin, Web Locks, reload or GPU qualifications. CI runs the native variants without `--inert` and must be inspected at the final head.

The full local unittest discovery did not finish within the 180-second command limit. This recovery does not renew the interrupted session's full-suite pass claim. Targeted tests above completed. Earlier hosted successes belong to their recorded commits, not automatically to the final update.

No live ComfyUI generation, model installation, environment switch, human art approval or paired owner usability trial was performed. The default-height observation in VALIDATION is synthetic and is not a controlled before/after percentage against the wishlist's original QA state.

## Review and use

Use the prototype to compare layouts and skins, not to evaluate model quality. It contains demo data and a non-submitting Preview setup button. Its example artwork predates this redesign. Production uses the existing Generate path.

On the Studio branch, export with:

```sh
python scripts/export-workshop-prototype.py --output .runtime/workshop-preview.html
```

Review final-head Workshop UI, recipe-shortlist, setup-lineage, model-readiness and core checks before merging. Then complete #539 on the owner's actual Studio / ComfyUI installation. Retain both layout choices during that trial; no automatic analytics collection was added.
