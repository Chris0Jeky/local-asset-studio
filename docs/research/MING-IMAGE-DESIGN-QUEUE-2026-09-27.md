# Try queue — Ming Image Design 2026-09-27

Hardware gate: AMD RX 9070 XT **16GB** + 32GB RAM. Prefer FP8/GGUF; strip SageAttention / Triton / DLSS / RTX VSR / Nunchaku when importing WFs; `--use-pytorch-cross-attention`. Ming’s current consumer path is **INT8 ConvRot** (not FP8/GGUF yet) — treat Triton/HIP INT8 as an explicit AMD risk, not a default Create enable.

| # | name / id | type | base | VRAM fit | license | LAS Create | NSFW | try/skip/park | reason | URL |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Ming-Image-0.1-Design (12GB DiT)** INT8 + w4a8/INT8 TE | Checkpoint family | Ming Design | **tight** (DiT INT8 ~6.2GB; TE w4a8 ~12.8GB or INT8 ~19.5GB → needs Dynamic VRAM / offload; BF16 package **no**) | **MIT** | **no** (Comfy smoke first; no Create preset) | SFW (design UI) | **try** | Only realistic 16GB lane. Smoke after Comfy ≥ PR #16482 merge. A/B TE w4a8 vs INT8+offload. Do **not** download BF16 (~53GB). | https://huggingface.co/inclusionAI/Ming-Image-0.1-Design · https://huggingface.co/Comfy-Org/Ming-Image |
| 2 | Ming-Image-0.1-Design BF16 full | Checkpoint | Ming Design | **no** (weights alone ~49–53GB; validated 80GB) | MIT | no | SFW | **skip** | Cannot load on 16GB; cloud/80GB only. | same |
| 3 | **Ming-Image-0.1-Design-Layer (24GB DiT)** | Checkpoint family | Ming Layer | **no** / park (official DiT BF16 **24.62GB** alone; TE shared huge; Comfy Layer files exist but node/TE story thin) | MIT | no | SFW | **park** | No dual-GPU / clear 16GB offload story. Revisit if GGUF/FP8 Layer + TE land. | https://huggingface.co/inclusionAI/Ming-Image-0.1-Design-Layer |
| 4 | Comfy-Org Ming INT8 Layer DiT | Quant ckpt | Ming Layer | unclear/tight (listed ~6.2GB DiT; TE still heavy; packaging size vs official 24.62GB DiT **discrepancy**) | MIT | no | SFW | **park** | Size mismatch vs official Layer transformer — verify before any download. | https://huggingface.co/Comfy-Org/Ming-Image |
| 5 | Official `infer.py` + flash_attention_2 | Runtime | Ming | no on AMD daily | MIT | no | SFW | **skip** | CUDA 80GB path; FA2 / CUDA-centric. Not LAS Create. | https://github.com/inclusionAI/Ming-Image |
| 6 | vLLM-Omni serving recipe | Serve | Ming | n/a (server) | MIT | no | SFW | **park** | Card recipe URL historically 404; not desktop Create. | model cards |
| 7 | OpenRouter free API (time-limited) | Cloud API | Ming | n/a | MIT weights / API ToS | no | SFW | **skip** (local-first) | Fine for quality peek only; not LAS local lane. | news coverage |
| 8 | Ostris AI-Toolkit Ming LoRA trainer (12GB claim) | Train toolkit | Ming Design | train-only (RTX 4070 12GB NVIDIA report with INT8+offload) | MIT + toolkit | no | SFW | **park** | Interesting for later asset LoRAs; NVIDIA-centric report; not inference Create. | https://note.com/sepiablue/n/n89e59ce996d9 |
| 9 | Prompt enhancer Ling-3.0-flash-VL / qwen3.8-27B | PE helper | — | separate VRAM | varies | no | SFW | **park** | Official PE step; optional later if Design smoke wins. | Ming README |

**Do not** flip LAS Create defaults. Tracking: see `ISSUES.md`. Cross-tree: #739 / #760 / #934 / #1028.
