# LAS_MAP — where frontier MCP plugs into local-asset-studio

## Lane split (keep distinct)

| Lane | Purpose | Sources | Default surface |
|---|---|---|---|
| **Civitai / Create** | Local SFW craft on RX 9070 XT 16GB | Civitai/HF weights · Comfy graphs | Create tab · Workflow Studio |
| **Frontier MCP** | Cloud / connector gen without local GPU | Canva · Figma Weave · HyperFrames · fal · Replicate · Meshy | Bot playbooks → download → Experiment Lab / Foundry intake |
| **Uncensored** | Adults 18+ craft | Local Illu/Pony/WAI + lab techniques | Uncensored only (#1176) — **not** cloud MCP |

Do not mix Uncensored try-queues into Canva/fal defaults. Do not treat Civitai week-delta (#1259) as frontier MCP work.

## Product surfaces

| LAS surface | Frontier MCP fit | Issue hooks |
|---|---|---|
| **Create** | Import cloud stills as **references** only; presets stay local | #14 atelier · #1207 island trial |
| **character-consistency** | Cloud multi-ref as draft sheet; lock locally | docs/character-consistency/* · #232 |
| **Shot Lab** | Cloud clips as b-roll / compare lane vs H3/LTX/Wan | #12 · #13 |
| **Asset Foundry** | Meshy/Tripo GLB intake + review checklist | #15 · #25 · #24 · #31 Blender/VRM |
| **AV / HyperFrames** | Already conceptualized in FRONTIER-RESEARCH §6 | HyperFrames connector live |
| **Spoken Briefs** | **Out of scope** for this pack (#635/#640 = local TTS audio) | skip |
| **Workflow Studio MCP** | Studio-owned commands (#123) ≠ cloud fal | keep separate |
| **AGENT-TOOLING** | comfy-local / comfy-cloud on PC | already documented |

## Docs placement (this wave)

Preferred draft PR paths:

- `docs/research/FRONTIER-MCP-ASSETS-2026-10-01-*.md` — research snapshot  
- Optional ADR seed: `docs/adr/NNNN-frontier-mcp-lane.md` (number when filing)  

Extend, do not rewrite: `docs/FRONTIER-RESEARCH.md`, `docs/FRONTIER-ARCHITECTURE.md`.

## Civitai lane vs frontier lane (operator cheatsheet)

| Need | Prefer |
|---|---|
| Anime identity + pose lock on 16GB AMD | Civitai Create (QI-2.1, WAI, CN) |
| Poster / social / layered marketing | Canva MCP |
| Editable campaign video | HyperFrames |
| Product UI mock | Figma |
| Photoreal / Flux-class without download | fal or Replicate MCP |
| Game prop mesh this week | Meshy MCP → Blender → Foundry |
| NSFW craft | Local Uncensored only |

## Issue comment targets (this pack)

| Issue | Why |
|---|---|
| #17 Frontier roadmap | Umbrella — add MCP cloud branch |
| #15 Asset Foundry | Meshy/Tripo intake |
| #25 3D props/rigs/motion | Rig/animate via Meshy |
| #1176 Uncensored | Explicit: cloud MCP ≠ Uncensored |
| #1259 Civitai week-delta PR | Complementary lane note |

**Skip #635 / #640** — Spoken Briefs audio; findings do not map.
