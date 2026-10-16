# Combined pictogram qualification: budget diagnosis

Date: 2026-10-13. This is the durable LAS copy of Alibi qualification evidence. The canonical Alibi checkout remains clean at `ff32dc41066739796084264f181297958b3fdae7` on `codex/club-art-icons-qualified-20261012`; the clean build reports `sourceDirty: false`. No continuation probe was retained or committed; the existing ff32 checkpoint is preserved.

## Canonical baseline and caps

- Full build `ad31c6f47f0c`: shell `1,412,565` bytes against unchanged `1,412,792` (227 bytes headroom); startup code/content gzip `205,531` against unchanged `205,248` (283 bytes over); JavaScript gzip `133,345`.
- Official content: `483,634` bytes, `61,946` gzip; deferred content gzip `8,650`.
- The frozen icon-fragment baseline contains 56 outputs; existing receipt `frozen-56-fragments.json` has SHA-256 `35c4005821e55d239137d5f4bcb1c27428c612db22029276adbb41f80e6ad224`.
- No budget limits, decoder, runtime behavior, artwork contours, or source were changed.

## Exact-preserving probes

**Icon table compaction.** The unchanged presentation source measured 29,928 raw / 24,320 minified / 9,536 gzip. A shared static shape-markup helper measured 28,968 / 23,136 / 9,574; despite smaller raw/minified source, gzip grew 38 bytes. Its full build measured shell 1,412,564 and startup gzip 205,530, leaving startup 282 over cap. The second-round path-token table variants (2, 4, 6, 7 tokens) measured respectively 29,389 / 23,060 / 9,667; 29,388 / 23,059 / 9,675; 29,326 / 22,997 / 9,683; and 29,289 / 22,960 / 9,696. All increased gzip and were discarded. The 56 frozen SVG fragments remained the equality target; no contour or runtime change was kept.

**Fallback URI escaping.** A build-only serializer starting from `encodeURIComponent` and selectively unescaping only `=`, `:`, `/`, `;`, and `,` reduced official content by 160 raw bytes and startup gzip by 22, to 205,509 (261 over cap). Other escaping stayed intact. A validation-only Chromium comparison found old/new fallback renders pixel-identical on phone (390×844) and desktop (1440×1000), and checked markup interpolation safety. The serializer change was not retained.

**Official-data short-string dictionary.** The actual five-global payload had 556 distinct repeated strings shorter than 32 characters (6,329 occurrences) and 143 existing dictionary entries. A positive-raw-savings selection over 406 candidates cut serialized content by 17,186 raw bytes but increased official-content gzip by 1,098 (61,946 → 63,044), so raw savings did not help startup.

A bounded gzip-greedy subset of eight strings—`provisional`, `The Copper Conservatory`, `The Salt Observatory`, `The Winter Post Office`, `The Nocturne Gallery`, `The cleaner`, `Vault Ledgers`, `Vault Chambers`—was then measured in a full emitted build. Startup was 205,454, still 206 over the unchanged cap; official-content gzip was 61,868 (−78) and platform gzip 5,094 (+1). Official-content bytes were 477,070; `coreOfflineBytes - officialContentBytes` remained 1,412,565. The candidate encoder used the existing `[5,index]` wire form; decoder and runtime were unchanged. A validation-only comparison confirmed `JSON.stringify(decodedCandidateGlobals) === JSON.stringify(baselineGlobals)` for all five globals. The subset was discarded because the exact full-build budget still failed.

## Checks and disposition

- Focused pictogram/alias checks: 12 passed (existing checkpoint evidence); codec suite rerun on canonical ff32: `node --test tests/official-data-codec.test.cjs`, 4 passed / 0 failed.
- `git diff --check` passed; temporary validation harnesses were removed. The canonical full build was restored and reproduces build `ad31c6f47f0c`, payload SHA-256 `8aa187d8e35364166748008c1658f2b9a09c419b5929859c4c930efa28f0823f`.
- No full verify or intentionally failing broad gate was run for the blocked candidate. The candidate remains unqualified at the unchanged startup cap; this receipt does not claim physical-device acceptance.
