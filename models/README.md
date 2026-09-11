# Model registry

`installed-manifest.json` records relative model paths, file sizes, SHA-256 values and available source revisions. The files were checksum-verified when originally downloaded. Presence and size can be checked quickly; rehashing every weight is deliberately not part of every launch.

No weights are stored in Git. They remain in the configured ComfyUI `models` directory. This registry does not install a fresh machine automatically.

- **WAI v17:** installed from [frankjoshua's Hugging Face mirror](https://huggingface.co/frankjoshua/waiIllustriousSDXL_v170). `wai-provenance.json` records agreement with another mirror. Original creator authentication/commercial terms remain unresolved. No VPN was needed for the copy installed here.
- **NoobAI XL 1.1:** [author model card](https://huggingface.co/Laxhar/noobai-XL-1.1) restricts commercial use including generated products; hobby/research preset only.
- **Pixel Art XL:** [LoRA source](https://huggingface.co/nerijs/pixel-art-xl), paired with SDXL. It is a style aid, not automatic production pixel cleanup.
- **FLUX.2 dev 32B:** `flux2-32b-candidates.json` is metadata for a later experiment, not installed weights. Its large diffusion component and separate Mistral encoder need a concrete RAM/offload strategy.

Other installed options: SDXL base, FLUX Klein 4B FP8, RealVisXL V5 FP16, Animagine XL4 Opt, Pony V6, Z-Image Turbo BF16, Qwen Image Edit2511 Q4 with Lightning, and Xinsir OpenPose SDXL. Research documentation contains source links and measured limitations. A model being installed does not imply unrestricted rights over its weights, outputs, third-party characters, or references.
