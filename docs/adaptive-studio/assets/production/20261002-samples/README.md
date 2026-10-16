**Published source bundles:** [GitHub delivery](https://github.com/Chris0Jeky/local-asset-studio/pull/1269#issuecomment-5951723697). All three archives were downloaded back and matched original bytes and SHA-256.

# Six controlled illustrative sample sets

Selected for source-sample delivery by dot under owner-delegated art judgment on 2026-10-02. This is an art selection, not source/license clearance, runtime qualification, release selection, or evidence of measured model capability.

## Contents

- `sample-character-canon`: accepted portrait, new olive-outfit full-body RGBA original, and black silhouette copied from its exact alpha
- `sample-pose-pair`: full-body identity and separate jointed mannequin; no pose-transfer output
- `sample-outfit-study`: olive outfit and blue-jacket alternate, with genuine alpha preserved
- `sample-lighting-pair`: upper-left and upper-right lighting, approximately consistent scene geometry
- `sample-composition-pair`: selected source and a pixel-exact 1024×1024 close crop at `[170,125,1194,1149)`
- `sample-sequence-strip`: unaltered 1254×1254 sheet plus four 621×621 extracted frames

`sample-repair-pair` is explicitly excluded. Its deferred repair-route evidence is still required.

## Evidence and reusable files

[ROLE-MANIFEST.json](ROLE-MANIFEST.json) maps independent source files, thumbnails, labels and example-only captions for all six IDs. [FILE-INVENTORY.json](FILE-INVENTORY.json) hashes every attachment-only image. [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) records the six earlier reference inputs. [GENERATION-PROVENANCE.json](GENERATION-PROVENANCE.json) and [generation-prompts.json](generation-prompts.json) preserve exact prompts and confirmed input files for four generation calls. Output handles are local tool handles, not provider job IDs. Model build, seed, provider job ID and generation time remain unknown.

[DERIVATIVES.json](DERIVATIVES.json) gives exact crops, alpha operation, sizes, hashes and thumbnail encoding settings. [REVIEW-COMPOSITES.json](REVIEW-COMPOSITES.json) records checkerboard/contact-sheet assembly separately from reusable source components. [QA.md](QA.md) records observed limitations. Six receipts live in `../../receipts/sample-*--20261002.json`.

There are 4 generated originals, 6 unaltered earlier references, 6 deterministic components, 16 separate WebP thumbnails, 6 per-sample contact sheets, 1 overview and 2 alpha QA sheets. All thumbnails are at most 320px on the long edge and at most 60 KiB; sources retain their actual dimensions. No derivative upscales pixels.

## Delivery path rules

All `originals/`, `inputs/`, `components/`, `thumbnails/`, `contact-sheets/` and `qa/` paths are relative to the root obtained by extracting every delivery ZIP together. They are binary PR attachments only, not repository paths and not runtime asset URLs. Text under `docs/adaptive-studio/assets/production/20261002-samples/` and `docs/adaptive-studio/assets/receipts/` is repo-ready. Never commit the image or ZIP payloads as part of this text-only evidence change.

`ARCHIVE-SHA256SUMS.txt` is the archive payload hash list. `DELIVERY.json` lists final bounded ZIP sizes, hashes and membership. These two repository delivery records are created after archive freezing; the frozen archive includes its own `SHA256SUMS.txt` instead.

## Recheck

Run `python docs/adaptive-studio/assets/production/20261002-samples/validate_samples.py /path/to/extracted/bundle` with Python, Pillow and NumPy. This is an offline mechanical check, not heavy application CI. Exact crop pixels, exact silhouette alpha, input/output hashes, actual dimensions, thumbnail sizes, prompts, roles and unchanged source/runtime/release gates are checked.

`build_samples.py` is the editable record of this local production operation; its initial paths use the named sibling source-pack layout documented by SOURCE-MANIFEST. To rebuild in a different workspace, supply those inputs at the same paths or adapt the explicit path map. Its operations do not generate or retouch images.

## Gates

Art: selected as illustrative source sets. Source/license review: not reviewed. Rendition: offline technical checks only; the separate rendition acceptance gate is not changed. Runtime: not qualified. Release: not selected. No application route, provider/model compatibility, device performance, or actual temporal/identity consistency measurement is claimed.
