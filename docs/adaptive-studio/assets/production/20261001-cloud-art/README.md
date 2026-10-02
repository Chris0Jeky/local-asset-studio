# Cloud-generated art candidate evidence, 2026-10-01 session

This directory contains text-only evidence for 14 generated candidates across seven Local Asset Studio asset IDs. It records review preparation and provenance. It does not assemble or qualify a runtime asset pack, accept artwork, or select a release asset.

## Source and delivery

- [PR 1269 discussion](https://github.com/Chris0Jeky/local-asset-studio/pull/1269) is the destination for the original PNG and ZIP attachments
- [Anchor preview comment](https://github.com/Chris0Jeky/local-asset-studio/pull/1269#issuecomment-5943033183) is already available
- [Verified source delivery and contact sheet](https://github.com/Chris0Jeky/local-asset-studio/pull/1269#issuecomment-5943078591) are published in the PR discussion
- Download [part 1](https://github.com/user-attachments/files/32938292/las-art-candidates-part-01-of-03.zip), [part 2](https://github.com/user-attachments/files/32938294/las-art-candidates-part-02-of-03.zip), and [part 3](https://github.com/user-attachments/files/32938295/las-art-candidates-part-03-of-03.zip)
- [DELIVERY.json](DELIVERY.json) lists the three frozen ZIP names, exact byte sizes and SHA-256 hashes; every part is below 10 MiB
- All three ZIPs extract into one common directory. Their 42 payload file hashes were verified after extraction. All three archives were downloaded back from their published GitHub links and matched original bytes and SHA-256 values
- [ARCHIVE-SHA256SUMS.txt](ARCHIVE-SHA256SUMS.txt) is an unchanged copy of the archive's `SHA256SUMS.txt`; it verifies archive files only. The repository receipts have path notes added, so their JSON file hashes intentionally differ from their frozen archive counterparts

## Path rules

Receipts are in [`../../receipts/`](../../receipts/). Their prompt records point to `production/20261001-cloud-art/generation-prompts-complete.json`, relative to the repository asset root `docs/adaptive-studio/assets/`.

All `inbox/`, `review-renditions/` and `review-contact-sheet.jpg` paths in delivery manifests and review notes are relative to the root obtained by extracting all three ZIPs together. They are attachment-only binary paths, not promises that image files are tracked next to these text files. Originals may be copied into the repository's ignored `assets/inbox/` directory for local review. ZIPs, original PNGs, review WebPs and the contact sheet must not be added to source by this text-only publication.

## Evidence and pending decisions

- [Exact prompts](generation-prompts-complete.json) and [output mapping](output-map.json) preserve all prompts and local tool output handles; a local tool handle is not a verified provider job ID
- [Review notes](REVIEW.md), [original inventory](inventory.json) and [review rendition manifest](rendition-manifest.json) record checks and remaining deviations
- Eight WebP review renditions passed decode, hash, dimension and byte-budget checks. Workflow3 is 600×450; reference long edges are 320px. No crop or upscale was applied
- Model build, seed, provider timestamps and uncaptured source/terms evidence remain unknown
- Owner art review remains `not-reviewed`; runtime review remains `not-qualified`; release selection remains `not-selected`
- Workflow3 and identity3 are proposed anchors awaiting owner acceptance. Composition2 is the clearer thumbnail comparison; neither composition2 nor composition3 meets the exact one-third horizon target

## CI status

A pre-existing **Adaptive Studio specifications / contracts** failure is recorded in [run 36943971012, job 110641663269](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/36943971012/job/110641663269). Inventory validation passed for 154 entries; `test_brief.py` reported 15 passed and one failed. At line 181, the assertion expects the `CLAUDE.md` wording “48 further” followed by “path-filtered lanes”, while the document contains “46 further”.

The `CLAUDE.md` and test blobs were identical at base `0996cb0fafd85c6f63a7d21543efa870a000b07e` and the observed README-only head `772191dbbe2c930cc6f3c9a169412593eb0dfc9a`. This baseline failure does not identify an art-path failure. A pinned snapshot of all 49 workflow YAMLs confirmed 48 additional path-filtered lanes. This change corrects only the stale count from 46 to 48 in CLAUDE.md. Local red/green verification on Python 3.12.14 reproduced the baseline failure, then passed all 16 brief tests after that one-token correction. Intake tests passed 23/23 independently; inventory validation passed all 154 requests. Final hosted CI remains separate and pending.

The full **Check studio** run was still in progress at the last recorded observation, 2026-10-02 00:05:50 UTC. Other check results were pending; this document is a dated snapshot, not a live CI status.

Local image-file validation is separate from repository CI and from runtime/device qualification. This text-only evidence package is not a claim that the application build or an assembled asset pack passes.
