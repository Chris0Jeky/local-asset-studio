# Inspect effective scope and export an explicit ComfyUI mask

Implementation for #245/#243, building on transform PR #279. This is a CPU-only
review/export path. It does not submit jobs, register a model adapter, approve
artwork or change the existing Production/native execution paths.

## Why this step exists

A scaled mask can have different coverage from the original brush selection.
The workflow needs to expose that **before** a caller uses the effective-mask
pin at Apply. Source transparency, model sampling permission and final source
write coverage must not be interchangeable.

`repair_scope_review.py` reconstructs the prepared bundle against the external
checked character-edit plan and transform request, then creates three views:

1. Effective source-space write support and source protection.
2. Added/removed support relative to the authored mask, with independent counts
   for all fractional-coverage changes.
3. Working context, sampling coverage, and protected padding.

Exact counts and bounding boxes use the full-resolution masks. The diagnostic
views use bounded, nearest-neighbour thumbnails; a very thin area can disappear
in that thumbnail. The original six prepared files are copied byte-for-byte into
the review output so the complete masks remain available. The checkerboard is
only a transparency display background, never a model matte.

## Run the synthetic demonstration

```console
python scripts/repair_scope_demo.py --out experiments/runs/scope-demo-001
```

Use a new directory. The command reuses the existing two-character synthetic
transform demonstration, creates a scope review and reconstructively verifies
it. Open `scope-review/scope-review.html` inside the output. The same directory
contains source/working masks, the separate Comfy mask carrier and the receipt.
No user reference art or model is used. The test candidate from the existing
demo remains synthetic CPU pixels, not a successful anatomy correction.

## Review an actual prepared bundle

Use the existing plan, request and prepared bundle from `PIXEL-TRANSFORMS.md`:

```console
python scripts/repair_scope_review.py preview --workspace C:/AI/repair-work --plan C:/AI/repair-work/transform-plan.json --request C:/AI/repair-work/transform-request.json --request-sha256 ACTUAL_REQUEST_FILE_SHA256 --bundle scaled-context --out scope-review-001
python scripts/repair_scope_review.py verify --workspace C:/AI/repair-work --plan C:/AI/repair-work/transform-plan.json --request C:/AI/repair-work/transform-request.json --request-sha256 ACTUAL_REQUEST_FILE_SHA256 --bundle scaled-context --review scope-review-001
```

`--request-sha256` is the existing CLI pin of the **raw request file**. The
returned `request_sha256` identifies the canonical request object, as in the
transform packet; these two digests need not equal. Output paths are new,
workspace-relative directories. All successful output is JSON. Validation/IO
errors use exit 2; malformed CLI syntax uses argparse's normal exit-2 usage.

The HTML is a local static document with embedded PNGs, no JavaScript, no remote
fonts/assets and a restrictive content-security policy. It is not integrated
into the running Studio shell and is not an accessibility certification of that
shell. The views are explicitly **not colour managed**. Supported source colour
metadata remains in the copied context; diagnostics do not certify that colour.

The top-level `expected_effective_write_sha256` identifies the exact effective
source mask shown by the review. After a separate explicit review decision, a
caller can use that value with the existing transform Apply command. The viewer
does not make that decision, automatically apply a result, or change the mask.

## Separate mask carrier: prevent alpha polarity mistakes

The export is `comfy-mask.png`, an RGBA image whose RGB channels are zero and
whose alpha is `255 - work_write`. It is **not a cutout, the context image or a
final write mask**. Its native contract is
`comfy.LoadImage.MASK-inverse-alpha/v1`.

For a compatible registered Comfy workflow, load `context.png` for IMAGE context
and load `comfy-mask.png` separately for the latter node's **MASK output only**.
Never use the carrier's black IMAGE output as the source, and do not invert the
MASK a second time. The context's transparency is not sampling permission.
Working padding is opaque in the mask carrier (zero sampled edit coverage), even
when padding is transparent in the context.

The official Comfy documentation defines LoadImage's MASK output as normalized,
inverted alpha. Tests roundtrip all 256 coverage values through an actual PNG
and independently invert decoded alpha. That proves the byte representation and
documented polarity, **not execution of an installed Comfy node**, floating-point
bitwise equivalence, or compatibility of every downstream inpaint node.

The export preserves soft coverage. It refuses RGBA-as-coverage inputs, metadata
on L masks, inconsistent shapes, fractional protection or overlap with protection.
It does not shrink scope or erase a protection conflict to make an export pass.
A model that changes the whole context still needs the existing protected final
compositor. Its own mask consumer, reference slots, canvas registration and
model/runtime configuration must be qualified under #248 before generation.

Primary contract checked 14 September 2026:
https://docs.comfy.org/custom-nodes/backend/images_and_masks

Pillow resize behaviour and the available filters:
https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize

## One bundle verifier, independent evidence states

`repair_pixel_transforms.verify_prepared` is the extracted read-only bundle
verification seam from the existing Apply function. Apply still requires its
caller's effective-mask pin and retains its current result format. Review and
Apply now reconstruct through the same preparation, source/reference, mask,
geometry and exact-artifact checks rather than maintaining a second verifier.

The verifier returns the already captured bytes and decoded source inputs.
The review never reopens a verified prepared file to produce its views. A file
changed after capture therefore cannot leak different pixels into that review;
a later verification rechecks the live dependencies and fails if they changed.

The review receipt records request/plan/source/bundle/mask identities, renderer
version, geometry, exact support/coverage counts and every output file's hash and
byte size. `verify_review` reconstructs all output from the **external** plan,
request and prepared bundle, checks the exact member inventory and enforces the
existing aggregate byte bounds. An edited carrier or receipt cannot be accepted
by just rehashing it. Unknown files, symlinks and existing output directories are
refused; nothing is automatically removed to make a failed packet pass.

This inherits the cooperative single-user filesystem assumptions of the existing
source/transform tools, not a hostile-filesystem lease or universal power-loss
guarantee. A rendering/Pillow change can invalidate an old exact review packet;
retain it and explicitly create a new one instead of rewriting its evidence.
The review state remains `unreviewed`, with `semantic_approval:false`,
`neural_inference:false` and `model_compatibility:not_qualified` even after a
mechanically successful verification.

## Verification and remaining work

Pure-mask/view tests exercise real Pillow buffers, all 256 inverse-alpha values,
noninteger coverage, expansion/contraction, exact full-resolution counts,
transparent context, protected padding, immutable inputs and escaped offline HTML.
They were first run against missing implementations and failed, then passed after
implementation. Full repository tests additionally exercise the real character
plan/demo, source capture, transformed packets, stale and rehashed artifacts,
CLI subprocesses, read-only reconstruction, original-source preservation and
legacy Apply regression coverage.

The development container cannot resolve GitHub DNS for a clone. Pure tests run
locally; full fixture integration requires the hosted checkout. Do not count
local environment skips as successful integration. Exact final-head CI results
and any review corrections are recorded in the PR, not asserted in advance here.

#245 remains open: native mask-consumer execution/registration, actual candidate
alignment checks, owner-reviewed real repairs and later scope editing need more
work. #251 owns the in-Studio interactive mask editor and shared user/agent
commands; this static review is a directly usable intermediate, not that UI.
No extra generation credit, source-art publication or HUMAN_TODO decision is
introduced by this implementation.

## Display review and reproducible browser probe

The viewer puts four plain-language pixel counts above the comparison views,
uses side-by-side source/change views on wide screens, and keeps raw technical
records in a collapsed disclosure. The exact effective-mask digest is a labelled
read-only field that can be selected without introducing an Apply button or
JavaScript. Mask handoff instructions remain available in a separate disclosure.
This renderer is `scope-diagnostic/v2`; older generated reviews stay intact but
need an explicit new rendering to match the current exact review contract.

Two presentation regressions were written first and failed before adding the
visible counts, collapsed evidence and escaped read-only digest. The local
scope suite then ran 34 cases: 20 passed, 14 full-repository cases skipped in the
partial checkout. Hosted results must establish those integration cases.

An optional reproducible probe uses the same pure synthetic image/mask fixture:

```console
python tests/check_repair_scope_browser.py --browser PATH_TO_EXISTING_CHROMIUM --out experiments/runs/scope-browser-001
```

It requires the optional Playwright package and an already installed Chromium
binary; it installs nothing. The isolated development container additionally
requires `--no-sandbox`; do not use that flag for ordinary workstation browsing.
The probe supplies authored HTML through `set_content`, blocks outgoing network
requests and records screenshots plus JSON results. It checks all three images,
all four statistics, a read-only digest, keyboard disclosure, no horizontal
overflow and no external requests at 1280px and 390px. It is not automatically
added to the normal suite or represented as Studio-origin/native integration.

The probe passed locally in Chromium 144.0.7559.96 and both screenshots were
inspected. Initial file-URL navigation was blocked by the container browser
policy; no policy was changed. The successful evidence is rendered-content and
keyboard behaviour, not successful local-file navigation, actual 200% browser
zoom, full accessibility certification, model execution or artwork acceptance.
