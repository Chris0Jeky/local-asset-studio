# Comparison review desk

Implementation slice for **#10 (Experiment Lab)** and **#16 (Studio UX)**. It
supports the controlled studies in #3/#14 and evidence requirements in #22.
Built on main `93b1f847b29cc6e5da488eacf297556453e94116`, independently of open
PR #41's backend/install changes and the unmerged Prompt/AV labs. No new queue,
model manager, inference adapter, external service or framework is introduced.
Atelier PR #42 landed during this pass. Its settings-sweep changes are retained
through the PR test merge against current main; this branch does not replace them.

## Use it

In **Experiments**, open a finished image comparison and choose **Open review
desk**. A failed comparison with retained images can also be inspected. The page
is `/review.html?project=<32-character project ID>` on the normal Studio port.
Opening the page reads saved state; **Prepare review** is a separate explicit
CPU/file operation. It snapshots the retained sources, randomizes stable aliases
and writes bounded previews without embedded prompts or filenames.

Compare any two candidates side by side, or toggle left/right in the same area.
Use Whole image, Centre detail, Upper half, or numeric keyboard-accessible crop
edges. The same normalized rectangle is applied to every oriented source. Choose
a light/dark alpha background and save the view. No source image is stretched to
match another's dimensions. Previews are capped at 1536 px; exported crops start
from the original snapshot resolution. Matching coordinates do not align faces,
hands or camera views, and different model seeds do not establish equal compute.

Record each candidate's verdict, observed constraints/identity/pose/composition/
detail, optional preference, cleanup seconds and notes. Blank cleanup is **null**;
zero means a measured zero, not an absent observation. These are reviewer entries,
not automated quality metrics. Switching candidates or display modes preserves
unsaved notes. A stale server revision refuses the edit without clearing the
local draft; download the draft JSON before an explicit reload when needed.

**Reveal settings & provenance** permanently records that the settings were
seen. Finalize only after every candidate has a verdict. Selecting a result also
requires a Keep verdict, passing stated constraints and a completed recorded
execution. Selecting none is valid. Reveal is a local bias-reduction aid, **not
an access-control boundary**: the user can still inspect the plan elsewhere in
Studio, and image content itself may suggest its source.

**Export review evidence** creates a portable ZIP containing every candidate's
original bytes, including rejected results, plus the immutable experiment plan,
recorded recipes/execution failures, review history, matched contact sheet and
checksums. Input references and model weights remain external as recorded in the
plan/recipes; this is not a complete self-contained inference environment.
The export is **not** model-terms clearance, commercial approval or engine
acceptance. Existing HUMAN_TODO choices are unchanged.

Earlier candidate assessments can be restored as a **new revision**. History is
retained, the final decision is cleared, and previously revealed settings cannot
be made unseen. Changing a rating also invalidates the decision; changing only
the shared crop preserves it but requires a new revision-specific export.

## Architecture

| Module | Responsibility |
|---|---|
| `app/review_media.py` | Bounded byte verification/decode, EXIF orientation, metadata-free previews, shared crop math, alpha compositing and deterministic contact-sheet layout |
| `app/review_desk.py` | Snapshot provenance, revisioned commands, assessment/reveal/decision rules, review history, file publication and evidence export |
| `app/production.py` | Existing service integration: command dispatch, artifact routing and transactional legacy-review compatibility |
| `app/static/review.*` | Standalone same-origin review page, retained drafts and guarded async canvas updates |
| `app/static/production.js` | Discoverable entry point; legacy selection controls disappear after the desk is prepared |

Four additive tables live in **the existing `projects.sqlite3`**:
`comparison_reviews`, `comparison_review_events`, `comparison_review_files`,
`comparison_review_exports`. No project plan is rewritten. Opening a desk retains
any earlier simple review as `prior_review`; state.review gets a link to the desk.
Later commands update only the review summary in the current project state row.
Attempts, artifacts and generation reservations remain intact. A failed project
never becomes an execution success because an image was selected.

Commands use `BEGIN IMMEDIATE`, a read of the expected revision and one database
transaction for the document/event/project-summary change. Two callers cannot
both write the same revision. Legacy selection is gated in the same write
transaction so it cannot race a newly opened desk and overwrite its summary.
No global application settings are changed. Hashing/finalization is deliberately
bounded but may briefly hold the project-database writer; this is not a latency
claim for maximum-size workloads.

A canonical SHA-256 fingerprint covers the stored plan, stage attempts, job
identities, exact recipes, output identities and hashes. A changed plan, source
mapping or execution record blocks subsequent mutations rather than silently
binding old reviews to new work. Workspace source bytes and review snapshots are
rechecked before finalizing/exporting. Published files are individually hashed
before serving. SQLite state is authoritative; unpublished intermediate files
never appear in the artifact download route.

CPU preview/export work has a per-Studio nonqueued media lock, no GPU ownership
and no calls to prepare/create_job/_request. Multiple independent processes still
share SQLite publication/revision checks; they can perform redundant bounded
CPU work before one wins publication. This is not a global CPU scheduler.

## API and agent contract

Use the existing same-origin, loopback-protected route:

```text
POST /api/production/<project-id>/review
Content-Type: application/json
Origin: http://127.0.0.1:8191
```

| Action | Additional fields | Effect |
|---|---|---|
| `inspect` | none | Read only; returns exists=false before explicit preparation |
| `open` | optional reviewer | Idempotently prepare one stable review snapshot |
| `rate` | alias, assessment | Replace a candidate assessment and invalidate the final choice |
| `view` | crop, background | Save matched display/export geometry |
| `reveal` | none | Irreversibly reveal settings in this review |
| `finalize` | selected (alias or null), notes | Record the explicit decision after validation |
| `restore` | source_revision | Replay an earlier rate assessment as a new revision |
| `export` | none | Publish evidence for the current finalized revision; repeat returns its existing receipt |

Every action except inspect/open requires integer `expected_revision`. Reviewer
is `local-user` (default) or `local-agent`, a declaration rather than authenticated
identity. Unknown fields/actions are rejected. Existing Handler errors are HTTP
400 with useful text, including `Review conflict`; no new HTTP status convention
or independent server has been introduced.

```json
{
  "action": "rate",
  "expected_revision": 0,
  "alias": "A",
  "reviewer": "local-user",
  "assessment": {
    "verdict": "needs_work",
    "observations": {"constraints": "fail", "identity": "pass"},
    "cleanup_seconds": null,
    "preference": 3,
    "notes": "Costume retained; the hand does not contact the handle."
  }
}
```

Verdicts: unreviewed, keep, needs_work, reject. Observations: constraints, identity,
pose_contact, composition, detail; each pass/fail/not_assessed. Preference is null
or integer 1–5. Cleanup is null or integer seconds 0–86400. Notes are literal text,
never executable instructions. Do not let an agent silently label a human review.
No image generation or repair is triggered by a defect note or rejected result.

Crop uses integer basis points `[left, top, right, bottom]` within 0–10000, with
positive area. Pixel conversion floors the leading edges and ceils the trailing
edges after EXIF orientation. The contact-sheet report stores exact per-source
pixel boxes and rendered dimensions. It also records that transparent pixels
were composited on the selected background. ICC/HDR colour-management is not
implemented: 8-bit review previews strip source metadata; exact originals remain
in the pack. Animated, high-bit-depth, CMYK and unsupported formats are rejected
instead of silently comparing an arbitrary frame or tone mapping.

## Evidence and recovery

```text
projects/<project>/reviews/<random session>/
    sources/A.png, B.jpg, ...       exact original bytes; not exposed while blind
    A.png, B.png, ...               registered metadata-free previews
    export-<random ID>/
        contact-sheet.png
        review.json                immutable review snapshot/history/transform report
        plan.json
        review-evidence.zip        sources + above + checksums.json
```

Only registered previews and export artifacts are served through Production.file.
Paths are scoped to the project, with traversal, linked project directories,
symlinks/junctions and unpublished files rejected. This is not a sandbox against
a privileged process racing local filesystem mutations. The local owner can
read the SQLite database and sources directly.

The ZIP manifest covers every other archive member by SHA-256 and byte count;
it cannot hash itself. External file receipts hash the ZIP and individual exposed
reports. Returned receipt reuse identifies an **earlier immutable export**, not
fresh certification that the workspace still matches it. Failed/missing source
checks do not overwrite snapshots or cause a substitute image to be served.

Caps: 16 retained image candidates; 32 MiB and 16 megapixels per image; 256 MiB
aggregate input; 1 MiB recipe evidence; 256 revision changes; eight published
exports; 1 GiB review-file budget per project plus 1 GiB free output headroom.
File/memory operations are sequential and bounded. This is not a measured peak
RAM guarantee or a real-time rendering system.

Files are created in unique directories without overwrite. If decoding, hashing,
rendering, publication or the final revision check fails, intermediate files may
remain on disk but are not registered or downloadable. Existing work is preserved.
No automatic startup resume or stale-artifact deletion occurs. Inspect failed
review directories, preserve relevant diagnostics and archive them explicitly
before freeing space. Do not erase sources merely because a receipt is absent.
There is no cross-filesystem/SQLite power-loss transaction or universal directory
fsync guarantee; a crash after file creation can leave an unpublished orphan.

Removing this feature should leave the four review tables and directories intact;
old revisions remain readable as evidence. Legacy review selection remains
available on projects that never opened the desk, not as a bypass for one that did.

## Validation and reproducible QA

The local partial checkout ran **49 Python core tests** and the Node-backed
frontend contract test, with Python 3.13.5, Pillow 12.3.0 and Node 22.16.0.
Tests include two-instance stale writes, stable blind order, metadata stripping,
zero/null semantics, snapshots, restart/history restore, plan/recipe/source drift,
constraints, failed-stage selection, byte/pixel/storage caps, EXIF/crop/alpha,
atomic publication visibility and exact archive hashes. Compilation and patch
whitespace checks passed. The six actual-Handler HTTP tests are included for the
full repository/hosted CI; they are not claimed from the partial local checkout.

```console
python -m unittest discover -s tests -p test_review_desk.py -v
python -m unittest discover -s tests -p test_review_frontend.py -v
python -m unittest discover -s tests -p test_review_http.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The unchanged Ubuntu repository workflow runs the full suite and validator.
A path-filtered Windows job runs the 56 focused core/frontend/actual-HTTP tests.
Both use the existing pinned Pillow test environment; no model/runtime package
is changed. Hosted results must be observed on the PR, not inferred from the YAML.

Optional browser QA uses inert procedural PNG fixtures and the actual Production
review service/database; its small HTTP wrapper is explicitly a fixture, not the
production Handler. The local Chromium 144 run exercised the whole workflow,
conflicting agent edits, retained/downloaded drafts, real ZIP download/hash checks,
history restore, keyboard input and 390 px layout with no horizontal overflow,
JavaScript errors, external requests or generation calls. Desktop/mobile screenshots
and decoded contact-sheet pixels were inspected. This is **not art acceptance**.

```console
python -m pip install playwright
python -m playwright install chromium
python tests/review_browser_smoke.py --out experiments/runs/review-browser-qa
```

Local environment limitations are explicit: its overlay filesystem rejected
SQLite fsync, so tests used a temporary directory on `/dev/shm`; no durability
setting was disabled. Its managed browser blocked localhost navigation. The
successful local browser run therefore used `--dispatch-bridge` with
`--chromium /usr/bin/chromium`: Fetch, image decode and download links are bridged
to Python's real fixture HTTP service. Native browser-to-Studio transport remains
covered separately by actual Handler tests/normal workstation acceptance, not
claimed from this bridged run. The test-only bridge never ships in the app page.

## Remaining workstation/issue acceptance

Use a retained original-character comparison to assess actual pose/contact,
identity and cleanup. Verify Main/HiDream review after switching backends, opening
an existing review in two browser tabs, keyboard/screen-reader use and final-size
pixels in the native browser/Windows Studio. Compare original versus refinement
only when both are explicit saved stage outputs; no external image is silently
introduced as a baseline. The current desk handles still images, not synchronized
video/audio, generated semantic alignment or a native painting application.

#10 still needs its full accepted multi-stage production demonstration and any
additional executor work. #16 retains its wider shot/asset/editor UX tasks.
#3/#14 still need real controlled model studies and subjective selection. This PR
adds usable review infrastructure without claiming these broad issues closed.

## Primary implementation references

Reviewed 12 September 2026:

- [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html):
  write transactions and BEGIN IMMEDIATE underpin expected-revision updates.
- [Pillow ImageOps](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html):
  EXIF transpose and aspect-preserving contain behavior.
- [Pillow Image](https://pillow.readthedocs.io/en/stable/reference/Image.html):
  lazy decode, pixel limits, image modes and crop operations.
- [WCAG 2.2 dragging alternatives](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html):
  crop inputs/presets work without a precision drag gesture. This is not a formal
  WCAG conformance audit.
