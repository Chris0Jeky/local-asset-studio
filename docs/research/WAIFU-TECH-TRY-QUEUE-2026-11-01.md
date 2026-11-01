# Frontier try-queue, 1 November 2026

A web scan of anime-capable models, reference methods and 3D-adjacent tools released mostly August to November 2026,
ranked by value per hour on this PC (RX 9070 XT 16 GB, ROCm, no CUDA). Every fit is a hypothesis until it runs here.
Reddit and Civitai pages returned nothing usable, so nothing below rests on them alone.

| # | Candidate | What it uniquely adds | Status here |
| --- | --- | --- | --- |
| 1 | [Character sheet LoRAs](https://huggingface.co/Alissonerdx/CharacterSheet) (TripleView, Klein 9B) | Front, side and back from one picture. Stock LoRA loader, no custom node | **Shipped** as `character-sheet-klein-9b`. Clean anime turnarounds on white with head and feet level. Agent-inspected only |
| 2 | Anima Turbo v1.1 (in [`circlestone-labs/Anima`](https://huggingface.co/circlestone-labs/Anima)) | CFG 1 at 8 to 12 steps. One blog reports about 4x speed with the reference adapter, only at `ref_guidance` 1.0 | Downloading; transfer is slow |
| 3 | [See-through](https://github.com/shitagaki-lab/see-through) (Apache-2.0, SIGGRAPH 2026) | One anime image to up to 23 RGBA layers in a PSD. README names a ROCm wheel | Not tried. Needs its own environment, not the shared runtime |
| 4 | [Anima-LLLite](https://huggingface.co/kohya-ss/Anima-LLLite) | Masked inpainting and line-art control for Anima, which has had neither | Not tried. Node is marked experimental |
| 5 | [Anima Role Ref KV](https://huggingface.co/AnticPan/Anima-Role-Ref-KV) (26 October) | A rival one-reference method, cached once | Not tried. `scripts/identity_score.py` can now settle it head to head |
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

Licences above are as stated on the pages read, not cleared. See each model's pin in `models/library.json` before use.
