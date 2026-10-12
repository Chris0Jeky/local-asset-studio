# Native AMD Animagine proof — 12 October 2026

One deliberately submitted Studio job completed on the installed AMD runtime. This proves the current Animagine portrait graph with both optional LoRAs disabled; enabled adapter branches, other variants and artistic suitability were not evaluated. Generation completed; owner art acceptance and licence acceptance remain unrecorded.

| Evidence | Observed value |
| --- | --- |
| Preset | `anime-animagine-quality` |
| Authored graph SHA-256 | `6230dc971484ec8e45fa83e1ec1d69f51678167d7343ac3d14197110eac795a0` |
| Studio job | `dd0c1838-8b91-4a03-ac1d-57b0688ebed8` |
| ComfyUI prompt | `144091d1-db6e-4db3-af34-3511b64616d8` |
| Output asset | `a2ec0cb54a32547f9bcb083d412188b1` |
| Checkpoint | `animagine-xl-4.0-opt.safetensors`, 6,938,350,040 bytes |
| Checkpoint SHA-256 | `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac` |
| Fresh checkpoint hash | 12.295 seconds; before/after file identity stable |
| Runtime | ComfyUI 0.35.0; embedded Python 3.12.10; PyTorch 2.9.1+rocm7.2.1 |
| Device | AMD Radeon RX 9070 XT; runtime identifier `cuda:0 AMD Radeon RX 9070 XT : native` |
| Render | 832 × 1216, batch 1, seed 2026101201, 28 Euler ancestral steps, normal schedule, CFG 5 |
| Execution time | Native engine 17.42 s; Studio job 18.478 s; activation/hash/job/shutdown packet 95.049 s |
| Output | `Anime-Animagine-Portrait_00002_.png`, RGB PNG, 1,392,418 bytes |
| Output SHA-256 | `d9dc8968f1ac3c796dc6e1b595929c9e40cbfca435612f73632d0f9caa520bc3` |
| Raw submitted graph file SHA-256 (CRLF) | `47eeb30fbb2f7272cefe3b2e277601da06e959e474ba6f0d72b0fbd382d73cf6` |
| Committed graph text SHA-256 (LF) | `f26d7d76ef4cccde046da9506db3777dde81b2adfdbb7621a8db678cd0245924` |
| Canonical submitted JSON SHA-256 | `714c30684fb917be1c2c4e315512cfa32a87ad5bd22027ad2f7ca209bb0a9005` |

The [recipe](recipe.json) records the complete submitted controls, references and parents. The [submitted workflow](submitted-workflow.json) retains the seven-node compiled graph: Studio removed the two disabled LoRA nodes from the nine-node authored graph. No input image or private source artwork was used. The listed checkpoint binary was used for inference; model binaries and output artwork are not committed here. The original output and raw runtime records remain outside Git in the local maintenance evidence folder.

Git normalizes text line endings, so the raw run file and committed text have distinct byte hashes while parsing to the same graph. The canonical hash uses UTF-8 `json.dumps(graph, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`; it is identical for both records.

Agent visual inspection opened the output: a silver-haired elf in an embroidered blue robe, side profile with downcast/closed eyes and a soft bright background. No hands were visible; no obvious text or watermark was observed. This is technical inspection, not an owner verdict.

Five backend API samples reported at most 6.777 GiB VRAM used. Thirty-eight process-counter samples reached 11,352,096,768 dedicated bytes and 180,449,280 shared bytes, with `spilled=false`. These counters have different bases and sampled peaks are not exhaustive hardware peaks. Free RAM fell from 9.957 GiB at admission to a sampled minimum 3.646 GiB during model loading, then recovered to 12.741 GiB after shutdown. Future cold runs of this packet require 12 GiB free RAM at admission.

The job completed and the ComfyUI queue was empty before the exact owned Studio and ComfyUI processes were stopped and joined. No uncertain submission was repeated, and no model download, installed package, driver or network-policy change occurred.

Publisher terms were checked on 12 October 2026: [Animagine XL 4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0) identifies the unchanged [SDXL CreativeML Open RAIL++-M licence](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md) and permits private use. This run used the owner's existing private-experiment scope, with an original clothed adult character. No new redistribution clearance or owner licence decision is inferred. Creative and licensing choices remain in `HUMAN_TODO.md`.
