# Wave 2 delivery

**Current art decision, 2 October 2026:** [The selection record](../20261002-art-selection/README.md) supersedes earlier pending-owner wording for the selected candidates. The two prior anchor approvals remain direct-owner decisions; new choices are accepted under owner-delegated assistant art judgment. Alternatives stay unselected. Source/license, runtime and release gates are unchanged. Historical QA findings and frozen attachment archives are preserved.

Five generated candidates for four asset IDs, original PNGs preserved byte-for-byte, with review-only WebP renditions.

## Paths and scopes

- `inbox/`: unaltered new originals in the delivery archive
- `review-renditions/`: WebP renditions in the delivery archive, not runtime assets
- `review/contact-sheet.jpg`: labeled review contact sheet in the delivery archive
- `docs/adaptive-studio/assets/receipts/`: repository-ready JSON receipts
- `docs/adaptive-studio/assets/production/20261002-wave2/`: repository-ready prompts, provenance, review and manifest
- `SHA256SUMS.txt`: all archive payload hashes except the checksum file itself

Binary paths are relative to the extracted delivery archive, not claims that binary files have been committed. Text paths are relative to the repository root. Input anchor PNGs were hash-verified against prior receipts and are not duplicated in this wave. Extract to a new directory. Never overwrite a different existing candidate.

## Review rendition transformation

Pillow 12.3.0 and libwebp 1.6.0; Lanczos downscale, WebP quality 85, method 6. No crop, no upscale, no metadata copied. Workflows are 600x450 and at most 100 KiB each; outfit is 213x320 (320px long edge, nearest integer aspect ratio) and at most 50 KiB. Originals remain unchanged.

## Release gates

Source provenance is recorded; source terms/license clearance has not been independently determined. Visual QA and rendition validation do not imply owner acceptance. Combine 1, pose 1, recover 2 and outfit 1 are now art-accepted under owner delegation; recover 1 remains unselected. The contact sheet features combine 1, pose 1, recover 2 and outfit 1. Recover 1 is preserved with a direction-of-motion caveat; recover 2 resolves that caveat and is selected for art. No runtime integration or release selection has happened.

The two prior anchor approvals are recorded separately in input-anchors.json. Prompt strings are exact; output handles are local tool handles, not provider job identifiers. Model, seed and provider generation timestamps are unknown.

## Published source bundle

- [Wave 2 source and preview](https://github.com/Chris0Jeky/local-asset-studio/pull/1269#issuecomment-5949668105)
- [ZIP](https://github.com/user-attachments/files/32953915/las-art-wave2-candidates.zip), 7,747,063 bytes, SHA-256 `5cd6d696b3d59907a6458ea02d134fb2f4771d3aeaad0a56d5a1643e8610ac48`
- Downloaded back from GitHub and hash/byte-checked on 2026-10-02 at 09:55 UTC
