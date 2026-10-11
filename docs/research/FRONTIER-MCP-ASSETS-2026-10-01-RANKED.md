# RANKED — next actions (prefer docs/ADR)

## Tier A — docs / ADR only (do first)

1. **ADR: Frontier-MCP lane beside Civitai Create** — decision: cloud MCP outputs are Experiment Lab / Foundry intake, never silent Create-preset promotion; evidence receipt schema from FRONTIER-ARCHITECTURE.  
2. **Research snapshot in `docs/research/`** — this pack condensed (LANDSCAPE + PIPELINES matrices). Draft PR only.  
3. **Cross-link** FRONTIER-RESEARCH §5–6 + AGENT-TOOLING: “connected bot connectors vs PC comfy-mcp”.  
4. **Update mental model in #17** via comment: add workstream “Frontier MCP connectors” under Shot Lab / Foundry without new competing issue.

## Tier B — skills / bot playbooks

5. **Playbook: Canva still → HyperFrames b-roll → Buffer** (SFW marketing). Skill markdown under agent skills or `docs/design-handoff/`.  
6. **Playbook: Figma Weave cost-gate** — always quote `acknowledgedCost`, never auto-spend.  
7. **Playbook: Meshy prop** (once key exists) — image→3D→remesh→download→Foundry checklist.  
8. **Optional:** Meshy skill pack `npx skills add meshy-dev/meshy-3d-agent` (REST, no MCP) as interim.

## Tier C — issue seeds (reuse existing first)

9. Comment **#15** — Meshy MCP as primary cloud Foundry intake; acceptance = multi-view + UV + scale, not “GLB opens”.  
10. Comment **#25** — Meshy rig/animate = prototype only; keep UniRig/human bend tests.  
11. Comment **#1176** — Uncensored stays local; quarantine cloud NSFW.  
12. Comment **#1259** — frontier pack complementary to Civitai week-delta; no Create flip.  
13. **Do not** open new tickets if #15/#17/#25 cover; only seed if owner wants a dedicated “connector auth inventory” issue later.

## Tier D — draft code PR (prefer NOT)

14. **Skip** Studio code to wrap fal/Meshy this wave — no product surface yet; docs first.  
15. **Skip** merges of any kind.  
16. Only justified code later: thin “import remote asset URL + receipt” helper under Experiment Lab (#10) after ADR signed.

## Top 5 for Chris (operator)

| # | Action | Tier |
|---|---|---|
| 1 | Merge-ready? No — review draft docs PR only | A |
| 2 | Decide install: fal **or** Replicate first (stills/video), then Meshy (3D) | B/C |
| 3 | Run one Canva→HyperFrames smoke with existing connectors | B |
| 4 | Comment/#15 Meshy Foundry contract | C |
| 5 | Keep Uncensored local; ignore cloud for NSFW | C / EXPLICIT |

## Explicit non-actions

- No comments on #635/#640  
- No weight downloads  
- No Midjourney MCP hope  
- No claiming Meshy meshes are engine-ready
