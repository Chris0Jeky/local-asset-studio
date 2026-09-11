> Migrated research snapshot from 11 September 2026. Use [Start here](../START-HERE.md) and [current state](../../CURRENT_STATE.md) for the new repository. Original workspace commands below are historical.

# Experimenting with your local image studio

11 September 2026. There are 20 saved ComfyUI workflows. Multiple model families have executed on this RX 9070 XT with 16GB VRAM and 32GB RAM. The future experiments below are separate from those proven runs. Long batch times are acceptable.

## Start here

1. Open http://127.0.0.1:8188. Open a numbered saved workflow or import its JSON from ComfyUI-Workflows. Expanded-Workflows/*-api.json files are for scripts, not visual import.
2. Choose the actual deliverable: a 64px icon, animation frame, website hero, product edit or concept illustration. Write three non-negotiable requirements.
3. Keep the original graph and save a working copy. Change the prompt and seed first. Generate one image before starting a batch.
4. Use four seeds, such as 1101–1104, for initial comparisons. The same seed does not encode the same scene across architectures; it supports repeatability within a configuration, not fairness by itself.
5. Change one factor at a time: checkpoint, LoRA strength, guidance, steps, reference strength or resolution. Record quantization separately from model identity.
6. Review all samples at delivery size and against the reference, including failures. Record why an image was rejected.
7. Promote a configuration after it consistently helps the deliverable. Preserve model revision/hash, graph, prompts, seed, source image and timings together.

The existing single-image smoke tests use different model-appropriate briefs. They demonstrate execution and reveal defects; they are not a fair quality ranking.

## First controlled comparison: pixel art

Use workflow 12 (SDXL Pixel Prop Concept) and workflow 20 (SDXL Pixel Art LoRA and 128px Export). Their recorded tests use the same chest prompt, seed 2026091103, 30 steps, CFG 6 and sampler. Workflow 20 adds Pixel Art XL at strength 1.0 and exports both raw and nearest-neighbour 128px images.

The LoRA sample looks more suitable as a small sprite, but the background remains opaque and the palette/edges need review. This is one paired example. Try strengths 0.6, 0.8 and 1.0 with four seeds before choosing a default. Start without a speed LoRA so its effect is separate. The author documents SDXL compatibility and 8x reduction: [Pixel Art XL](https://huggingface.co/nerijs/pixel-art-xl).

Run four seeds with the supplied runner:

```powershell
py -3.13 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Expanded-Workflows\run-batch.py' --graph 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Expanded-Workflows\pixel-lora-api.json' --out 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Batches\pixel-lora-four-seeds' --count 4 --seed 1101
```

Repeat with pixel-concept-api.json and a different output folder. Reusing the same folder resumes known jobs; changed inputs are rejected. The runner passed three mocked recovery/duplication tests and a real generation. Resuming that completed real run skipped generation. Images remain in ComfyUI/output, with locations in result.json. The first LoRA result and both images are also copied into Expanded-Workflows.

## Representative test suite

| Case | Fixed brief and constraint | Compare first | Judge at delivery |
|---|---|---|---|
| Pixel prop | One chest, three-quarter view, no surrounding loot | SDXL vs Pixel Art XL | 64/128px silhouette, clusters, palette, alpha |
| Stylized prop | One teal potion with brass stopper, isolated | SDXL, FLUX Klein, WAI | Outline, material readability, family consistency |
| Abstract website art | Teal/amber ribbons, left 45% quiet | SDXL, FLUX Klein, Z-Image | Desktop/mobile crops, text contrast, visual noise |
| Product photo | Teal/brass lantern on dark studio background | RealVisXL, Z-Image, FLUX Klein | Geometry, materials, lighting and reflections |
| Character design | Adult ranger, green cloak, brown boots, one lantern | WAI, Animagine, Pony; Noob for hobby work | Anatomy, outfit, silhouette and duplicates |
| Reference edit | Recolour only the lantern enamel | FLUX edit, Qwen Lightning, Qwen quality | Source preservation and unintended changes |
| Pose transfer | Approved character in authored passing pose | Reference edit vs pose ControlNet | Joint placement AND identity |
| Promotional layout | Exact headline and specified quiet area | Generated image plus HTML/SVG text; later text models | Spelling, hierarchy and layout |
| Texture | Mossy stone tile with seamless repeat | Planned specialist workflow | 3x3 repeat, edge discontinuities, baked lighting |
| Animation | Four distinct gait phases | Pose/reference generation vs Blender rig | Foot contact, pivots, continuity and loop timing |

Keep model-native quality prefixes where appropriate, but hold the semantic brief and output target constant. Identical prompt strings can handicap tag-trained models against prose-trained ones. For edits, use identical source pixels and masks. For real products, compare with the actual product rather than accepting invented geometry.

## Recording and judging results

Use Experiment-Scorecard.csv. Score brief adherence, structural correctness, visual quality, consistency and delivery readiness separately from 0–5: 0 unusable, 3 usable after work, 5 meets the brief cleanly. Leave subjective scores blank until reviewed. For sprites, delivery readiness means final-size pixels and alpha, not high-resolution beauty.

Record cold-load time separately from a loaded-model run. Classify invalid graphs, memory errors, native crashes and poor images separately. The observed Qwen-to-SDXL crash was an access violation, not a confirmed capacity error. Sampled available memory is not necessarily a true peak measurement.

Track accepted/generated images and generation plus cleanup time per accepted asset. For slow quality workflows, prioritize fidelity and usable-output rate; latency is a cost, not an automatic rejection. Start with four samples. For close finalists, use 8–12 and hide model names during review where practical. Avoid one universal score across unrelated use cases.

## Experimental models and LoRAs

Check source author, actual files, base architecture, revision, model card and terms. Prefer the creator; record mirror provenance and compare checksums. Tensor weights and executable repository code need different handling. A popular repository or permissive mirror label does not prove original terms or authenticity.

Match LoRAs to the specific base family: SDXL base, Pony, Illustrious, FLUX variants and Qwen have different ecosystems. Record trigger words, model/text-encoder strengths and sampler. Compare no LoRA against one LoRA before stacking several. Pixel Art XL is the installed first example.

For character training, curate consistent approved views and hold out evaluation poses. Contradictory generated sheets are poor training data. Successful local LoRA training has not yet been demonstrated here.

## Staged expansion

| Stage | Candidate | Purpose and present state |
|---|---|---|
| Current | SDXL, WAI v17, Animagine, Pony, NoobAI 1.1, RealVisXL | Installed and generation-tested illustration/photo alternatives; Noob terms prohibit commercial generated products |
| Current | FLUX Klein 4B, Z-Image Turbo, Qwen Edit 2511 Q4 | All generated on this PC; fast concepts, general images, instruction edits |
| Current specialists | Pixel Art XL, OpenPose, deterministic exports, Blender | LoRA and pose runs passed; complete Blender-to-browser example supplied |
| Next experiment | HiDream-O1 FP8 | Unified generation/editing/reference test in a separate compatible runtime; not installed/tested |
| Next alternatives | SD3.5 Large, FLUX.1/Krea or Klein 9B, Z-Image base | Select against a specific weakness; verify exact release and encoder requirements first; not installed/tested |
| Specialist expansion | Depth/canny, reference adapters, detail/upscalers, tiling, style/character LoRAs | Add individually against recurring defects in the scorecard; compatibility is model-specific |
| Later heavy trial | FLUX.2 dev 32B | Exact quantized-file metadata saved; no weights downloaded or generation claimed |
| Separate consideration | Ideogram 4 | Local AMD feasibility remains untested; gated weights and documented default hosted dependencies need separate consideration |

[HiDream-O1](https://huggingface.co/HiDream-ai/HiDream-O1-Image) and its [community ComfyUI node](https://github.com/Saganaki22/HiDream_O1-ComfyUI) make FP8/SDPA a credible next experiment. Both warn about PyTorch 2.9.x, which the current working AMD runtime uses. Start with one 512px job in an isolated compatible environment; do not replace the working ROCm installation merely to satisfy another model's dependencies.

## FLUX.2 dev 32B: later-stage runbook

FLUX2-32B-Future-Candidates.json pins city96's revision and hashes. Q3_K_S is about 15.78GB, Q3_K_M 15.96GB, Q4_K_S 19.30GB and Q4_K_M 20.08GB. These are diffusion files only. Even Q3 leaves little room in 16GB VRAM for activations; Q4 needs substantial offloading. [Quantizer repository](https://huggingface.co/city96/FLUX.2-dev-gguf).

Before downloading, account for the Mistral encoder, VAE, RAM and disk. ComfyUI documents its encoder; stable-diffusion.cpp documents a quantized Mistral Small 3.2 24B route. Investigate local encoder unloading/scheduling, CPU offloading and possible prompt-embedding caching before declaring the whole pipeline viable. A remote-encoder example does not satisfy an entirely local workflow. [ComfyUI guide](https://docs.comfy.org/tutorials/flux/flux-2-dev), [stable-diffusion.cpp guide](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/flux2.md).

Then pin and checksum files, run one low-resolution sample with supported attention, measure memory/time, inspect output and increase quality one variable at a time. Compare the same product and multi-reference briefs against smaller models. If the machine cannot complete the experiment reliably, record the limiting stage rather than repeatedly exhausting RAM. More system RAM may help, but no upgrade requirement is established by an unrun trial.

The official card distinguishes model-use terms from output-use terms, and its HF gate includes contact sharing. Resolve exact access conditions at the later download stage. [FLUX.2 dev](https://huggingface.co/black-forest-labs/FLUX.2-dev).

No recurring research/download automation was created. This is the saved next-stage plan, separate from the current verified library.
