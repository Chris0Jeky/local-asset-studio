# Civitai scavenge — 2026-09-21

Public pages only. **No weights downloaded.** Box: RX 9070 XT 16GB, Comfy, LAS.

## Read this first

- **`PRESETS.md`** — **1-page SFW copy-paste** positives/negatives + CFG/sampler/steps (WAI / Noob / Pony / Animagine / RealVis). Start here for LAS.
- **`BATCH3.md`** — SFW tag/prompt/wildcard playbook.
- **`BATCH4.md`** — SFW leftovers + RealVis/Animagine depth (no B3 primary dupes).
- **`BATCH3_EXPLICIT.md` / `BATCH4_EXPLICIT.md`** — quarantined NSFW/hentai only (never merge into SFW).
- **`FINDINGS.md`** — merged pack (Batches 1–4).
- **`BATCH2.md`** / **`BATCH2_BROWSER.md`** — Klein / Z-Image / creators / browser verify.
- **`LINKS.md`** / **`LINKS-CHAT.md`** — URL indexes (chat-ready in LINKS-CHAT).
- **`SOURCES.md`** — API queries + `raw/` snapshots.
- **`COMPRESSED.md`** — spoken TLDR.
- **`QUEUE.md`** — batch status.
- **`ISSUES.md`** — already seeded. **Do not file new issues** — Grok updates PR **#756** only.

## Counts (pack)

| | |
|---|---|
| Weight files downloaded | **0** |
| New GitHub issues this scavenge | **0** (PR #756 only) |
| Batch 4 SFW new ids (approx) | ~35 |
| Explicit quarantine files | 2 |

## AMD notes that should survive into the docs PR

- Strip **SageAttention, Triton, DLSS, RTX VSR, Nunchaku/SVDQ** from imported WFs.
- 16GB: prefer FP8/GGUF; don’t stack BF16 everything.
- Pony `score_9*` **only** on Pony — never on WAI/Illu/Animagine/Noob.
- WAI: Euler a, CFG 5–7, rating `general`, neg `nsfw/explicit`.
- Animagine Opt: quality tags **at end**, CFG 5, 28 steps.
- Explicit content stays in `*_EXPLICIT.md` only.
