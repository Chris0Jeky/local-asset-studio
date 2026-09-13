# Bundle Explorer validation

Date: 13 September 2026. No workstation runtime, model installation, queue or
human choice was changed by this implementation session.

## Checks performed

- `node --check` on bundle-core.js, bundle-explorer.js and the edited shell.
- `node --test tests/bundle_core.cjs`: 16 passing pure-policy tests.
- `python -m unittest discover -s tests` in the **focused local file set**:
  the new Python wrapper passed. This was not a run of the full repository suite.
- `python tests/bundle_browser_smoke.py`: production bundle JS/CSS exercised in
  an inert Chromium fixture at 1440px and 390px, with reduced motion enabled.
  Keyboard entry/selection, invalid dimensions, editing/reset, Escape/focus
  return, stale inspection, changed-workbench rejection, explicit apply,
  clearing inherited adapters, one-output batch and zero write requests passed.
  Screenshots were inspected for the two layouts.
- The copied original shell was checked against its fetched Git blob SHA
  `5ad79b777633c5f455dfe75be5098ca229fc6570` before the small loader insertion.

The browser fixture uses an in-memory transport and the documented legacy
workbench seam. It runs the actual new UI files, but is **not** a full Studio
server test, an HTTP security test, Windows/native-tool integration evidence,
or model-quality evidence. It makes no external requests. A local browser with
Playwright is optional; the driver never installs one automatically. Set
`STUDIO_TEST_BROWSER` for an existing browser executable, or use installed
Chromium/Playwright Chromium.

The full repository and hosted CI were not run in the local focused file set.
Consult the PR's actual CI result rather than inferring a full pass from these
checks. This file intentionally does not turn a queued CI run into success.

## Workstation acceptance still required

Open Create and the explorer through the real Studio server. Verify both existing
preview links and the actual loaded KB. Apply one unchanged supported image
recipe and one deliberately edited variant; confirm resolved controls, reset
references, retained recovery draft, batch one, current dependencies and explicit
Generate. Do not run a neural job merely to validate navigation.

Check all supported keyboard interactions, 200% zoom, long source text and
screen-reader announcement/focus behavior against the full shell. Verify exact
model/runtime pins before claiming example equivalence. Exercise inspection and
example-index failures. Unsupported or reference-bearing routes must remain
inspect-only; no adapter compatibility or recommendation enforcement is claimed.

Full project gates remain `python -m unittest discover -s tests` and
`python scripts/validate-repo.py`, plus the existing frontend checks. The broader
representative-art and versioned-substitution acceptance belongs to #143/#144.
