# Model registry

`installed-manifest.json` records relative model paths, file sizes, SHA-256 values and available source revisions. The files were checksum-verified when originally downloaded. Presence and size can be checked quickly; rehashing every weight is deliberately not part of every launch.

No weights are stored in Git. They remain in the configured ComfyUI `models` directory. This registry does not install a fresh machine automatically.

`library.json` adds the 22 Workflow Lab assets with exact filenames, destination
folders, pinned source URLs, sizes, SHA-256 values, model families and terms.
All 22 were installed and checksum-verified on 11 September 2026. Use Studio's
**Models & folders** for presence, verification receipts, available storage and
explicit install/resume actions. The older manifest describes the original set;
the two manifests are complementary. The [Workflow Lab guide](../docs/WORKFLOW-LAB.md)
explains which split weights and adapters belong together.

- **WAI v17:** installed from [frankjoshua's Hugging Face mirror](https://huggingface.co/frankjoshua/waiIllustriousSDXL_v170). `wai-provenance.json` records agreement with another mirror. Original creator authentication/commercial terms remain unresolved. No VPN was needed for the copy installed here.
- **NoobAI XL 1.1:** [author model card](https://huggingface.co/Laxhar/noobai-XL-1.1) restricts commercial use including generated products; hobby/research preset only.
- **Pixel Art XL:** [LoRA source](https://huggingface.co/nerijs/pixel-art-xl), paired with SDXL. It is a style aid, not automatic production pixel cleanup.
- **FLUX.2 dev 32B:** its Q4 diffusion weight and matching Mistral Q4 encoder are installed and checksum-verified. Inference remains untested; `flux2-32b-candidates.json` preserves the source metadata. A concrete RAM/offload strategy is still needed.

Other installed options: SDXL base, FLUX Klein 4B FP8, RealVisXL V5 FP16, Animagine XL4 Opt, Pony V6, Z-Image Turbo BF16, Qwen Image Edit2511 Q4 with Lightning, and Xinsir OpenPose SDXL. Research documentation contains source links and measured limitations. A model being installed does not imply unrestricted rights over its weights, outputs, third-party characters, or references.
