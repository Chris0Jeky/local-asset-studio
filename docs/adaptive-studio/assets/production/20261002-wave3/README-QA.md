# Wave 3 delivery and QA

**Current art decision, 2 October 2026:** [The selection record](../20261002-art-selection/README.md) supersedes earlier pending-owner wording for the selected candidates. The two prior anchor approvals remain direct-owner decisions; new choices are accepted under owner-delegated assistant art judgment. Alternatives stay unselected. Source/license, runtime and release gates are unchanged. Historical QA findings and frozen attachment archives are preserved.

Fifteen generated candidates for twelve catalog workflow IDs. Original PNGs are preserved byte-for-byte. Three original candidates are retained alongside reviewed refinements. Twelve candidates are now art-accepted under owner delegation; three alternatives remain unselected. None is runtime qualified or selected for release.

## Review

Use `review/contact-sheet-1.jpg`, `-2.jpg`, and `-3.jpg` for the recommended set. Each tile pastes its exact 600x450 review rendition without another resize. `review/contact-sheet-alternatives.jpg` shows the three superseded originals. Read `REVIEW.md` and `visual-qa.json` for honest caveats. Contact sheet labels are review presentation only, never baked into asset pixels.

## Paths

- `inbox/`: unmodified generated PNG originals, attachment only
- `review-renditions/`: 600x450 WebP review files, attachment only
- `review/`: contact sheets, attachment only
- `docs/adaptive-studio/assets/receipts/`: ordinary JSON receipt source
- `docs/adaptive-studio/assets/production/20261002-wave3/`: ordinary text prompts, mappings, provenance and QA
- `SHA256SUMS.txt`: hashes of every payload file in that ZIP except itself
- `PART-README.txt`: exact part contents and extraction guidance

Binary paths are relative to the named extracted ZIP part. Text paths are repository-relative. Three ordinary independent ZIP files are each below 10 MiB; they are not spanned ZIP fragments. Each part includes its own originals, previews and receipts, plus common review/provenance text and contact sheets. Candidate-1 inputs accompany their refinements in the same part. Each part can be inspected independently. Extract each into a separate new folder; common text/contact files are intentionally repeated and identical. Prior accepted anchor files refer to the earlier delivery and are not duplicated.

## Exact source records

`generation-prompts-initial.json` and `output-map-initial.json` preserve the supplied initial records. `generation-prompts.json` and `output-map.json` add the three refinement records. Each `*-refinement.json` retains the exact supplied edit prompt and inputs. The receipts hash exact UTF-8 prompt strings without an added newline. `input-anchors.json` records accepted anchor hashes, with the owner's approximately 09:27 UTC decision separate from derivative review. `catalog-checks.json` pins the twelve original acceptance constraints at repository commit 6645f7d61b2bfdbca4853ea92b5fde6d6b0c8164.

## Renditions

Pillow 12.3.0, libwebp 1.6.0; RGB conversion, Lanczos downscale from 1448x1086 to 600x450, WebP quality 85/method 6. Exact 4:3, no crop or upscale, no EXIF/ICC copied. Every WebP is at most 100 KiB. These are review renditions, not integrated runtime assets. Generated refinement edits are not pixel-preserving transformations. Originals remain untouched.

## Boundaries

The producer is OpenAI image_gen.imagegen (dot-run), not an owner-operated model session. Output IDs are local tool output handles. Provider model, seed, provider job ID and provider generation timestamps are unknown. Independent terms/license clearance remains unresolved. Art acceptance is recorded for the twelve delegated selections. Runtime qualification and release selection remain separate pending gates. No GitHub mutation, browser operation, application integration or heavy CI occurred in this preparation.
