# Which model family should restyle a finished picture? — 14 September 2026

The owner asked whether FLUX.1 dev, FLUX.2 Klein 9B, Z-Image Turbo or a wider LoRA search would beat the SDXL
route for "give this picture a different look, accurately". Facts measured on this PC (RX 9070 XT 16 GB, ROCm 7.2.1,
PyTorch 2.9.1, 32 GB RAM) or read from the model cards on this date; nothing here is licence clearance.

| Family | Installed here | Measured on this PC | Editing / restyle route | Licence | Verdict for restyling today |
|---|---|---|---|---|---|
| WAI v17 / Nova (SDXL Illustrious) + IP-Adapter + OpenPose + LoRAs | yes | 28–90 s per 1–1.5 MP image; face pass +18 s | img2img + ControlNet + style LoRAs (`restyle-wai`) | WAI terms unresolved; LoRAs per civitai flags | **The route that produced the owner's target finish** (`experiments/curated/style-pose-matrix/2026-09-14-restyle/`). Keep. |
| FLUX.2 Klein 4B fp8 | yes (`flux-2-klein-4b-fp8`) | 16–44 s per edit (character-reference pilot, 12 Sep) | native reference edit (`flux-edit`), up to 4 references; AniEdit LoRA adds anime style transfer from references | Apache-2.0 (base); AniEdit LoRA is FLUX.1-dev non-commercial | **Now carries the Restyle route** (`restyle-klein`, measured the same night: the picture as the single reference, the finish described in words plus a keep sentence and the source description, 6 steps, CFG 1, ~1.5 MP, 16–20 s warm; kept pose, wink, robe and throne; the style picture as a second reference washed it out, 2 MP changed the hair). AniEdit still untested (download in progress). |
| FLUX.2 Klein 9B | no | — | same as 4B, stronger | **non-commercial**; 24 GB+ recommended, 16 GB only at reduced resolution | The 24 GB figure is for bf16 (16.9 GB transformer + 15.3 GB encoder). As **fp8 (8.8 GB) with the fp8 Qwen3-8B encoder (8.1 GB) offloaded to host RAM it fits 16 GB**; the official fp8 repository is gated on Hugging Face (HTTP 401 without a login), the `unsloth/FLUX.2-klein-9B-GGUF` mirror is not (Q6_K 7.3 GB, Q8_0 9.3 GB). The owner set the non-commercial terms aside for their own experiments (14 Sep, night). Q6_K + encoder + AniEdit 9B v2 are downloading; not measured yet. |
| FLUX.1 dev | no | — | Kontext-era editing is FLUX.1-Kontext, not dev; dev is text-to-image | non-commercial | Superseded by FLUX.2 Klein for editing; slower; skip. |
| FLUX.2 dev Q4 GGUF | yes (18.7 GB) | not timed | — | non-commercial | Too large for 16 GB without heavy offload; skip for interactive use. |
| Qwen Image Edit 2511 Q4 + Lightning | yes | **672 s** per image (14 Sep) | instruction edit with 1–3 references (`qwen-1ref/2ref/3ref`), strong identity keeping | Apache-2.0 | Right tool for "change X, keep everything else" when 11 minutes per try is acceptable; not for iterating on a look. |
| Z-Image Turbo bf16 | yes (11.7 GB) | **178 s warm / 307 s cold** at 1024×1536, 15–23 s/it (model fills VRAM: 11.7 of 13.1 GB usable) | text-to-image only here; Fun ControlNet Union (pose/canny/depth/tile) exists; 100+ community anime LoRAs and an anime merge checkpoint; **Z-Image-Edit unreleased** | Apache-2.0 | Excellent prompt following and clean output, but no edit model yet and the installed file is the wrong variant for this card. The "few seconds" reports use fp8 (~6 GB) or GGUF with headroom. Worth one measured retry **after** installing the fp8 build; until then not a restyle route. |
| Krea 2 Turbo | yes | 986 s per 768×1152 (memory) | img2img polish (`krea-refine`) | Krea 2 community licence | Too slow to iterate. |

## What this means for the strategy

0. **Superseded the same night:** Klein 4B with the finish described in words became the first Restyle destination
   (`restyle-klein`); the points below are the state before that measurement and remain true for the SDXL recipe.
1. **Keep the SDXL route as the default Restyle** because it is the only one that has produced the owner's target
   finish here, and it is fast enough to iterate (about a minute and a half per attempt including the face pass).
2. **The style *picture* is a weak lever on SDXL**: the IP-Adapter board moved the palette, not the finish. The finish
   came from checkpoint + style LoRA + prompt terms. So "explore all the LoRAs" is the right next lever on this route:
   the seven Illustrious LoRAs installed on 14 September are the shortlist; Mishima Kurone and Momoko are in the recipe,
   Glossy / Detail enhancer / Konosuba untested on it.
3. **Klein 4B + AniEdit is the experiment that could change the strategy**: a reference-driven anime editor that runs in
   under a minute on this card and takes up to four references (style pictures) directly. It needs a download
   (AniEdit v2, 948 MB, civitai; non-commercial licence, NSFW in the training set) and one proving pass on the throne
   witch against the owner's target. Not started.
4. **Z-Image Turbo is not a shortcut yet**: no edit model, and the installed bf16 file is 10× too slow on this card.
   Installing the fp8 build (~6 GB) and re-timing is cheap and would tell whether Z-Image + ControlNet + an anime LoRA
   is a future route.
5. Two commercial notes stand regardless of quality: Klein 9B and FLUX.1 dev are non-commercial, and the artist-style
   LoRAs in the shipped recipe are the owner's call in HUMAN_TODO q-26.

Download facts measured the same night: Hugging Face and civitai transfers ran at 3.4 MB/s for a few minutes, then
0.25–0.5 MB/s through the Proton VPN tunnel for hours, with connection resets mid-file; `scripts/fetch-hf.py` and
`scripts/civitai-fetch.py` restart from zero, so the session resumed the partial files with `curl -C -` and verified the
SHA-256 before installing (scratchpad helpers; receipts in `.runtime/downloads/receipts.json`).

Sources read on this date: Thunder Compute's Z-Image Turbo guide (fp8 ~6 GB, bf16 ~12 GB, 2.3 s on a 4090);
Comfy-Org/ComfyUI issue 11190 (9070 XT: 43 s at 1024² on a ROCm nightly, corrupted output on Windows); Tongyi-MAI/Z-Image
README (Edit and Omni-Base unreleased, Apache-2.0); black-forest-labs FLUX.2-klein-9B card (non-commercial, ~29 GB VRAM
in bf16); civitai AniEdit (Flux 2 Klein) page; alibaba-pai Z-Image-Turbo-Fun-Controlnet-Union card; civitai
Z-Image-Turbo-Anime checkpoint page (Apache-2.0, fp8 AIO ~10 GB).
