# #923 "zero-output success": live probe — 27 September 2026 (17:31-17:32 local)

**Claim under test** (#923): `_observe_history` marks a submission `completed` when history has no error status and
empty `outputs`. Can ComfyUI report success **with no outputs** for a graph that has a save node? The most plausible
honest route is a prompt that ComfyUI answers entirely from its cache.

**Setup.** ComfyUI 0.35.0 on the primary (8188), which logs "Using RAM pressure cache". The Studio ran main `8c37eb05` (PID 31928).
`probe.py` is the as-run driver and `probe.json` holds every record.

| Probe | What | IDs | ComfyUI history | Studio record |
| --- | --- | --- | --- | --- |
| P1 | Studio `wai` job, SFW scenery, seed 2026092923, 12 steps | job `0bee0aae`, prompt `e9fa48e3` | `success`; `execution_cached` = []; outputs `7: Studio/WAI-Illustration_00052_.png` | `completed`, 34.3 s, 1 output, asset `8e98ec83…` |
| P2 | identical Studio job (same controls, same seed) | job `b7fb7ed4`, prompt `482a6b29` | `success`; `execution_cached` = all 7 nodes, **including SaveImage `7`**; outputs `7: Studio/WAI-Illustration_00052_.png` (P1's file) | `completed`, 0.1 s, 1 output = P1's file, new asset row `58ab073c…` |
| D1 | direct `LoadImage -> SaveImage`, no model | prompt `1d16ef5b` | `success`; nothing cached; outputs `probe_00001_.png` | (not a Studio job) |
| D2 | identical direct graph | prompt `36650b10` | `success`; `execution_cached` = [`1`, `2`]; outputs `probe_00001_.png` (D1's file) | (not a Studio job) |

A third, accidental case confirms the cache path. On the same day, `experiments/curated/cancel-live-20260927/` job `5e4ce0fa`
(prompt `553b363b`) repeated job `b84538ac`'s graph, finished in 0.5 s, and recorded `WAI-Illustration_00051_.png`, the
earlier job's file.

**Result: refuted on the cache path.** When a prompt is served entirely from cache, save node included, ComfyUI 0.35.0
still reports `success` **with** outputs. It replays the cached node's UI result, which names the earlier file. The code
agrees. In `execution.py`, a cached node goes through `_send_cached_ui()`, which copies `cached.ui` into `ui_outputs`.
`history_result["outputs"]` is built from that, and `SaveImage` always returns a `ui` block. No zero-output success was
observed.

**What the Studio records instead (not a zero-output bug).** A fully cached repeat is recorded as `completed` in about 0.1 s.
Its output is the earlier job's file, registered as a second asset row (asset IDs are per job and output index, so
`8e98ec83…` and `58ab073c…` point at the same bytes). Nothing marks that output as a cache replay rather than a new render.
The picture is truthful (same graph, same seed), but the receipt cannot distinguish a render from a replay.

**Not verified.** A save node whose cached `ui` is `None`, and an empty image batch, were not produced. In this build,
`ImageFromBatch` clamps its length to at least 1, and `EmptyImage` has a minimum batch of 1. RAM-pressure evictions
drop a whole cache entry, so the node re-executes; that was read in the code, not tested. Custom output nodes were not
covered. The Studio still has no guard for a zero-output success: if one ever occurs, it would record `completed` with
no outputs.

## Exact recipes

`recipes/0bee0aae-recipe.json` (P1) and `recipes/b7fb7ed4-recipe.json` (P2) are the Studio's own `/api/jobs/<id>/recipe` exports, fetched after the run, 27 Sep 2026. Each holds the preset, the controls and the full submitted workflow, so the probe stays reproducible if the `wai` catalog entry or graph changes later.
