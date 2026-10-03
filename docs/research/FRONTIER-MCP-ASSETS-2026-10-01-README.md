# Frontier MCP asset creation — 2026-10-01

**Owner lane:** Civitai Scavenger / Chris (Chris0Jeky)  
**Date:** Thu 2026-10-01 ~00:30 BST  
**Repo focus:** [Chris0Jeky/local-asset-studio](https://github.com/Chris0Jeky/local-asset-studio)  
**Hard rules:** research only · no merges · no weight downloads · no secrets · adults 18+ quarantine if NSFW mentioned · prefer docs/ADR over code PRs

## Scope

What can realistically land in LAS (esp. Create / Asset Foundry / Shot Lab / Uncensored) when bots call **frontier models through MCP/connectors** — not only local Comfy on the RX 9070 XT 16GB.

Pipelines covered:

1. High-quality stills  
2. Consistent characters  
3. Animation / video  
4. 3D mesh / texture / rig that can look good

## Pack index

| File | Role |
|---|---|
| [LANDSCAPE.md](./LANDSCAPE.md) | Connected vs installable MCP inventory + capability matrix |
| [PIPELINES.md](./PIPELINES.md) | End-to-end recipes (bot → MCP → artifact → LAS) + quality bar |
| [LAS_MAP.md](./LAS_MAP.md) | Plug points into Create / Uncensored / docs; Civitai vs frontier lanes |
| [RANKED.md](./RANKED.md) | Ranked next actions A–D (docs preferred) |
| [GAPS.md](./GAPS.md) | Blockers (no MCP, auth, cost, quality) |
| [COMPRESSED.md](./COMPRESSED.md) | One-screen spoken TLDR |
| [SOURCES.md](./SOURCES.md) | URLs, plugin/server ids, timestamps |
| [ISSUES.md](./ISSUES.md) | Comments posted + draft PR URL |
| [EXPLICIT.md](./EXPLICIT.md) | Quarantine notes (adults 18+ / Uncensored only) |

## Prior packs (do not duplicate)

- `/workspace/handoffs/civitai-scavenge-2026-09-30/` — local Civitai Create try-queue  
- `/workspace/handoffs/las-image-models-wave-2026-09-24/` — QI-2.1 / Pruna / AMD  
- `/workspace/handoffs/nsfw-north-star-2026-09-27/` — Uncensored craft (#1176)  
- `/workspace/handoffs/ming-image-design-2026-09-27/` — Ming Design local VRAM story  

Existing LAS docs this extends (not replaces): `docs/FRONTIER-RESEARCH.md`, `docs/FRONTIER-ARCHITECTURE.md`, `docs/AGENT-TOOLING.md`, `docs/character-consistency/*`.

## Success criteria

- Pack written under this path  
- Docs draft PR (or justified skip) — **do not merge**  
- Comments on best-fit open issues (prefer #17/#15/#25/#1176/#1259 over Spoken Briefs #635/#640)  
- Honest quality verdict: what looks good via MCP today vs still local-Comfy-only  
