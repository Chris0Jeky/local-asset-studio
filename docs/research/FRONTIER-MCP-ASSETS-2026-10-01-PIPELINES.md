# PIPELINES — end-to-end recipes (bot → MCP → artifact → LAS)

Quality labels: **P** = prototype · **G** = good enough for review · **Prod** = shippable with light human polish. All paths assume **no secrets in chat** and **no weight downloads**.

## P1 — Marketing / UI still (connected) — Prod

```
Brief → Canva generate-image (optional imageReferences)
     → get-generate-image-job → Open generated image / export-design PNG
     → download to handoffs or Drive
     → optional: Canva separate-image-layers / remove-background
     → land: docs screenshots · Buffer create_post asset · Notion brief
```

**LAS:** Not Create-primary. Use as **reference uploads** into Prompt Lab / character pack (#38) or campaign finishing (#16).  
**Quality:** Prod for social/poster; not anime identity pack.

## P2 — Design system screen → code (connected) — Prod

```
Figma file → get_design_context / download_assets
          → repo PR (UI) — outside pure asset gen
```

Optional generative: `weave_find_model` → cost quote → user Approve → `weave_run_model` → download outputs → `upload_assets` into file.

**LAS:** Design-handoff docs; not Comfy Create.  
**Quality:** Prod for product UI; Weave gen quality = underlying model (verify per run).

## P3 — Branded motion / spoken campaign (connected) — G→Prod

```
COMPRESSED.md / brief → HyperFrames compose (design_source preset)
                     → get_project_status until draft/completed
                     → MP4 URL → optional Buffer schedule
```

Alt: Figma motion timeline → `export_video` MP4.

**LAS:** Spoken Briefs (#635) stay **local TTS**; HyperFrames is **visual** campaign lane, complementary not replacement.  
**Quality:** Prod for explainers; not Shot Lab cinematic continuity (#12).

## P4 — Frontier stills without local GPU (install fal or Replicate) — G

```
Bot + fal MCP (search_models → get_pricing → run_model / submit_job)
  OR Replicate MCP (models.search → predictions)
→ CDN URL → download to LAS experiments root OR Canva upload-asset-from-url
→ human acceptance record (FRONTIER-ARCHITECTURE evidence shape)
```

**LAS:** Treat as **Experiment Lab cloud branch** (#10) — separate from local Create presets. Do not auto-promote into SFW Create defaults.  
**Quality:** Often G–Prod single frames; identity across set still needs local Create.

## P5 — Character sheet assist (hybrid) — P→G

```
Accepted face/costume refs (local Create or photos)
→ Canva/Weave/fal with multi-ref / maintainCharacterConsistency-style guidance
→ sheet candidates
→ LAS character-consistency EDIT runbook (Krita / Qwen-Edit / IP-Adapter)
→ promote only after identity metrics
```

**Honest:** Frontier MCP **does not replace** `docs/character-consistency/*` or Civitai Consistency LoRA try-seeds from 2026-09-30 pack.  
**Quality:** P alone; G with local lock.

## P6 — Prop / character mesh (install Meshy) — P→G

```
Approved still (P1/P4 or Create)
→ meshy_image_to_3d (or multi_image) [ai_model per Meshy docs]
→ meshy_remesh / meshy_retexture
→ optional meshy_rig → meshy_animate
→ meshy_download_model GLB/FBX
→ Blender MCP or manual: pivot, scale, UV check, LODs
→ LAS Asset Foundry contract (#15) → engine round-trip (#24)
```

**LAS map:** Feeds #15 / #25; complements TRELLIS/Hunyuan local research in FRONTIER-RESEARCH (AMD 16GB often blocks local 3D — cloud Meshy is the practical path).  
**Quality:** G for props after cleanup; character skinning **P** until human bend tests.

## P7 — Short AI video shot (install fal/Replicate or Weave) — P→G

```
Still or prompt → fal/Replicate video model OR Figma weave_run_model (Veo-class if available)
→ clip URL → HyperFrames compose as muted b-roll OR Shot Lab intake later
```

**LAS:** Parallel to H3/LTX/Wan local Shot Lab (#11–#13). Use cloud when AMD/H3 path blocked.  
**Quality:** G for mood/b-roll; P for contact-accurate gameplay motion.

## P8 — Comfy partner / Cloud (PC agents) — G

```
Codex/Claude with comfy-mcp partner_generate OR comfy-cloud
→ hosted Flux/Ideogram/Kling/… (credits)
→ download into Studio-labeled agent run (docs/AGENT-TOOLING.md rules)
```

**Do not** bypass Studio evidence from Grok Bot against shared portable Comfy.  
**Quality:** Model-dependent; treat as paid Experiment Lab.

## Landing contract (all pipelines)

Every artifact that enters the repo or LAS library should carry:

1. Source connector / MCP server id  
2. Model or tool name as returned (no invented aliases)  
3. Prompt / refs hashes or URLs  
4. Cost acknowledgement if Weave/Comfy partner  
5. Acceptance: reviewed true/false  

Prefer writing receipts under pack `_artifacts/` or LAS experiments root — **not** committing binaries to git.
