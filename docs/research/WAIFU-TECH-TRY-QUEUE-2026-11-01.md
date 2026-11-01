# Frontier try-queue, 1 November 2026

A web scan of anime-capable models, reference methods and 3D-adjacent tools released mostly August to November 2026,
ranked by value per hour on this PC (RX 9070 XT 16 GB, ROCm, no CUDA). Every fit is a hypothesis until it runs here.
Reddit and Civitai pages returned nothing usable, so nothing below rests on them alone.

| # | Candidate | What it uniquely adds | Status here |
| --- | --- | --- | --- |
| 1 | [Character sheet LoRAs](https://huggingface.co/Alissonerdx/CharacterSheet) (TripleView, Klein 9B) | Front, side and back from one picture. Stock LoRA loader, no custom node | **Shipped** as `character-sheet-klein-9b`. Clean anime turnarounds on white with head and feet level. Agent-inspected only |
| 2 | Anima Turbo v1.1 (in [`circlestone-labs/Anima`](https://huggingface.co/circlestone-labs/Anima)) | CFG 1 at 8 to 12 steps. One blog reports about 4x speed with the reference adapter, only at `ref_guidance` 1.0 | **Proven.** 4.6 s against 27 s, and 0.2091 against 0.2109 at strength 1.0. Preset `anima-ref-adapter-turbo`. Receipts: [adapter notes](../../experiments/curated/anima-ref-adapter/README.md#anima-turbo-v11) |
| 3 | [See-through](https://github.com/shitagaki-lab/see-through) (Apache-2.0, SIGGRAPH 2026) | One anime image to up to 23 RGBA layers in a PSD. README names a ROCm wheel | Not tried. Needs its own environment, not the shared runtime |
| 4 | [Anima-LLLite](https://huggingface.co/kohya-ss/Anima-LLLite) | Masked inpainting and line-art control for Anima, which has had neither | Not tried. Node is marked experimental |
| 5 | [Anima Role Ref KV](https://huggingface.co/AnticPan/Anima-Role-Ref-KV) (26 October) | A rival one-reference method, cached once | **Tried.** Runs here, Turbo included. CCIP level with the adapter, within noise (0.1956 against 0.1929), so the owner decides. [Receipts](../../experiments/curated/anima-ref-adapter/README.md#anima-role-ref-kv-head-to-head) |
| 6 | Anima InContext Character, `crazysheep924/AnimaRefLora` | More rival reference adapters. The second has an Apache-2.0 adapter | Not tried |
| 7 | Qwen 2.1 Anime_consistency, Multiple-Angles v2 | Four-view sheets and camera moves on the existing `qwen21` backend | Not tried |
| 8 | [LanPaint 2.2](https://github.com/scraed/LanPaint) | Training-free masked sampling on models without an inpaint checkpoint | Not tried. Custom node, keep off the primary backend |
| 9 | [StableGen 0.4](https://github.com/sakalond/StableGen) (GPL-3.0) | Blender add-on projecting textures from a ComfyUI server, with TRELLIS.2 meshes and auto-rig | Not tried. Rigger's ROCm status unknown |
| 10 | VNCCS 3.2, Character Card Studio | Character library and 4 to 14 panel cards on Qwen 2.1 | Not tried. Heavy node packs |

Rejected for now:

- FLUX 3 Image Klein: gated, needs a newer ComfyUI than 0.35, INT8 claim is NVIDIA-only.
- Fibo 2.0: 16.25 GB transformer alone, gated.
- MOSS Edit HQ v5: about 20 GB, not trained for pose, needs ComfyUI 0.42.3 or newer against the 0.42.1 backend.
- Krea 2 BBOX: 26 GB, aimed at comics layout.
- Anima-2.9B preview: the stock adapter corrupts it without a key remap, about 1.4x slower in one test.
- Hi3D, Idol, UltraTex: geometry only, CUDA, or sparse-attention kernels with no anime claim.

Empty slots: no new NoobAI or Illustrious release in 2026, and no anime-specific hand or eye repair tool turned up.

Differentiable rendering is a dead end on this card for now: nvdiffrast's GL path delegates to CUDA, Mitsuba has no
non-CUDA GPU backend, and no timing at 100k vertices exists for any CPU path. Agent mesh work therefore fits targets by
image registration in plain numpy and scipy; see the separate agent-sculpt tool.

## Engines

Would a real-time engine help? As a verifier, yes. It does not replace Blender or ComfyUI.

| Verdict | Engine | Why | Cost |
| --- | --- | --- | --- |
| Adopted | Godot 4.7.2 (installed, no account) | Loads a GLB as a game would and reports what survives. On a real figure it showed hair colour that lived in Blender shaders did not reach the export, which Blender renders hide. Spring bones and custom `light()` toon shaders are next | About 0 GB, seconds per proof |
| Owner step | Unreal Engine 5.8.x (5.8 shipped 17 June 2026) | Worth it only for Wuthering Waves-class shading. Substrate NPR/Toon is experimental in 5.8, and outlines still need post-process | 70 to 150 GB by forum figures, about 10 to 20 hours to a first proof, an Epic account for source access; launcher sign-in unconfirmed |
| Skip for now | Unity 6, Bevy, Filament | No gain over Godot for proofs | |

`--headless` Godot renders nothing: a pixel proof opens a window. The RX 9070 XT is not named on Epic's hardware pages. It
falls under "RX-6000 series or newer" for Lumen by inference, and no run or benchmark was found. Unreal facts come from Epic's
5.8 release notes and specs read 1 November 2026; size and sign-in come from forum posts or search text, so re-check them
before any install.

## Vendor tools (read 1 November 2026, from primary repositories)

Adopt now:

| Tool | Value | Notes |
| --- | --- | --- |
| [gltfpack](https://github.com/zeux/meshoptimizer) 1.3 (MIT) | Merges meshes and materials | **Tried.** On a real 316-mesh character GLB, Godot's peak draw calls went from 660 to 64 with bones and vertices intact. Morphs went 230 to 115 because two meshes sharing the same 115 were merged: no name was lost, and all 103 that move kept the same peak displacement. Playing one 2 cm morph in Godot changed the same 16 pixels on both files (IoU 1.000). Use `-noq` for Godot |
| [glTF-Validator](https://github.com/KhronosGroup/glTF-Validator) (Apache-2.0) | Gate for every export | Already used by `scripts/godot_asset_adapter.py` |
| [glTF-Transform](https://github.com/donmccurdy/glTF-Transform) (MIT) | Scriptable glTF edits and texture compression | Not tried |
| [VRM Add-on for Blender](https://github.com/saturday06/VRM-Addon-for-Blender) 4.10.3 (MIT) | VRM export, states Blender 2.93 to 5.2 | Not tried |
| [KTX-Software](https://github.com/KhronosGroup/KTX-Software) | GPU texture compression | Licence mix unread |
| [godot-vrm](https://github.com/V-Sekai/godot-vrm) | VRM and MToon in Godot | Community project, licence unstated by GitHub |

When Unreal is installed:

| Tool | Value | Notes |
| --- | --- | --- |
| [Epic's Claude Code plugin](https://github.com/EpicGames/unreal-engine-skills-for-claude-code-plugin) 3.1.2 (MIT) | Three skills (`unreal-mcp`, `create-toolset`, `unreal-skill`) over the editor's own MCP server | Needs a running 5.8 editor with the ModelContextProtocol and AllToolsets plugins. Its `execute_tool_script` runs arbitrary Python in the editor, and its README warns localhost is no trust boundary. Enable per project, not globally |
| Substrate Toon BSDF and Toon Profile | The first toon route to try | Experimental in 5.8. No open Unreal toon plugin was found in a primary repository |
| IK Retargeter foot-plane and morph-target split tools | New in 5.8 | From Epic's release notes |
| [VRM4U](https://github.com/ruyo/VRM4U) | VRM import, zips for UE 5.2 to 5.8 | GitHub reports no licence, its README says MIT |
| [OpenRigLogic](https://github.com/EpicGames/OpenRigLogic) (MIT) | MetaHuman rig logic, no Unreal dependency | Only with authored DNA files, so of little use for anime faces |
| [poly-hammer BlenderTools](https://github.com/poly-hammer/BlenderTools) (MIT) | Maintained Send to Unreal fork | No Blender 4.5 claim. Epic's own BlenderTools last released in 2023. Use only if glTF or FBX import falls short |

Skip for now: [Lore](https://github.com/EpicGames/lore) (0.12, on-disk formats may change, revisit after 1.0),
MetaHuman-DNA-Calibration (proprietary, Maya only), Blender Lab MCP (needs Blender 5.1), UniRig (CUDA), Unity's MCP (needs a
cloud project and a subscription). RealityScan, raddebugger, GLTFWebViewer, PythonSamples, deadline and
PixelStreamingInfrastructure have no use here. No official agent skill or MCP repository was found for Godot, OpenUSD or
Khronos, and none could be located for Houdini or Substance. Whether Unreal 5.8 runs well on an RX 9070 XT is still unknown.

Launcher fix, measured 1 November 2026: on a new account with launcher 20.3.x, Install Engine and + do nothing and the log says
`found 0 entitled apps`. Adding the free Game Animation Sample from the Samples tab and pressing Create project brought the engine list back
([forum report](https://forums.unrealengine.com/t/launcher-20-3-5-install-engine-and-do-nothing-0-entitled-apps-eula-never-shown/2840448)).
It needs the owner to accept the Fab EULA. Install error `DP-01` right after can be a timed-out Windows admin prompt (log: `Error Code 1223`),
not a real permissions fault.

Licences above are as stated on the pages read, not cleared. See each model's pin in `models/library.json` before use.
