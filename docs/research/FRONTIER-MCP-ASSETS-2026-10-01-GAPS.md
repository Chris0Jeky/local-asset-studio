# GAPS — blockers

## No MCP / not connected on Grok Bot box

| Gap | Impact | Mitigations |
|---|---|---|
| No fal / Replicate on box | Cannot run Flux-class / catalog video from Grok without new connector | Install hosted MCP with owner keys; or use Figma Weave for some models |
| No Meshy / Tripo / Rodin | No mesh generation from bot | Install `@meshy-ai/meshy-mcp-server`; Blender+MCP on PC |
| No Midjourney / Runway first-party MCP | Missing some brand-popular video/still UIs | fal/Replicate catalogs; Comfy partner Kling/Veo |
| Grok Bot ≠ PC comfy-local | This Linux box cannot drive RX 9070 XT Comfy | PC agents per AGENT-TOOLING; bot stays cloud connectors |

## Auth / account

| Gap | Notes |
|---|---|
| API keys not present in chat (correct) | Owner must add `FAL_KEY` / `REPLICATE_API_TOKEN` / `MESHY_API_KEY` in client config — never paste into issues |
| Weave / Comfy partner spend | Requires explicit cost acknowledgement |
| Comfy Cloud OAuth | On Codex only per AGENT-TOOLING; Claude/Grok not registered for cloud |

## Cost

| Gap | Notes |
|---|---|
| Per-run cloud billing | fal MCP free; pay per model run. Meshy credits per tool. HyperFrames render may be paid (`render_video` docs). |
| No pricing invented here | Use fal `get_pricing` / Meshy `meshy_check_balance` after install |

## Quality

| Gap | Notes |
|---|---|
| Character identity | Cloud MCP << local Create + character-consistency docs |
| Engine-ready 3D | Mesh gens need remesh/UV/rig/LOD review (#15) |
| Shot continuity | Cloud video ≠ Shot Lab anchors (#12) |
| NSFW | Most cloud endpoints filter; Uncensored remains local |

## AMD / local GPU

**Mostly irrelevant for frontier cloud MCP** (by design). Still relevant when hybrid: downloading huge Meshy textures or running Blender cleanup on 16GB is fine; local TRELLIS.2 24GB CUDA story from FRONTIER-RESEARCH remains a **local** gap, which Meshy cloud partially bypasses.

## Process

| Gap | Notes |
|---|---|
| Evidence trail | Cloud URLs expire; must download + hash into experiments |
| License / commercial | Each provider ToS separate from Civitai model licenses — record on acceptance |
| Plugin catalog SearchPlugins | Not available as a meta-tool on this executor; inventory via GetMcpTools + web docs |
