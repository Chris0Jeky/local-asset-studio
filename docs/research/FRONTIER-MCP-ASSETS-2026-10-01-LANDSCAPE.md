# LANDSCAPE — connector / MCP inventory (2026-10-01 ~00:30 BST)

Live check: `GetMcpTools` against Grok Bot box servers. Installable rows from official docs / GitHub (WebSearch + WebFetch). **Do not invent** model names, prices, or tools not evidenced below.

Legend: **Connected** = ready on this box today · **Installable** = documented MCP exists, needs owner key/config · **Absent** = no credible first-party MCP found in this pass.

## A. Already connected (verified ready)

| Server id | Stills | Consistent char | Video / anim | 3D mesh/tex/rig | Notes |
|---|---|---|---|---|---|
| `user-Canva` / `user-Canva-xai` | **Yes** (`generate-image`, refs, bg remove, layer split) | Weak (imageReferences / restyle; not identity LoRA) | Export MP4 from designs only | No | Marketing / layout / social; export PNG/JPG/PDF/MP4 |
| `user-Figma-xai` | Design UI + **Weave models** (`weave_find_model` / `weave_run_model`) | Via Weave if model supports refs (cost-gated) | **Yes** — Weave video models + `export_video` timeline MP4 | Weave may expose 3D-typed tool inputs; not a mesh Foundry | Design-to-code primary; generative spend needs `acknowledgedCost` |
| `user-HyperFrames by HeyGen-xai` | Indirect (compose uses linked media) | Brand style presets, not face LoRA | **Yes** — `compose` → MP4 (auto-render) | No | Campaign / captioned motion; public HTTPS media URLs only |
| `user-Buffer-xai` | No gen | No | No | No | Publish/schedule only — sink, not source |
| `user-Notion` / `user-Notion-xai` | No gen | No | No | No | Docs / briefs sink |
| `user-GitHub-xai` / `cursor-github` | No gen | No | No | No | Repo landing for docs/receipts |
| `user-Playwright` | Capture | — | — | — | Screenshot / QA, not generative |
| `user-Context7` | Docs | — | — | — | Library docs, not assets |

**Local PC (documented in LAS `docs/AGENT-TOOLING.md`, not this Linux box):** `comfy-local` via comfy-mcp 0.10.0 against portable ComfyUI — stills/video through **local** graphs. Codex also has `comfy-cloud` OAuth. Agent rule: generations belong in Studio evidence trail, not raw MCP `run_workflow` on shared install.

## B. Installable frontier MCPs (not on this box)

| Provider | Evidence | Stills | Char consistency | Video | 3D | Auth |
|---|---|---|---|---|---|---|
| **fal.ai** hosted MCP | https://fal.ai/mcp · https://mcp.fal.ai/mcp | Catalog 1000+ | Model-dependent (search_models) | Yes | Yes (catalog includes 3D) | `FAL_KEY` Bearer |
| **Replicate** official MCP | https://mcp.replicate.com/ · https://replicate.com/docs/reference/mcp · npm `replicate-mcp` | Yes | Model-dependent | Yes | Some community 3D models | `REPLICATE_API_TOKEN` / OAuth |
| **Meshy** official MCP | https://docs.meshy.ai/en/api/ai · npm `@meshy-ai/meshy-mcp-server` · github.com/meshy-dev/meshy-mcp-server | `meshy_text_to_image` / `_to_image` | Multi-image → 3D helps identity for props/chars | `meshy_animate` on rigged | **Strong** — text/image/multi→3D, remesh, retexture, **rig**, animate | `MESHY_API_KEY` |
| **Tripo** via trident-mcp / mcp-3d-gen | github.com/Gdetrane/trident-mcp · kevinten-ai/mcp-3d-gen | — | Multi-view | — | text/image/multiview→3D, retopo, convert | `TRIPO_API_KEY` |
| **Hyper3D Rodin** | Via mcp-3d-gen / blender-mcp Hyper3D path | — | — | — | Gen-1.5 style mesh | Provider key |
| **Comfy-Org comfy-mcp** | github.com/Comfy-Org/comfy-mcp · cloud.comfy.org/mcp | Local + **partner_generate** (hosted) | Via graphs / partner models | Partner video (Kling etc. per docs) | Not primary | Local URL and/or `COMFY_API_KEY` |
| **artokun/comfyui-mcp** | github.com/artokun/comfyui-mcp | Local agent control plane | Skills (Flux, WAN, Qwen…) | LTX / WAN packs | — | Local Comfy |
| **Blender MCP** | github.com/ahujasid/blender-mcp | Scene renders | — | — | Scene ops + Rodin/Hunyuan3D hooks | Local Blender + addon |
| **Luma** | Community AceDataCloud LumaMCP; Wireflow notes official Luma MCP for Ray/Photon | Photon images | — | Ray video | — | Third-party or Luma key — **verify before install** |
| **mcp-image** (shinpr) | mcpservers.org / Gemini·OpenAI·Seedream | Yes | `maintainCharacterConsistency` flag (prompt guidance, not LoRA) | No | No | Provider keys |

## C. Searched but no first-party MCP found this pass

| Name | Status |
|---|---|
| Midjourney | Absent as MCP (Discord/web product) |
| Runway / Pika / Kling first-party MCP | No first-party MCP confirmed; Kling appears via **Comfy partner-API** and fal/Replicate catalogs |
| Ideogram / Leonardo / Scenario / Stability / Adobe Firefly first-party MCP | Not confirmed first-party; may appear inside fal/Replicate/Comfy partner lists |
| Spline / CSM / Kaedim / Sloyd / Alpha3D first-party MCP | Not confirmed this pass |
| OpenAI / Gemini native “Images MCP” | No dedicated OpenAI Images MCP verified; Gemini/OpenAI reachable via **mcp-image**, Comfy partner nodes, or Weave |

## D. Capability matrix (honest)

| Capability | Best **connected** path | Best **installable** path | Quality today |
|---|---|---|---|
| HQ stills (SFW marketing) | Canva `generate-image` · Figma Weave | fal / Replicate Flux-class | **Production-good** for social/marketing |
| HQ stills (game / anime craft) | — | fal/Replicate + pull into LAS Create review | **Prototype → good**; Create LoRA stack still wins consistency |
| Consistent characters | Canva refs · Weave refs | mcp-image flag · multi-ref on fal · then LAS character-consistency | **Weak–medium** via MCP alone; **strong** local Create |
| Animation / campaign video | HyperFrames · Figma `export_video` · Weave video | fal / Replicate video · Comfy partner Kling/Veo | **Production-good** for branded explainers; **prototype** for shot-accurate game cinematics |
| 3D mesh + texture | None connected | **Meshy MCP** (primary) · Tripo · Rodin · Blender cleanup | **Good prop prototypes**; **not** finish-ready without remesh/UV/rig review (#15/#25) |
| 3D rig + anim | None | Meshy `meshy_rig` + `meshy_animate` | **Prototype**; UniRig/human review still required (LAS frontier docs) |

## E. What this box cannot do without new connectors

- Native Meshy / Tripo / Rodin tool calls  
- fal / Replicate catalog runs from Grok Bot  
- Midjourney  
- Guaranteed NSFW-capable cloud gen (see EXPLICIT.md)
