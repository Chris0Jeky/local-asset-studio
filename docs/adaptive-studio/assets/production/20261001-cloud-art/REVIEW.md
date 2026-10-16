# Local Asset Studio: generated candidate review

**Current art decision, 2 October 2026:** [The selection record](../20261002-art-selection/README.md) supersedes earlier pending-owner wording for the selected candidates. The two prior anchor approvals remain direct-owner decisions; new choices are accepted under owner-delegated assistant art judgment. Alternatives stay unselected. Source/license, runtime and release gates are unchanged. Historical QA findings and frozen attachment archives are preserved.

Prepared locally on 2026-10-02 UTC. This package contains 14 unaltered generated PNG candidates for seven asset IDs, 14 provenance receipts, eight small WebP review renditions, and a contact sheet. At original package preparation no artwork was accepted, runtime-qualified, or selected for release; the later art decisions are recorded above. Catalog and profile files were not changed.

## Repository placement and attachment base

This is the repository-placement copy of the frozen delivery review notes. The source is [PR 1269](https://github.com/Chris0Jeky/local-asset-studio/pull/1269), with the [anchor preview](https://github.com/Chris0Jeky/local-asset-studio/pull/1269#issuecomment-5943033183) already posted. The complete delivery links are recorded in the adjacent README and DELIVERY.json; the frozen archive contents are unchanged.

Metadata lives at `docs/adaptive-studio/assets/production/20261001-cloud-art/`, and receipts live at `docs/adaptive-studio/assets/receipts/`. In this document, contact-sheet, original-image and WebP paths refer to the root of the extracted delivery archives, not tracked files beside this document. Receipt prompt paths are assets-root-relative and point to the metadata directory. Exact prompt text and prompt hashes are unchanged.

## Start here

Open `review-contact-sheet.jpg`, then compare any full PNG in `inbox/`. The contact sheet is a labeled, padded review montage. Its composition slot shows candidate 2 for clearer thumbnail-scale readability; the latest candidate 3 and its WebP are also included.

Originally suggested candidates; this seven-candidate set is now art-selected:

- `workflow-create` candidate 3: the blank standing frame, star and single cyan folio retain a calm caption area
- `reference-identity` candidate 3: anime-rendered adult explorer with teal hair, silver streak and olive jacket; character anchor directly accepted by the owner at 09:27 UTC on 2 October 2026
- `reference-pose` candidate 1: readable asymmetrical mannequin with visible hands and feet; crossed-leg geometry is approximate, and this is not a skeleton-accuracy claim
- `reference-style` candidate 1: detailed ink hillside street study with linework, wires, bridge and tower; more elaborate than a simple street-corner study
- `reference-composition` candidate 2: larger, clearly separated masses read more strongly at 320px; horizon is approximately 39% from the top. Candidate 3 moves it to approximately 27% and reduces apparent mass sizes. Neither is exactly one-third. Both refinement rounds are exhausted; no exact compliance is claimed
- `reference-lighting` candidate 2: clearer hard-edged cast shadow from upper-left light; the neutral plaster face remains a generated study, with no independent originality or identity audit
- `reference-background` candidate 1: empty platform with usable foreground; main perspective lines enter from the lower right rather than the requested lower left

These preparation observations remain unchanged. The owner subsequently accepted the two anchors directly; five further choices were accepted under the later delegated art selection. No new owner art-choice round is pending for these seven selections.

## Provenance

The provider is recorded as `OpenAI image_gen.imagegen (dot-run)`. `generation-prompts-complete.json` preserves all 14 exact prompt strings, and `output-map.json` maps each candidate to its prompt and local tool output handle. These handles are not represented as provider job IDs.

Every receipt was created with the existing `intake.py` `receipt_for` helper, then completed with the exact prompt string and its SHA-256, measured original bytes/dimensions/hash, and actual input-original hash for edits. Prompts are hashed as their exact UTF-8 text with no added newline. Originals use their eventual ignored `inbox/<filename>` paths. Every file entry is a real file.

The generation session was observed between 2026-10-01 23:38 UTC and 2026-10-02 00:00 UTC; precise provider production timestamps were not exposed and remain null. Reported model build, seed, provider job ID and uncaptured source/terms evidence remain unknown. A route label does not verify a model identity or license. No image was generated from an owner-accepted anchor in this batch.

## Technical review rendition checks

- Workflow candidate 3: 600×450 WebP, under 100 KiB
- All six latest reference candidates: long edge 320px WebP, under 50 KiB each
- Additional composition candidate 2: 320×320 WebP for comparison, under 50 KiB
- Portraits use 213×320 pixels due to nearest-integer rounding
- Pillow Lanczos downscale and WebP quality 85/method 6; no crop, upscale or content edit
- Original PNGs are untouched; no EXIF or ICC metadata is copied to review WebPs
- `rendition-manifest.json` records dimensions, byte counts, hashes, contact-sheet choices and its montage treatment
- Technical checks are recorded separately from `art_review`; frozen archive receipts retain the original review state, while current repository receipts record the subsequent art acceptance

These are review derivatives, not runtime artifacts. Runtime/device checks have not been performed, and release selection remains `not-selected`.

## Delivery and repository handling

Extract all ZIP parts into the same empty directory; each is a standalone ZIP smaller than 10 MiB. Metadata, receipts, small review renditions and the contact sheet are in part 1; original PNGs span parts. `SHA256SUMS.txt` inside the ZIPs covers every archive payload file other than itself. Its repository copy is named `ARCHIVE-SHA256SUMS.txt`; those hashes apply only to extracted archive files, including the frozen original receipts, not the path-adjusted repository receipts. Verify after extracting all parts with `sha256sum -c SHA256SUMS.txt`.

The PNG files and ZIP archives are delivery attachments for the PR discussion, not tracked source files. In the repository, originals belong only in the ignored `docs/adaptive-studio/assets/inbox/` location. Receipt and review-document paths are relative to that assets directory. Do not commit originals, ZIPs, or treat review WebPs as selected runtime files. This text-only repository publication does not publish the image binaries or select them for release. Binary upload status is reported separately in the PR discussion.
