# Wan 2.2 I2V diagnostics

This is the source-bound contract for Studio's offline I2V diagnostic. It reads
an existing recorded video and its job recipe; it never calls ComfyUI's
`/prompt` endpoint and does not regenerate a job.

## Current forensic record

The visually failed recording is Studio job
`9bf10278-d1be-404d-b314-3b9b741909ce`, ComfyUI prompt
`9deb42bb-55f4-4187-bd30-0a09d8323513`, and output
`C:\AI\ComfyUI_windows_portable\ComfyUI\output\Studio\Wan22-i2v_00003_.mp4`.
The engine reported completion, while the asset review is `rejected`; those
states are intentionally separate. Its recorded graph is in the external run
directory `experiments/runs/9bf10278-d1be-404d-b314-3b9b741909ce/` as
`state.json`, `recipe.json` and `workflow.json`.

The submitted controls were 512x512, 81 frames, 20 steps, CFG 5, seed
2026091103, `uni_pc` / `simple`, denoise 1 and shift 8. The source named by the
graph is the uploaded 832x1248 PNG whose SHA-256 is
`6d37a921b1e884ca9b4cc8901e30d73a43217fbce3eeb937e6f16657d3b105e6`.
The exact graph records `wan2.2_ti2v_5B_fp16.safetensors`,
`wan2.2_vae.safetensors` and `umt5_xxl_fp8_e4m3fn_scaled.safetensors`.

The diagnostic sampled frames 0, 1, 4, 8, 16, 32, 48, 64 and 80. The first
decoded frame is recognizable within the square crop; multi-colour/mosaic
smearing is visible by frame 2 and is obvious by frame 4, then the subject
collapses into painterly fragments. This is temporal degradation after an
initially usable frame, not corruption that is already fully present at frame 0.
The contact sheet and preprocessed first frame are generated under the job's
external diagnostics directory and are also linked by the asset dialog.

Historical job `460ed2dd-1a6b-45e1-9374-ac130595517c` maps to Studio job
`e33116f1-7253-451a-8d41-f20a99aca808` and output
`Wan22-i2v_00001_.mp4`: 512x768, 33 frames, 20 steps, 1.375 seconds. Its
sampled frames retained the swordswoman, umbrella, rain and neon-street
composition with only a gentle drift. That is objective sampled coherence, not
a claim of finished-art acceptance; the old execution badge is not used as a
quality assertion.

The canonical installation control was then submitted once as Studio job
`e2799ee8-db57-4e0b-b71a-59823526ac4c`, ComfyUI prompt
`314092cf-4bcc-4d5f-a1b5-8bf99b3403fd`, using the checked official source
`fennec_girl_hug.png` (SHA-256
`ec0cbf7d8a81eb6fbfda1309b49a644f6cf123ccf5036197e8592ba205f67d71`) and the
canonical 1280x704/41-frame/30-step settings. It ran for about 995.6 seconds,
completed sampling through `KSampler`, and failed at `VAEDecode` with
`torch.OutOfMemoryError`: the HIP allocator was asked for 18.56 GiB on the
15.92 GiB RX 9070 XT. ComfyUI's history ends in the Wan VAE `Conv3d` path, the
executed-node list excludes `VAEDecode`, and no output was produced. The exact
history, submitted graph, request, queue snapshots and system stats are
preserved in `.runtime/i2v-diagnostics/2026-09-13-run-A/`.

This is a demonstrated decode-capacity limit for the current machine, not
evidence of a bad prompt, source image or model file. The installed Wan VAE
shape formula gives Run A a latent shape of `[1,48,11,44,80]`, versus
`[1,48,9,48,32]` for the coherent historical run; its spatial area is 2.29x
larger. Source inspection also shows that the automatic 3D tiled fallback
keeps all 11 temporal latent slices and sizes a 32x32 latent spatial tile for
this case, yet the final decoder convolution still requests 18.56 GiB. A
fragmentation setting alone is therefore not a proven remedy. Per the stop
rule, no Run B was submitted.

## Installed preprocessing contract

In the installed ComfyUI `v0.35.0` checkout, `Wan22ImageToVideoLatent` calls
`comfy.utils.common_upscale(start_image, width, height, "bilinear", "center")`
before `vae.encode`. `common_upscale` compares aspect ratios, center-crops the
original tensor, then calls `torch.nn.functional.interpolate` with bilinear
mode. Therefore an 832x1248 source requested at 512x512 is cropped to the
center 832x832 region (rows 208 through 1039 inclusive as pixels; crop box
`[0,208,832,1040]`) and then bilinearly resampled to 512x512. It does not
stretch the full source and does not letterbox it. Studio renders a portable
Pillow preview of that exact geometry and labels it as a parity render rather
than claiming byte-for-byte PyTorch pixels.

The installed implementation is recorded by the report with the ComfyUI Git
head and hashes for `comfy_extras/nodes_wan.py` and `comfy/utils.py`. At the
time of this record the runtime was Python 3.12.10, PyTorch 2.9.1+rocm7.2.1,
frontend 1.51.10, `comfy-kitchen` 0.2.33 and an AMD Radeon RX 9070 XT.

## Canonical comparison

The reference is ComfyUI's [official Wan 2.2 5B I2V workflow](https://github.com/comfyanonymous/ComfyUI_examples/blob/master/wan22/image_to_video_wan22_5B.json).
The checked source image is the companion
[fennec_girl_hug.png](https://github.com/comfyanonymous/ComfyUI_examples/blob/master/chroma/fennec_girl_hug.png).
The downloaded workflow hash used for this comparison is
`2b1784c9d6ecf03462651d6e8ded7b5cc5e18047e9eb5e2a885fb6c89c5ac515`.

Studio and upstream use the same Wan diffusion model, UMT5 encoder, Wan VAE,
`ModelSamplingSD3` shift 8, `uni_pc`, `simple`, denoise 1 and CFG 5. The
semantically relevant differences are:

| Concern | Studio failed job | Official quick-test control |
|---|---|---|
| source | uploaded portrait 832x1248 | `fennec_girl_hug.png`, 1280x704 landscape |
| target | 512x512, causing a centered portrait crop | 1280x704, matching the official source shape |
| steps | 20 | 30 |
| frames | 81 | 41 in the quick-test workflow; upstream note recommends 121 for the full reference case |
| positive | Studio motion/character-preservation brief | `a cute anime girl with fennec ears and a fluffy tail walking in a beautiful field` |
| negative | Studio English artifact/motion negative list | official Chinese quality/artifact/static-scene negative list |
| output | Studio `SaveVideo` MP4 adapter | official visual graph saves WEBP and WEBM |

No separate vision encoder or custom Wan node was silently substituted. The
current Studio graph still uses the three exact filenames above. The report's
semantic diff includes node classes, literal inputs and normalized links, so
changes to sampler, scheduler, shift, prompts, source, dimensions, frame
length, steps or output adapter remain visible.

## Preset architecture

The preset exposes explicit `Quick diagnostic`, `Balanced`, `Quality` and
`Canonical upstream` modes. Quick diagnostic is the default and uses a short
17-frame portrait-capable validation shape. Balanced uses 33 frames. Quality
uses 81 frames only when selected and warns that it is a higher-cost Studio
deviation. Canonical upstream uses the official model/settings and 1280x704,
41-frame quick-test shape; the Studio MP4 saver is the deliberate adapter.

For authored resolution pairs, Studio reads the uploaded source dimensions and
swaps the pair's orientation before binding it. Wan's remaining aspect-ratio
behavior is reported explicitly as a centered crop followed by bilinear
resampling. Runs are labeled as execution records; neither a mode nor a green
engine completion implies visual quality acceptance.

## Evidence boundary

Model records include file size, SHA-256, the matching `models/library.json`
pin and a safetensors container-header/data-offset check. These checks establish
identity and basic file integrity, not model licensing, GPU compatibility or
art quality. A diagnostic contact sheet establishes sampled-frame behavior only;
it does not replace a human review of the entire clip.
