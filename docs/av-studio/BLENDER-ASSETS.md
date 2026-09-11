# Blender automation and model/animation sources

Research date:11 September 2026. This directory provides source guidance and a narrow Blender job adapter. **No downloaded character pack, Blender execution or live Blender MCP session is claimed in this pass.** Existing Radeon TRELLIS and Blender-finishing evidence in CURRENT_STATE.md remains valid at its recorded scope.

## Choose the source according to the experiment

| Starting point | Why use it | Availability and constraints |
|---|---|---|
| [VRoid Studio](https://vroid.com/en/studio/guidelines) and [documented sample models](https://vroid.pixiv.help/hc/en-us/articles/31627266179865-How-to-use-sample-models) | Original anime avatars with editable appearance; useful for portraits, animation and voice/face integration | Preserve specific sample/preset and third-party clothing/hair terms. Not a blanket CC0 collection. |
| [VRoidPreset A–Z](https://vroid.pixiv.help/hc/en-us/articles/4402394424089-VRoidPreset-A-Z) | A specifically documented family to modify rather than a random ripped game mesh | Use the exact A–Z rules; old beta samples can have different terms. |
| [Quaternius Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html) | Practical CC0 stylized humanoid bases for games and controlled retargeting | Free Standard is a subset. Do not advertise every full-library body/hair or source BLEND as free. |
| [Quaternius Fantasy Outfits](https://quaternius.com/packs/modularcharacteroutfitsfantasy.html) | Compatible modular clothing and fantasy character combinations | Check the selected tier and matching skeleton/version before assembly. |
| [Universal Animation Library Standard](https://opengameart.org/content/universal-animation-library) | Author-published CC0 free pack with45 animations | The full120+ collection is a different tier. Save the actual archive/version and clip inventory. |
| [Universal Animation Library2 Standard](https://opengameart.org/content/universal-animation-library-2) | An independent free expansion for more gameplay actions | The complete130+ marketing count is not the free-subset count. |
| [Blender Studio Rain v3](https://studio.blender.org/characters/rain/v3/) / [Snow v4](https://studio.blender.org/characters/snow/v4/) | Creator-issued full rigs for acting, facial performance and animation practice | CC-BY credits and Blender4.1+ requirements; production rig features are not automatically portable to a game skeleton. |
| [Blender Studio Storm](https://studio.blender.org/characters/storm/v1/) | A newer expressive rig/pose-library investigation | Author specifies Blender5.0; confirm current download access and exact version. |
| [Adobe Mixamo](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) | Humanoid auto-rigging and reusable motion | Adobe ID/hosted uploads. Character and motion use inside projects is distinct from redistribution of a standalone library. |

The Quaternius author published a [June2026 root-motion update](https://quaternius.itch.io/universal-animation-library/devlog/1555893/added-root-motion-and-other-fixes), including root-motion/in-place variants and directional-loop fixes. An old downloaded zip can therefore behave differently from the current examples. Record what was downloaded rather than assuming all filenames reflect the latest rig.

For identifiable franchise characters, start with the original publisher/creator's issued model and its readme. A game-character name on a model-sharing site is not evidence of permission, mesh quality or authorship. Fan models and MMD/PMX/VMD assets have per-file conditions that can differ on modification, redistribution, commercial use and animation content. This pass deliberately supplies concrete original-anime and game-style sources rather than claiming an unverified franchise mesh is officially distributed. User-provided authorised files remain supported inputs to the proposed intake path.

## A useful first anime-avatar pipeline

`choose/author avatar → inspect skeleton/materials/expressions → modify costume/appearance → approve neutral reference → retarget one motion → map mouth cues/blinks → render portraits and a short dialogue shot → export a game variant separately`

[VRM Add-on for Blender](https://github.com/saturday06/VRM-Addon-for-Blender) and [VRM Animation](https://vrm.dev/en/vrma/) are important compatibility references. Record VRM version, humanoid bone map, expressions, eye-look, spring bones and MToon material assumptions. A plain GLB exporter may not preserve all of that metadata. Test Blender, viewer and target engine independently.

Maintain two branches: an editable/high-quality animation source and a runtime export with deliberate budgets, shader replacements, colliders and supported bone/expression data. Reducing polygons does not automatically make a production rig game-ready. Keep portrait render cameras and lighting fixed so comparisons reveal appearance changes rather than reframing.

For motion transfer, inspect rest-pose orientation, names, scale and proportions before retargeting. Test an idle and walk with known contact points. Review feet, hips, root translation, loop velocity and prop attachments. Source and target skeletons being humanoid is necessary but insufficient for acceptable movement. Use explicit in-place and root-motion outputs when the controller needs both.

For speech, translate accepted Rhubarb/alignment cues into an authored expression map. Preserve a neutral baseline and let emotion/blinks coexist with mouth motion. Avoid assuming every avatar uses ARKit names or that a viseme coefficient can be copied unchanged between characters. Retain cue timing in seconds/samples and the scene frame conversion in the job manifest.

## Automation choices

**Direct Blender CLI/bpy:** best first route for repeatable inspect/render/export operations in a disposable process. **Reviewed in-application adapter:** useful for interactive scene changes and readback without losing the user's context. **Broad community MCP:** useful for exploratory modelling when explicitly trusted, but its arbitrary code path should not become an unattended production default. [Blender MCP source](https://github.com/ahujasid/blender-mcp).

The included `integrations/blender/av_job.py` supports three named operations: `inspect_scene`, `render_frame` using an already approved camera, and `export_glb`. The code returns scene object dimensions, armature bone names, actions, shape-key names and materials, making the next operation discoverable to an agent. It does not invent motions, remesh an imported asset or claim a working live connection.

Example local job, after saving a safe copy of the source scene:

```json
{"operation":"inspect_scene","report":"scene-report.json"}
```

```powershell
blender --background "C:\AI\jobs\avatar\source.blend" --disable-autoexec --python "C:\path\local-asset-studio\integrations\blender\av_job.py" -- --workspace "C:\AI\jobs\avatar" --job "inspect.json"
```

Use an isolated process, workspace and OS permissions for untrusted files. `--disable-autoexec` avoids automatically trusting embedded scripts; it is not a complete exploit sandbox. Creator rigs can require scripts for UI/drivers; explicitly audit and trust the selected source when that is necessary rather than silently enabling scripts for all downloads. The adapter does not save over the input BLEND and refuses existing output/report files, but it is not safe against concurrent hostile filesystem mutation. Keep one writer.

## Model intake manifest to implement next

Capture creator page, download URL/version, archive/file SHA256, extracted file list, licence/readme hash, attribution, format, skeleton summary, textures/materials, scene units, addon/version requirements and declared permissions. Reject archive traversal and path collisions; never auto-run an installer from a character pack. Inspect missing textures and external file references before rendering. For GLB/VRM, parse structural metadata and run the appropriate validators before importing into a broad scripting environment.

The agent's first four questions should be answered by data, not guesswork: does the model have a rig; does it have usable facial shapes; does the desired motion map to that rig; and what must be preserved for the target renderer/engine? A screenshot plus a structured inspector report is substantially more useful than a one-line “import succeeded.”

Recommended controlled experiment: a VRoid original avatar for anime identity/face work; one Quaternius humanoid plus Standard motion pack for the game-export path; and Rain or Snow for richer facial/body acting. Reuse the existing procedural Lanternkeeper for deterministic rendering tests. Do not start with a folder of unrelated franchise rips and expect a universal retargeter to resolve every incompatibility.
