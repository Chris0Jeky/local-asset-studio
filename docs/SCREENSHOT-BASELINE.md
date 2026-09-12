# Screenshot-resource baselines

This guide records a private screenshot's *textual resource labels* without copying its image or claiming to reproduce it. The two recipes create a new, fully clothed adult fantasy cartographer and lanternkeeper: navy travel coat, brass hardware, teal accent, compass and warm lantern. They are starting points for a fantasy character illustration pack, not art approval.

## Choose one lane

The labels describe two model architectures. They cannot be combined in one ComfyUI loader chain.

| Lane | Base model | Compatible style resource | Recipe |
| --- | --- | --- | --- |
| Illustrious / SDXL | WAI Illustrious SDXL v17.0 | Noirpopwave v1.0 at 1.0 | `wai-noirpopwave-screenshot-baseline` |
| Anima | Anima base v1.0 | Failleaf Anima Base at 0.5; sky02 v1.0 at 0.3; BunnySlop Anima v1 at 0.9 | `anima-screenshot-stack` |

Do not load WAI and Anima checkpoints together, and do not put an Anima LoRA into the WAI graph. A LoRA changes tensor shapes for the model family it was trained against; mixing families is a compatibility error, not a style blend.

## Source-page technical record

The supplied Civitai page is recorded as [image 134076830](https://civitai.red/images/134076830). Its image API record is marked NSFW, has dimensions 1872 x 2736 and `baseModel: Illustrious`. The authenticated metadata response lists these attached version IDs: `2696276`, `2883731`, `2945208`, `2974201`, `2978471`, and `2978487`.

They resolve to Noirpopwave v1.0, WAI v17.0, Anima base v1.0, Failleaf Anima Base, sky02 v1.0, and BunnySlop Anima v1. The image API exposes no prompt, sampler, scheduler, steps, CFG, seed, denoise, resource weights, or stage graph. Its mixed WAI and Anima version list may describe attachment or multi-stage provenance; it is not evidence that those checkpoints ran in one graph. This guide therefore keeps two compatible lanes and uses the supplied screenshot transcription for the resource weights.

## Resolved resource manifest

All paths are relative to the configured ComfyUI `models` directory. The four new LoRAs were downloaded by `scripts/civitai-fetch.py`; its ignored receipt records the matching listing hash.

| Resource | Version and source | File | SHA-256 | Status |
| --- | --- | --- | --- | --- |
| WAI Illustrious SDXL | Civitai model 827184, version 2883731; matching HF mirror | `checkpoints/waiIllustriousSDXL_v170.safetensors` | `f116b0c78ff441467b0cdc8f1936e1ed18ea31e9997c7b132b1b8db533f0bd04` | already installed; attached version ID resolves to the matching mirror hash |
| Anima base | Civitai model 2458426, version 2945208 | `diffusion_models/anima-base-v1.0.safetensors` | `bd43b7cffe1ed1153d9c41e7beb2f18cb1273eafbaa3af3edd6a173dc90a006e` | already installed with matching support encoder and VAE |
| Noirpopwave | Civitai model 2398033, version 2696276 | `loras/noirpopwave.safetensors` | `7c9e15de134f38d4deeb96148cb2e562291622ccc0f786ed85485b9de3c4f044` | installed; Illustrious only; trigger `noirpopwave` |
| Failleaf Style for Anima | Civitai model 2648711, version 2974201 | `loras/Failleaf_Anima_Base_lora.safetensors` | `d74e2709313c1c84015091be2bba7c503dbe0abdf5be093896c289ae1c07ff2b` | installed; Anima only; trigger `@failleaf` |
| sky02 Light and shadow | Civitai model 2652568, version 2978471 | `loras/sky02Light.safetensors` | `bdb6d406d864f58db1de9fe8c11f8a2f05be347639c6ba7f68ad2ce897e21b9a` | installed; Anima only |
| BunnySlop AI Style | Civitai model 2613391, version 2978487 | `loras/BunnySlop_Anima.safetensors` | `e34c56d780dc86d232e06228ecf34699a634713969fa5fa15fe0dda9eac4e988` | installed; Anima v1; the listing is marked NSFW, but this recipe requests a clothed adult |

The source image resolves the previously truncated label as **Failleaf**, with two consecutive `l` characters after `fai`: `Failleaf Style for Anima`. The reported strengths are a source transcription, not an author recommendation: Noirpopwave 1.0, Failleaf Anima Base 0.5, sky02 0.3 and BunnySlop Anima v1 0.9.

## First render

Open **Workflow Lab**, select the recipe, and keep the supplied seed and `832 x 1216` size for the first one-image run. This is a modest portrait canvas and deliberately avoids upscale, detailer, multi-seed or multi-model work. Nothing submits until **Generate** is pressed.

For the WAI lane, use 24 steps, CFG 6, Euler ancestral and the normal scheduler. The Noirpopwave trigger is already in the positive prompt and its LoRA slot is 1.0.

For the Anima lane, use 30 steps, CFG 4, Euler ancestral and the simple scheduler. Failleaf, sky02 and BunnySlop occupy the first three slots at 0.5, 0.3 and 0.9. The remaining three slots are zero and are pruned before submission.

## Learn by changing one control

Keep the prompt and seed fixed while comparing these deliberate changes:

1. Render the supplied WAI recipe, then set Noirpopwave to `0` for the control. This shows the WAI base without that style LoRA.
2. Restore Noirpopwave to `1.0`; do not add Anima resources to that graph.
3. Render the supplied Anima recipe, then set BunnySlop to `0` while keeping Failleaf at `0.5` and sky02 at `0.3`. This shows the lighting and Failleaf combination without the heavier style contribution.
4. Restore BunnySlop to `0.9`. A later ablation can set Failleaf to `0`, keeping the other two slots unchanged.

Record the prompt ID and choose the preferred result before any correction pass. A successful render proves only that a particular settings combination executed. It does not establish likeness to the private reference, acceptable anatomy, ownership, licensing clearance or acceptance of the artwork.

## Terms and privacy

The model registry records the listing metadata that was available on 12 September 2026. WAI is a community mirror with no declared licence in its card. The Anima model weights use CircleStone Labs' non-commercial model licence while its card says generated outputs may be used commercially; third-party LoRA terms remain separate. Read each linked listing before commercial use. The source artwork was not opened or stored for this work.
