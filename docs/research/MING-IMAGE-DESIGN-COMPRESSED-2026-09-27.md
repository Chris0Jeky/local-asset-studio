# COMPRESSED — Ming Image Design 2026-09-27 (spoken TLDR)

Chris — Ming Image Design research for Local Asset Studio, September twenty-seventh. Research only. No weights. No merges. No preset flips.

**What it is.** Ant inclusionAI Ming-Image-zero-point-one — MIT license. Two checkpoints: Design does text-to-UI, posters, infographics with real RGBA transparency. Layer splits a flat design into two-to-nine editable transparent PNGs. Marketed as six-B, but the diffusion transformer is only part of the download. Design totals about fifty-three gig on disk; Layer about sixty-five. The text encoder alone is about thirty-four gig BF16.

**Twelve vs twenty-four.** The original September shorthand paired Design's twelve-point-three-one-gig transformer with Layer's twenty-four-point-six-two-gig transformer and labelled both BF16. The Layer label was wrong: its official storage is F32. These are stored transformer sizes, not measured consumer-card VRAM requirements.

**Correction, current 2026-10-19 (issue thirteen twenty-four; FINDINGS section zero).** The pinned official API reports about six-point-one-five billion Layer parameters as F32; the card recommends BF16 for inference. Design and Layer have nearly equal counts, with Layer seven thousand six hundred eighty parameters higher. The roughly twelve-point-three-gig Comfy BF16-named file is consistent with that Layer count at two bytes plus metadata. This explains the size gap as a plausible precision/repackaging difference; the actual Comfy header and tensor mapping remain unverified.

**Accessible evidence.** [Nine raw current API responses and their dated receipts](evidence/ming-image-2026-10-19/README.md) now retain exact revisions, file sizes and advertised LFS hashes. The September raw pack is still missing, so current metadata must not be described as a recovered September audit. F32-to-BF16 conversion changes bytes; matching hashes between original shards and a repack is not the right acceptance test. No weights or tensor headers were downloaded.

**Vs Qwen stack.** Does not replace Qwen-Image-two-point-one, Edit-two-five-one-one, WAI, Pony, or RealVis. Different lane: layout and UI text rendering, not character or photo. License is MIT — friendlier than Qwen Research for shipping. Layer-decomp quality reported ahead of open Qwen-Image-Layered on Crello; closed Qwen layered is close.

**Sixteen-gig AMD.** Official validate is one eighty-gig CUDA GPU. ComfyUI core Ming support merged in PR sixteen-four-eight-two. Comfy-Org and Kijai ship INT8 ConvRot DiT about six gig plus text-encoder INT8 about nineteen-point-five or W-four-A-eight about twelve-point-eight. Even the lightest Design stack needs Dynamic VRAM and system-RAM offload on a nine-zero-seven-zero XT. INT8 ConvRot on gfx twelve-zero-one has a rocky AMD history — prefer FP8/GGUF when available; today Ming’s consumer path is INT8 ConvRot, which may conflict with the strip-Triton rule.

**Verdict.** Design twelve-gig DiT — **try** smoke in Comfy only, not Create daily. Layer twenty-four-gig DiT — **park** until a real offload or quant story exists. No dual-GPU plan.

The historical pack path was under handoffs ming-image-design-2026-09-27; that pack is unavailable here. The linked current evidence is tracked in this repository.
