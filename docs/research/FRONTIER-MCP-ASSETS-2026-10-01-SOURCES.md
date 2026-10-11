# SOURCES — URLs, server ids, timestamps

**Retrieved:** 2026-10-01 ~00:30–00:45 BST (Europe/London, box clock).  
**Method:** GetMcpTools (live connected), WebSearch, WebFetch, gh/cursor-github issues, prior handoff packs, LAS docs via GitHub API.

## Live MCP servers (ready on Grok Bot box)

| Server | Evidence |
|---|---|
| `user-Canva` | GetMcpTools serverStatus ready — generate-image, export-design, remove-background, separate-image-layers, … |
| `user-Canva-xai` | GetMcpTools ready — same family |
| `user-Figma-xai` | GetMcpTools ready — weave_*, export_video, get_design_context, … |
| `user-HyperFrames by HeyGen-xai` | GetMcpTools ready — compose, render_video, list_projects, … |
| `user-Buffer-xai` | GetMcpTools ready — create_post, list_channels (publish only) |
| `user-Notion` / `user-Notion-xai` | Catalog present |
| `cursor-github` / `user-GitHub-xai` | Issue/PR tools |
| `user-Playwright` | Browser |
| `user-Context7` | Docs |

## Official / upstream docs fetched or searched

| Topic | URL |
|---|---|
| Meshy AI / MCP | https://docs.meshy.ai/en/api/ai |
| Meshy MCP repo | https://github.com/meshy-dev/meshy-mcp-server |
| fal MCP landing | https://fal.ai/mcp |
| fal MCP docs | https://fal.ai/docs/documentation/setting-up/mcp |
| fal blog MCP | https://blog.fal.ai/connect-your-ai-to-1-000-models-with-the-fal-mcp-server/ |
| Replicate MCP site | https://mcp.replicate.com/ |
| Replicate MCP docs | https://replicate.com/docs/reference/mcp |
| Comfy-Org comfy-mcp | https://github.com/Comfy-Org/comfy-mcp |
| artokun comfyui-mcp | https://github.com/artokun/comfyui-mcp |
| trident-mcp (Tripo) | https://github.com/Gdetrane/trident-mcp · https://github.com/mordor-forge/trident-mcp |
| mcp-3d-gen | https://github.com/kevinten-ai/mcp-3d-gen |
| blender-mcp | https://github.com/ahujasid/blender-mcp |
| AceDataCloud LumaMCP | https://github.com/AceDataCloud/mcp-luma |
| Wireflow image MCP roundup | https://www.wireflow.ai/blog/best-ai-image-generation-mcp-tools-in-2026 |
| Wireflow Luma MCP | https://www.wireflow.ai/blog/best-luma-mcp-tools-in-2026 |
| mcp-image | https://mcpservers.org/servers/shinpr/mcp-image |

## LAS repo evidence

| Item | URL / path |
|---|---|
| FRONTIER-RESEARCH.md | docs/FRONTIER-RESEARCH.md (as of fetch 2026-10-01) |
| FRONTIER-ARCHITECTURE.md | docs/FRONTIER-ARCHITECTURE.md |
| AGENT-TOOLING.md | docs/AGENT-TOOLING.md |
| character-consistency/ | docs/character-consistency/* |
| #17 Frontier roadmap | https://github.com/Chris0Jeky/local-asset-studio/issues/17 |
| #15 Asset Foundry | https://github.com/Chris0Jeky/local-asset-studio/issues/15 |
| #25 3D props/rigs | https://github.com/Chris0Jeky/local-asset-studio/issues/25 |
| #1176 Uncensored north-star | https://github.com/Chris0Jeky/local-asset-studio/issues/1176 |
| #1259 Civitai week-delta draft PR | https://github.com/Chris0Jeky/local-asset-studio/pull/1259 |
| #635 Spoken Briefs (skipped) | https://github.com/Chris0Jeky/local-asset-studio/issues/635 |
| #640 Chaptered listening (skipped) | https://github.com/Chris0Jeky/local-asset-studio/issues/640 |
| #123 Workflow Studio MCP | https://github.com/Chris0Jeky/local-asset-studio/issues/123 |

## Prior packs

- `/workspace/handoffs/civitai-scavenge-2026-09-30/`
- `/workspace/handoffs/las-image-models-wave-2026-09-24/`
- `/workspace/handoffs/nsfw-north-star-2026-09-27/`
- `/workspace/handoffs/ming-image-design-2026-09-27/`

## Honesty constraints applied

- No invented list prices  
- No claim Runway/Midjourney first-party MCP exists  
- Weave/Comfy partner model availability must be re-checked at call time via weave_find_model / list_partner_models  
- Meshy tool names taken from docs.meshy.ai (may evolve — re-read MCP source before coding)
