# Game Asset Lab

Research and agent-facing starter, **11 September 2026**. Additive to the current Studio and the earlier frontier PR; does not depend on that PR being merged. Existing runtime, model manifests and production presets are untouched.

## Read in order

1. [Frontier findings](FRONTIER.md): choose the right production route and inspect the new research candidates.
2. [Reference workflows](REFERENCE-WORKFLOWS.md): role-separated references and the three actual Qwen API graph variants.
3. [Agent contract](AGENT-CONTRACT.md): let an agent discover capabilities, create a plan, execute external tools and retain accepted stage evidence.
4. [Agent skill](../../agent-skills/game-assets/SKILL.md): reusable operating instructions for a local agent.

Machine entry points: [eight routes](../../research/game-assets/routes.json), [23 capability records](../../research/game-assets/capabilities.json), [37 primary-source entries](../../research/game-assets/sources.json), [brief schema](../../research/game-assets/brief.schema.json).

## Delivered versus future work

| Delivered | Evidence boundary |
|---|---|
| JSON plan/ready-task/receipt CLI | Tested offline. Does not invoke a model, editor, MCP service or engine. |
| One/two/three-reference Qwen API graphs and derivation factory | Static topology and regression checks passed. Extra reference paths still need installed-node validation and inference. |
| PNG sprite atlas packer | Pixel round-trip tested, preserves logical canvas, anchors and variable durations. Does not judge motion quality. |
| OpenRaster layer writer | ZIP/XML/layer order/composite tests passed. Native Krita import has not been tested here. |
| Procedural QA demo generator | Produces tiny frame/layer fixtures, an atlas and an ORA. These are test graphics, not generative character artwork. |
| Production routes and capability map | Agent instructions with dependencies and acceptance criteria, not eight completed autonomous production systems. |

No new model weights, live GPU jobs, paid services, downloaded third-party workflows, editor installations or commercial-license acceptances are part of this pass. Models listed in research are not automatically cleared for use. In particular, the standard **HY-Motion 1.0 and Hunyuan3D 2.1 grants exclude UK usage**; see the findings and exact source terms.

## Try the tools

The planner uses Python 3.12+ standard library. Media tools additionally use Pillow; this pass tested Python 3.13.5 / Pillow 12.3.0. Use an existing suitable asset-finishing environment or a separate venv, not the working Comfy interpreter. The optional requirements file pins the tested media dependency.

```console
python scripts/game_asset_pipeline.py routes
python -m unittest discover -s tests -p "test_game_asset_*.py" -v
python scripts/game_asset_demo.py --out experiments/runs/game-asset-qa
python scripts/game_asset_pipeline.py next --plan experiments/runs/game-asset-qa/plan.json --workspace experiments/runs/game-asset-qa
```

The last command returns `preflight` as ready. It does not generate anything. The demo directory must not already exist. Open `editable.ora` in Krita for the outstanding application-level test; the archive has real layers, not just a filename renamed from PNG.

```console
python scripts/game_asset_pipeline.py plan path/to/brief.json --out path/to/new-plan.json
python scripts/game_asset_pipeline.py qwen-variants --out experiments/runs/qwen-reference-variants
python scripts/game_asset_pipeline.py graph-check research/game-assets/workflows/qwen-3ref-api.json
python scripts/game_asset_pipeline.py graph-check research/game-assets/workflows/qwen-3ref-api.json --object-info path/to/saved-object-info.json
python scripts/game_asset_media.py atlas path/to/frames.json --workspace path/to/asset-workspace --out path/to/new-atlas-folder
python scripts/game_asset_media.py ora path/to/layers.json --workspace path/to/asset-workspace --out path/to/new-source.ora
```

`graph-check` deliberately implements a subset of Comfy validation: class/input availability, simple types/enums, link outputs and cycles. Dynamic custom-node schemas may need native validation. It never posts `/prompt`.

All asset paths inside manifests are portable workspace-relative paths with hashes. The CLI rejects traversal and symlinks escaping the workspace. Output paths are explicitly supplied by the calling agent and may be outside the workspace; the future executor must enforce its own output-root policy. Outputs are exclusive-create: choose a new name rather than overwriting a source. Keep one writer per job workspace.

## Important limitations

Budgets are **declared**, not enforced against an external agent's arbitrary actions. Receipts are integrity-checked attestations, not authenticated reviewer signatures. They verify nonempty files and exact bytes, not whether those bytes depict a good character or constitute a real engine import. The agent must actually do the work and attach meaningful evidence. The code intentionally does not pretend a `.json` report proves a runtime test.

Atlas PNGs use agreed untagged sRGB RGBA interchange. ICC-tagged inputs, non-PNG and non-RGBA inputs require explicit conversion first. Frames are never silently resized, trimmed, quantized or recolored. ORA supports flat, normal source-over layers; masks, groups, animation and rigs must remain in native project files. A partially written atlas retains `.incomplete`; consume only a completed manifest without that marker.
