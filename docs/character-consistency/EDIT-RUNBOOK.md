# Run the controlled-edit proof

From the repository root, with the existing Python/Pillow environment. No new model, native plugin, paid service or neural inference is needed for these steps. Read [architecture](EDITING.md) and [tool policies](TOOL-POLICIES.md) first. This extension imports the existing `scripts/character_study.py` contracts from the character foundation.

## 1. Discover and run a deterministic example

```console
python scripts/character_edit.py describe
python scripts/character_edit.py policies
python scripts/character_edit_demo.py --out experiments/runs/edit-proof-001
```

Choose a new output directory each time. The demo authors two simple block-shaped figures and a left-figure torso mask. It deliberately supplies a solid-colour candidate that would overwrite the *whole context crop* if applied naively. The actual result only changes the permitted torso pixels and preserves the second figure and background.

Inspect `comparison.png`, `revision-2/result.png`, `revision-2/changed-pixels.png` and `revision-2/result.json`. Expected at the authored 384x256 canvas: **4,032 changed pixels; 94,272 exactly preserved pixels; zero changes outside the edit mask or inside the protection mask**. This is a mechanical compositing proof, not a neural costume edit or a success-rate benchmark.

The example retains `document.json`, `intent.json`, `plan.json`, original source, per-actor reference/canon fixture files, both masks, padded input bundle and candidate. None is automatically marked accepted.

## 2. Recompile the example without changing it

```console
python scripts/character_edit.py plan --document experiments/runs/edit-proof-001/document.json --intent experiments/runs/edit-proof-001/intent.json --out experiments/runs/edit-proof-001/plan-copy.json
python scripts/character_edit_pixels.py prepare --workspace experiments/runs/edit-proof-001 --plan experiments/runs/edit-proof-001/plan-copy.json --out prepared-copy
```

The plan includes source/document identity, actor-bound references, route exclusions/caveats, proposed stages and budget owner. It contains no armed ComfyUI submission payload. An eligible route is not proof of installation or native input compatibility.

For real artwork, replace the example's synthetic design and source with your reviewed documents, update the actual SHA-256 values, and create a fresh intent against `sha(document)` using the existing canonical JSON helper. Do not reuse approval from an altered canon or hand-edit the derived plan. `prepare` rechecks the actual source, canon, reference and mask bytes; a stale hash fails before new output publication.

## 3. Understand the masks and coordinate contract

The edit mask is a full-canvas **grayscale L PNG**: 0 retains source, 255 accepts candidate, intermediate values blend. The optional protection mask is a full-canvas **binary L PNG**: 255 forbids changes. These conventions differ intentionally. Overlap between editable support and protection is rejected, not silently subtracted.

Non-target actor bounds are conservative additional protection. A write mask touching another actor requires a better reviewed envelope or an explicit coupled interaction. Neither a model nor an agent can silently expand scope by editing only a derived plan field.

`context_box` is `[x0,y0,x1,y1]` in source pixels, with the last coordinates exclusive. The working crop is padded only at right/bottom to the requested alignment (1/8/16/32); there is no resampling. The recorded `unpadded_size`, `model_size`, `padding_ltrb`, crop coordinates and exact context/mask hashes are in `prepared/bundle.json`.

The small demo's 87x93 context becomes 88x96 at alignment 8. That demonstrates coordinate accounting, **not** an appropriate model resolution. For real inference choose a supported native crop size; explicit scale-transform support is future work. A backend that resizes or normalizes unexpectedly must be handled by a tested adapter, not an unrecorded inverse resize.

A Comfy node that reads mask from inverse alpha needs an explicit conversion step in the future adapter. Passing this grayscale mask as an arbitrary RGBA reference is not equivalent. Existing #62 owns the native nonempty-alpha guard.

## 4. Supply a candidate and apply it

Create the candidate using a compatible model/native editor *outside this CLI*. Preserve the exact recorded padded dimensions and normalize colour/profile explicitly. Keep its original generation recipe and actual prompt ID in the existing Studio evidence system.

Get its SHA-256, for example:

```console
python -c "from pathlib import Path; from scripts.character_study import file_sha; print(file_sha(Path('experiments/runs/edit-proof-001/candidate.png')))"
```

Then use the printed value in place of `ACTUAL_SHA256`:

```console
python scripts/character_edit_pixels.py apply --workspace experiments/runs/edit-proof-001 --plan experiments/runs/edit-proof-001/plan.json --bundle prepared --candidate candidate.png --candidate-sha256 ACTUAL_SHA256 --out applied-copy
```

The command validates bundle integrity **and recomputes its expected pixels** against the source; rehashing an altered bundle does not make it valid. It verifies candidate bytes, size, mode and ICC profile, composites through the original mask and proves decoded RGBA preservation outside the allowed area. A no-op result remains unreviewed and receives a warning rather than art approval.

Pillow blending here is encoded-space blending, not full linear-light colour management. EXIF-bearing and animated PNG inputs must be normalized through a separate explicit intake route. Matching profile bytes do not prove the candidate was rendered in the intended colour space. The operating model is one trusted local writer, not a hostile multi-user filesystem sandbox.

## 5. Costumes and scenarios

For a costume change, keep identity references under their actor and add the new costume reference as `role: costume`; do not relabel it as a pose to satisfy a backend slot. Propose a costume revision and an appropriate old/new garment mask before generation.

For `scenario` and `interaction`, `layout` must contain each target actor exactly once, desired bounds, optional pose artifact, a complete back-to-front actor order, and contact regions. Interaction requires at least two participants and a declared contact relation. A scene with two sequential actor passes cannot claim a one-candidate budget. Background generation and later repairs consume the same owner allowance; the current CLI validates declarations, not live consumption.

No native graph is synthesized from these fields in this first slice. Unsupported actor/reference counts or spatial controls stay unresolved. The coordinator integration must project them explicitly and demonstrate that it does not discard the distinctions.

## Checks

```console
python -m unittest discover -s tests -p "test_character_edit*.py" -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The dedicated tests cover exact pixel retention, candidate/bundle tamper, stale source and actor references, mask modes/polarity/coverage, ICC/dimension changes, non-target actors, source/output path policy, typed plan rejection, policy unknowns, budgets and transitive invalidation. The native preset presence test uses the real catalog in repository CI. None of these tests claims to measure neural anatomy or artistic quality.

## Next native handoff

An agent can use the current JSON CLI as its allowlisted file-based tool immediately. Connecting it to a live Krita canvas and the Studio UI is a separate slice in #71 under #23/#65: shared revisions, real source snapshots, native layer import, explicit Generate, transactional reservation and uncertain-job recovery. Critique calibration remains #66. Preserve `HUMAN_TODO.md`; no test or hash closes a human creative decision.
