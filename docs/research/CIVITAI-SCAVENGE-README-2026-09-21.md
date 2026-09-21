# Civitai scavenge — 2026-09-21

Public pages only. **No weights downloaded.** Box: RX 9070 XT 16GB, Comfy, LAS.

## Read this first

- **`FINDINGS.md`** — merged pack. Catalog (Illustrious/WAI, NoobAI, Pony, Animagine, RealVis, FLUX.2 Klein, Krea2, Xinsir/OpenPose, IP-Adapter, LoRA combos) plus an appendix on **Qwen-Image-2.1** (GGUF/INT4, samplers, what to strip on AMD).
- **`FINDINGS.FULL.md`** — catalog before the 2.1 appendix (same tables).
- **`LINKS.md`** — URL index from the 2.1 / workflow pass.
- **`SOURCES.md`** — API queries and `raw/` snapshots.
- **`ISSUES.md`** — already seeded on the LAS repo. Do not file a second set.
- **`COMPRESSED.md`** — spoken TLDR of the catalog pass.

## Counts

| | |
|---|---|
| Catalog unique page URLs (FULL) | ~95 |
| 2.1 appendix rows | 5 (ids 579280, 2951890, 2952100, 2952547, 2951557) |
| Creators called out | 15 |
| Weight files downloaded | 0 |
| civitai.red | Same product in the browser; catalog scrape also saved red HTML/API. `curl` to the host was 403. |

## AMD notes that should survive into the docs PR

- 2.1 workflows advertising **SageAttention, Triton-CUDA, DLSS5, RTX VSR** are NVIDIA. Keep the graph, drop those nodes.
- 16GB path for 2.1 is **GGUF Q4_K_M/Q5 or INT4 W4A8**, not BF16 and not 19 GB fp8 of the older Qwen-Image.
- Do not reuse **2511 Lightning / angles / try-on LoRAs** on 2.1 until tested.
- WAI normal sample (Euler a, CFG 5–7) and WAI **4-step** LoRA (Simple, CFG 1–1.5, A2/A3 on v14+) are different presets.
- Pony Union graph says OpenPose preprocessor fails on Pony. Match ControlNet to base (Xinsir vs Illustrious `1359846` vs Noob `962537`).

## Issues already open

See `ISSUES.md`: PR **#756**, smoke issues **#757–#764** (WAI LoRAs, NoobAI, Pony, Qwen 2511 vs 2.1, Xinsir, Krea2, FLUX Klein/dev GGUF, `*.part` cleanup).
