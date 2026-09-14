# Workflow Lab

Open **Asset Studio** on the desktop, or visit **http://127.0.0.1:8191**.
The five in-page views are **Create**, **Workspace**, **Experiments**, **Models & folders** and **Workflow lab**;
the header also links the separately served **Scene editor**, **Voice baseline**, **Prompt Lab**, **Review desk** and
**Workflow Studio** pages. The catalog has 66 presets across 14 categories (13 September 2026), including the 20
Workflow Lab additions for manga, modern anime, video, geometry and textured 3D; each addition has an editable native
ComfyUI graph, and `presets/recipes.json` separately holds 30 named starting points.

## Start with these routes

| Intent | Recipe | A useful comparison |
|---|---|---|
| Clean manga linework | Manga Line Art | Three seeds, then LoRA strength 0.6 / 0.8 / 1.0 at the winning seed |
| Printed manga texture | Manga Ink and Screentone | Keep `m4ng41nk`; compare ink coverage and screentone at a fixed composition |
| Dramatic lighting | Cinematic Anime Lighting | Compare the adapter against strength 0; it uses the SDXL base family |
| Modern anime illustration | Anima Aesthetic 1.1 | Descriptive prose plus tags, 20 / 30 / 36 steps, CFG near 4 |
| Retro anime | Krea 2 Retro Anime | Official free adapter on Turbo FP8; compare adapter strength 0 and 1 |
| Animate an illustration | Wan 2.2 Animate Image | Start with **Quick diagnostic**; use **Balanced**, **Quality** (81 frames opt-in), or **Canonical upstream** deliberately |
| Geometry from a reference | Hunyuan3D Draft | Inspect silhouette in the GLB viewer, then try Detail for denser geometry |
| Textured 3D | TRELLIS.2 Automatic Cutout | Isolate one subject; inspect all sides, seams, materials, and topology |

These are selected starting points, not a universal leaderboard. Small adapters
are matched to their documented base family. Do not mix SDXL, Illustrious, Anima,
Krea, or video LoRAs simply because every file ends in `.safetensors`.
See CURRENT_STATE.md for the actual execution evidence and remaining limitations.

## Audition, choose, finish

1. Choose a recipe and write a specific brief. Describe the subject, composition,
   materials, light, and one intended action for video. Keep negative prompts short.
2. Click **3-seed audition**. This only fills the variation count; **Generate** is
   the separate action that starts the jobs. Batches run serially on the local GPU.
3. **Compare** two image outputs. Choose a composition, keep its seed, and change
   one factor such as adapter strength. Extra steps cannot reliably repair anatomy.
4. Click **Use as reference** after selecting a refinement or editing recipe.
   **Animate** attaches the image to Wan. **Make 3D** attaches it to TRELLIS with
   automatic foreground removal. These actions prepare the next stage; they do not run it.
5. Save a named setup for quick recall. Export **Recipe** with the final output.
   It includes exact graphs, seeds, prompt IDs, and output descriptors.

Recipe imports compare the embedded graph with the current preset. If the preset
has changed, import refuses to silently substitute the new graph. You can open the
embedded workflow in ComfyUI or deliberately start from the current preset.
Model weights and uploaded reference images are separate local dependencies;
the JSON does not bundle them. Identical seeds alone do not promise identical
images across different models, runtime versions, or GPU implementations.

Wan 2.2 I2V has an offline diagnostic action on recorded video assets. It reports
the source and requested geometry, the installed center-crop/resample behavior,
model hashes, prompts, canonical upstream graph differences and sampled frames
without submitting a new job. The route records engine execution separately from
creative review or quality acceptance. See [WAN22-I2V-DIAGNOSTICS.md](WAN22-I2V-DIAGNOSTICS.md)
for the control-case contract and the current forensic record.

## What goes in which folder?

The configured model root is `C:\AI\ComfyUI_windows_portable\ComfyUI\models`.
Use **Models & folders** to copy an exact path, open Explorer, inspect installed
weights, or install a pinned curated asset. Downloads verify size and SHA-256 before
the final filename becomes visible to ComfyUI. They preserve 20 GiB of working headroom.

| Folder | Purpose |
|---|---|
| `checkpoints` | Bundled image models; the current native Hunyuan loader also reads here |
| `diffusion_models` | Split image, video, and 3D diffusion weights |
| `text_encoders` | The matching prompt encoder |
| `vae` | Pixel, video, audio, shape, or texture decoders |
| `loras` | Family-specific style and capability adapters |
| `clip_vision` | Reference-image encoders such as DINO |
| `background_removal` | BiRefNet foreground extraction |
| `upscale_models` | Learned image upscalers such as ESRGAN |
| `latent_upscale_models` | Optional latent video upscalers used by community workflows |
| `ipadapter` | IP-Adapter reference-identity weights, paired with a `clip_vision` encoder |
| `ultralytics` | Ultralytics face, hand and person detectors under `bbox/` and `segm/` |
| `inpaint` | Inpaint heads and models such as the Fooocus head and MAT Places512 |
| `vae_approx` | The small TAESD/TAEF1 decoders ComfyUI uses for live latent previews |

Whether a pinned file installs automatically depends on its **suffix, not its folder**. Only
`.safetensors` is fetched and published by the installer; `.gguf`, `.pth`, `.pt` and `.onnx` pins are
**pin only**. `library.json` records their size, SHA-256 and terms so **Models & folders** reports
presence, but the installer refuses them and the card shows a disabled *Copy in by hand* button.
Today that is the detectors in `ultralytics`, the Fooocus head in `inpaint`, the two upscaler `.pth`
files, and the three GGUF backbones — which live in `diffusion_models` and `text_encoders`, not in the
four folders above. `ipadapter` and `vae_approx` currently hold only `.safetensors`. A pin with no
curated source URL is refused the same way while its file is missing, and verifies once it is there.

A weight whose suffix is outside that set is not pinned at all and appears nowhere in the Models view.
`inpaint/inpaint_v26.fooocus.patch` is the live example: installed, 1.3 GB, and deliberately unpinned.

Your downloaded `minimax_h3_fl2va_pruned_int8_convrot.safetensors` belongs in
`models\diffusion_models`. The configured PC uses an NTFS hard link to the
checksum-verified Downloads copy, so it does not consume a second 20 GB.
The H3 text encoder, two VAEs, and Turbo adapter are separate required files.

An interrupted download keeps its `.part` file. A subsequent explicit install can
resume only if the server supports byte ranges and the final SHA-256 matches.
An interrupted installer process may leave `.runtime/downloads/install.lock`.
Check that its recorded PID is no longer an installer before removing that lock.
Existing differing final files are preserved rather than overwritten.

## Your Civitai references

The [image you linked](https://civitai.red/images/141483065) records Krea2 Raw INT8
with NIJISIS Krea2 V.1, Euler/simple, 8 steps, CFG 1, and 768×1152. The NIJISIS LoRA
requires 1,000 Buzz. You chose free alternatives; no Buzz was spent.
The installed [official Krea retro-anime LoRA](https://huggingface.co/Comfy-Org/Krea-2)
on Turbo FP8 is a different recipe. It does not reproduce NIJISIS or imply identical quality.
FP8 was selected because the upstream issue tracker contains Radeon INT8 ConvRot
failure reports; only local execution can establish compatibility for this machine.

[Seed Hunter 1.6](https://civitai.red/models/2881362/minimax-seed-hunter-workflow-latent-upscaler-seamless-video-continuation-speedups)
combines low-resolution auditions, chosen-latent upscaling, continuation, audio,
and interpolation. Its additional custom-node dependencies include
[obvpm](https://github.com/obvpm/comfyui-obvpm),
[H3 latent upscaling](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler),
[H3 Prompt IDE](https://github.com/ethanfel/ComfyUI-H3-Prompt-IDE), and
[WhatDreamsCost](https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI).
The original **v1.6 JSON is downloaded and checksum-verified**, using the public
[no-credit endpoint](https://civitai.com/api/download/models/3293757?fileId=3193862).
Find it in ComfyUI's **Studio Workflow Lab → Community** folder, or in
`workflows/community`. The Studio inspector examined 154 nodes and found 24 missing
node classes and three additional weights; the adjacent inspection JSON records
the full list. The community custom-node code was not installed and the graph was
not executed. Native H3 preview, base-quality, first-image and first/last-image
variants are also available. H3's runtime incompatibility still applies.

**H3 on this PC:** two accepted tiny trials ended in a Windows access violation
while loading the NVFP4 text encoder; a fresh process with `--disable-mmap` did not
fix it. No video was produced. The workaround was reverted, both prompt IDs were
retained, and no uncertain job was automatically repeated. The local config blocks
accidental H3 submissions through Studio while keeping its files and visual graphs.
Revisit with a verified compatible encoder/runtime; use Wan for the active video route.
The local compatibility work is tracked in
[issue 18](https://github.com/Chris0Jeky/local-asset-studio/issues/18).
The owner confirmed eligible-territory use for H3. That does not settle every other
license condition or the rights to input media.

## 3D expectations

Hunyuan produces geometry. It does not promise clean UVs, PBR materials, topology,
rigging, or a game-ready asset. Inspect the silhouette and underside in the viewer,
then finish in Blender. Draft and Detail decode at different geometry resolutions.

The TRELLIS route uses native Torch nodes, a 512 shape stage and 1024 texture bake.
It preserves separate structure, shape and texture sampling from the bundled
ComfyUI template. It omits the template's heavy 1536 cascade, 4K bake, remeshing,
AO and normal-map passes. The RGBA variant needs transparent foreground; the
automatic variant uses BiRefNet. This is an experimental textured draft route.
Interactive previews use a locally vendored, integrity-checked model-viewer bundle.

Both TRELLIS variants completed locally after the small
[CPU UV compatibility patch](../runtime-patches/README.md). They retained an
invented ground plane even with a valid matte, so they are not clean asset exports
by themselves. The transparent-reference preset now starts from a real cutout PNG;
an image merely being called RGBA does not guarantee useful transparency.

The Workflow Lab page includes a trimmed, lighter lantern with its PBR textures.
Use `scripts/finish-generated-mesh.py` through Blender to repeat the finishing
step on a new file. Bottom trimming is explicit and can remove wanted geometry
or leave an open cut; inspect it from every side. Example on the configured PC:

```powershell
& 'C:/AI/blender-4.5.13-windows-x64/blender.exe' --background --python scripts/finish-generated-mesh.py -- --input 'C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio/Trellis2-rgba_00001_.glb' --output 'C:/AI/finished/lantern-preview.glb' --target-faces 80000 --trim-bottom-fraction 0.035
```

Without `--trim-bottom-fraction`, it only reduces geometry. It refuses to overwrite
an existing export and writes a sidecar with source hash, settings and face counts.
The original mesh is preserved. This Blender step is a separate finishing command;
the Generate button produces the full native GLB.

## Edit the full workflows

The 20 new visual graphs are installed in ComfyUI's workflow browser under
**Studio Workflow Lab**. The repository copies are in `workflows/comfyui`.
Select **Download visual workflow** in Studio and open that JSON in ComfyUI if
using another machine. The **Open ComfyUI** link opens its editor; it does not
automatically replace your currently open user graph.

For a community JSON, use **Workflow lab → Inspect workflow JSON** first. This
reports saved model filenames and missing node classes without executing the graph
or installing code. Bypassed nodes are included; dynamic selections may be absent.
Node presence and model-file presence do not prove GPU compatibility or output quality.

## Sources and model terms

- [Anima](https://huggingface.co/circlestone-labs/Anima): CircleStone non-commercial
  weight terms; generated outputs have separate terms in the model card.
- [Krea 2](https://huggingface.co/Comfy-Org/Krea-2): Community terms, official Turbo
  and retro-anime adapter. [Radeon INT8 report](https://github.com/Comfy-Org/ComfyUI/issues/15084).
- [LineAni](https://huggingface.co/artificialguybr/LineAniRedmond-LinearMangaSDXL-V2),
  [screentone](https://huggingface.co/strkyyy/manga-ink-screentone),
  [cinematic lighting](https://huggingface.co/ntc-ai/SDXL-LoRA-slider.cinematic-lighting).
- [Wan 2.2 native guide](https://docs.comfy.org/tutorials/video/wan/wan2_2),
  [official package](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged).
- [MiniMax native guide](https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native),
  [H3 terms](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE).
- [Hunyuan 2.1](https://huggingface.co/Comfy-Org/hunyuan3D_2.1_repackaged),
  [TRELLIS.2](https://huggingface.co/Comfy-Org/TRELLIS.2),
  [DINO-NAF encoder](https://huggingface.co/Comfy-Org/Pixal3D),
  [BiRefNet](https://huggingface.co/Comfy-Org/BiRefNet).

Hashes, exact pinned revisions/URLs, destination paths and asset sizes are in
`models/library.json`. Successful generation and art acceptance remain separate;
[HUMAN_TODO.md](../HUMAN_TODO.md) holds the optional creative choices.
