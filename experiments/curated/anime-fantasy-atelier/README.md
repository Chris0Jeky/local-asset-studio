# Anime & Fantasy Atelier — execution samples (12 September 2026)

Agent-run proving generations for the atelier overhaul. Originals stay under the ComfyUI `output/`
folder (paths and SHA-256 in `execution-evidence.json`); `examples/anime-fantasy-atelier/*.jpg` are
quality-88 JPEG copies for viewing. Every run here was inspected by eye; none is an art approval.

| Route | Sample | Settings | Wall time |
|---|---|---|---|
| Krea 2 Turbo + NIJISIS @1.0 (ComfyUI probe, before the preset existed) | [witch-nijisis-baseline](../../../examples/anime-fantasy-atelier/witch-nijisis-baseline.jpg) | 768x1152, 15 steps, euler_ancestral/simple, cfg 1, seed 281715418 | 986.6 s |
| Krea 2 Turbo + TextFusion @1.0 + Niji Sweet Spot @1.0, prompt `@NJSW33T, …` (probe) | [witch-target-stack](../../../examples/anime-fantasy-atelier/witch-target-stack.jpg) | same | 941.2 s |
| same stack + 4-step distill LoRA @0.85 (probe) | [witch-target-stack-4step](../../../examples/anime-fantasy-atelier/witch-target-stack-4step.jpg) | 4 steps, otherwise same | 270.9 s |
| `krea-anime-atelier`, variant "4-step audition" (Studio job) | [krea-anime-atelier-4step](../../../examples/anime-fantasy-atelier/krea-anime-atelier-4step.jpg) | authored prompt, 4 steps | 197.0 s |
| `wai` "Fantasy portrait" (Studio job) | [wai](../../../examples/anime-fantasy-atelier/wai-fantasy-portrait.jpg) | 832x1216, 30 steps, cfg 5 | 26.2 s |
| `noob` "Fantasy portrait" (Studio job) | [noob](../../../examples/anime-fantasy-atelier/noob-fantasy-portrait.jpg) | 832x1216, 28 steps, cfg 5.5 | 28.2 s |
| `anime` (Animagine 4) "Fantasy portrait" (Studio job) | [animagine](../../../examples/anime-fantasy-atelier/anime-fantasy-portrait.jpg) | 832x1216, 28 steps, cfg 5 | 30.2 s |
| `pony` "Fantasy portrait" with CLIPSetLastLayer -2 (Studio job) | [pony](../../../examples/anime-fantasy-atelier/pony-fantasy-portrait.jpg) | 832x1216, 30 steps, cfg 6 | 30.2 s |

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
