# COMPRESSED — Ming Image Design 2026-09-27 (spoken TLDR)

Chris — Ming Image Design research for Local Asset Studio, September twenty-seventh. Research only. No weights. No merges. No preset flips.

**What it is.** Ant inclusionAI Ming-Image-zero-point-one — MIT license. Two checkpoints: Design does text-to-UI, posters, infographics with real RGBA transparency. Layer splits a flat design into two-to-nine editable transparent PNGs. Marketed as six-B, but the diffusion transformer is only part of the download. Design totals about fifty-three gig on disk; Layer about sixty-five. The text encoder alone is about thirty-four gig BF16.

**Twelve vs twenty-four.** Twelve-gig shorthand means Design’s transformer at twelve-point-three-one gig BF16. Twenty-four means Layer’s transformer at twenty-four-point-six-two gig BF16. Not target VRAM of a consumer card.

**Vs Qwen stack.** Does not replace Qwen-Image-two-point-one, Edit-two-five-one-one, WAI, Pony, or RealVis. Different lane: layout and UI text rendering, not character or photo. License is MIT — friendlier than Qwen Research for shipping. Layer-decomp quality reported ahead of open Qwen-Image-Layered on Crello; closed Qwen layered is close.

**Sixteen-gig AMD.** Official validate is one eighty-gig CUDA GPU. ComfyUI core Ming support merged in PR sixteen-four-eight-two. Comfy-Org and Kijai ship INT8 ConvRot DiT about six gig plus text-encoder INT8 about nineteen-point-five or W-four-A-eight about twelve-point-eight. Even the lightest Design stack needs Dynamic VRAM and system-RAM offload on a nine-zero-seven-zero XT. INT8 ConvRot on gfx twelve-zero-one has a rocky AMD history — prefer FP8/GGUF when available; today Ming’s consumer path is INT8 ConvRot, which may conflict with the strip-Triton rule.

**Verdict.** Design twelve-gig DiT — **try** smoke in Comfy only, not Create daily. Layer twenty-four-gig DiT — **park** until a real offload or quant story exists. No dual-GPU plan.

Pack path under handoffs ming-image-design-2026-09-27.
