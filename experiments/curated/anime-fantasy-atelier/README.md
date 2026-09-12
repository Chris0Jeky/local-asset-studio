# Anime & Fantasy Atelier — execution samples (12 September 2026)

Agent-run proving generations for the atelier overhaul. Originals stay under the ComfyUI `output/`
folder (paths and SHA-256 in `execution-evidence.json`); `examples/anime-fantasy-atelier/*.jpg` are
quality-88 JPEG copies for viewing. Every run here was inspected by eye; none is an art approval.

| Route | Sample | Settings | Wall time |
|---|---|---|---|
| Krea 2 Turbo + NIJISIS @1.0 (ComfyUI probe, before the preset existed) | [witch-nijisis-baseline](../../../examples/anime-fantasy-atelier/witch-nijisis-baseline.jpg) | 768x1152, 15 steps, euler_ancestral/simple, cfg 1, seed 281715418 | 986.6 s |
| Krea 2 Turbo + TextFusion @1.0 + Niji Sweet Spot @1.0, prompt `@NJSW33T, …` (probe) | [witch-target-stack](../../../examples/anime-fantasy-atelier/witch-target-stack.jpg) | same | 941.2 s |
| same stack + 4-step distill LoRA @0.85 (probe) | [witch-target-stack-4step](../../../examples/anime-fantasy-atelier/witch-target-stack-4step.jpg) | 4 steps, otherwise same | 270.9 s |
| 4-step probe `witch-airy-watercolor-short-4step`: fal-krea2-airy-anime-watercolor, krea2_turbo_4step_rank_64_lora_comfyui; euler_ancestral/simple | [witch-airy-watercolor-short-4step](../../../examples/anime-fantasy-atelier/witch-airy-watercolor-short-4step.jpg) | 768x1152, 4 steps, cfg 1, seed 281715418 | 170.43 s |
| 4-step probe `witch-nijisis-4step`: NIJISIS_KREA_2_krea2_3274861_epoch_8, krea2_turbo_4step_rank_64_lora_comfyui; euler_ancestral/simple | [witch-nijisis-4step](../../../examples/anime-fantasy-atelier/witch-nijisis-4step.jpg) | 768x1152, 4 steps, cfg 1, seed 281715418 | 200.54 s |
| 4-step probe `witch-target-ersde-4step`: Krea2_TextFusion_Refusal_Reduction, Niji_Sweet_Spot_Krea2_v2A, krea2_turbo_4step_rank_64_lora_comfyui; er_sde/simple | [witch-target-ersde-4step](../../../examples/anime-fantasy-atelier/witch-target-ersde-4step.jpg) | 768x1152, 4 steps, cfg 1, seed 281715418 | 180.4 s |
| 4-step probe `witch-target-plus-baroque-oil-4step`: Krea2_TextFusion_Refusal_Reduction, Niji_Sweet_Spot_Krea2_v2A, fal-krea2-baroque-dreamscape-oil, krea2_turbo_4step_rank_64_lora_comfyui; euler_ancestral/simple | [witch-target-plus-baroque-oil-4step](../../../examples/anime-fantasy-atelier/witch-target-plus-baroque-oil-4step.jpg) | 768x1152, 4 steps, cfg 1, seed 281715418 | 190.32 s |
| `krea-anime-atelier`, variant "4-step audition" (Studio job) | [krea-anime-atelier-4step](../../../examples/anime-fantasy-atelier/krea-anime-atelier-4step.jpg) | authored prompt, 4 steps | 197.0 s |
| `krea-style-lab`, variant "4-step audition" (Studio job): fal-krea2-airy-anime-watercolor, krea2_turbo_4step_rank_64_lora_comfyui | [krea-style-lab-4step](../../../examples/anime-fantasy-atelier/krea-style-lab-4step.jpg) | 1024x1024, 4 steps, euler/simple | 207.1 s |
| `wai` "Fantasy portrait" (Studio job) | [wai](../../../examples/anime-fantasy-atelier/wai-fantasy-portrait.jpg) | 832x1216, 30 steps, cfg 5 | 26.2 s |
| `noob` "Fantasy portrait" (Studio job) | [noob](../../../examples/anime-fantasy-atelier/noob-fantasy-portrait.jpg) | 832x1216, 28 steps, cfg 5.5 | 28.2 s |
| `anime` (Animagine 4) "Fantasy portrait" (Studio job) | [animagine](../../../examples/anime-fantasy-atelier/anime-fantasy-portrait.jpg) | 832x1216, 28 steps, cfg 5 | 30.2 s |
| `pony` "Fantasy portrait" with CLIPSetLastLayer -2 (Studio job) | [pony](../../../examples/anime-fantasy-atelier/pony-fantasy-portrait.jpg) | 832x1216, 30 steps, cfg 6 | 30.2 s |
| `krea-anime-atelier` with the FULL target stack: TextFusion @1.0 + Niji Sweet Spot @1.0 + koukouya @1.0 (Studio job, first run with koukouya installed) | [krea-target-stack-koukouya](../../../examples/anime-fantasy-atelier/krea-target-stack-koukouya.jpg) | 832x1248, 15 steps, euler_ancestral/simple, cfg 1, seed 20260912 | 827.6 s |
| `anime-detail-fix` on the NoobAI fantasy portrait the owner flagged for six fingers (Studio job; Impact Pack FaceDetailer face pass then hand pass, WAI v17 repaint) | [anime-detail-fix-noob-hands](../../../examples/anime-fantasy-atelier/anime-detail-fix-noob-hands.jpg) | 832x1216 input, 24 steps, dpmpp_2m/karras, cfg 5, denoise 0.4 face / 0.45 hand, seed 2026091201 | 36.2 s |
| `krea-refine` on the krea-style-lab fox shrine the owner said lost detail and had morphed fox faces (Studio job; Qwen-VAE encode, 4-step distill LoRA, TextFusion + Niji Sweet Spot) | [krea-refine-style-lab-foxes](../../../examples/anime-fantasy-atelier/krea-refine-style-lab-foxes.jpg) | 1024x1024 input, 4 steps, euler/simple, cfg 1, denoise 0.35, seed authored | 233.2 s |
| `anima-artist-stack` graph as a direct ComfyUI probe with anima-aesthetic-v1.1 substituted for the still-downloading base v1.0 and the ke-ta/kieed slots removed (xilmo 0.7, huashijw 0.6, koukouya 0.3, NEWANIMASTYLE 1.0) | [anima-stack-aesthetic11-4adapters](../../../examples/anime-fantasy-atelier/anima-stack-aesthetic11-4adapters.jpg) | 832x1216, 30 steps, euler_ancestral/simple, cfg 4, seed 975436216244440 | 35.0 s |
| `anima-artist-stack` graph as a direct ComfyUI probe with anima-aesthetic-v1.1 substituted for the still-downloading base v1.0, ALL SIX adapters at the authored strengths (kieed is LyCORIS) | [anima-stack-aesthetic11-6adapters](../../../examples/anime-fantasy-atelier/anima-stack-aesthetic11-6adapters.jpg) | 832x1216, 30 steps, euler_ancestral/simple, cfg 4, seed 975436216244440 | 25.0 s |

The Krea target-stack probes reproduce the owner's reference image settings (civitai image 142028671:
15 steps, Euler a, simple, cfg 1) with two of its three LoRAs; the third (koukouya style) is not
installed. The 4-step distill LoRA gave results on par with 15 steps at 3.5x the speed and is the
recommended audition path on this card.

One probe (`witch-nijisis-4step`, prompt `af39c7de-…`) failed with a HIP out-of-memory error at
768x1152 after several runs in one ComfyUI process; the secondary exception killed ComfyUI's prompt
worker and the process was restarted. It is recorded as a failure, not repeated silently.

Studio jobs prove the catalog bindings and the strength-0 slot pruning: the submitted graphs in the
`*-recipe.json` files contain no zero-strength LoRA loader, and Pony's clip-skip node was rewired to
the checkpoint. SDXL timings are at 832x1216 with warm model caches; Krea timings include LoRA
patching. Timings are not benchmarks.
