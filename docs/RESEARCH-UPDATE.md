# Follow-up findings — 11 September 2026

Four lightweight outstanding graphs completed during repository migration:

| Preset | Server seconds | Finding |
|---|---:|---|
| RealVis website banner | 26.595 | Convincing fictional lake/cabin landscape, with usable quiet water areas. Text placement still needs a real layout test. |
| SDXL stylized prop | 15.126 | Graph executed; see the generated sample before accepting its art. |
| SDXL gentle variation | 5.942 | Recognizable small teal/brass lantern and plain background; image is only 256px and softened. This is not an upscale or exact-preservation workflow. |
| WAI pose guide | 21.649 | Graph executed; pose control is not identity preservation. |

Full server records remain in the original local workspace. The repository keeps the compact result table in `experiments/curated/initial-results.json`.

HiDream-O1 subsequently completed an isolated FP8/SDPA render with a pinned dependency overlay. See [executed HiDream findings](HIDREAM.md). The primary Transformers package was not changed, and the node's Torch 2.9.x warning remains relevant.

FLUX.2 dev 32B remains a later-stage candidate. Its diffusion weights alone are not its full memory footprint; the encoder and activations also matter.
