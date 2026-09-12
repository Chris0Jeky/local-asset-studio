# Character identity-plus-pose probes — 12 September 2026 (evening)

Direct ComfyUI probes of an SDXL route for the character-consistency programme: WAI v17 with the installed
`ip-adapter_sdxl_vit-h` (identity from the canon front) and `xinsir-openpose-sdxl` (a skeleton extracted from
the canon back crop), rendering the canon's back view at 704×1536. They were submitted straight to ComfyUI's
`/prompt`, not as Studio jobs and not as Production attempts, so they spend no study budget and prove only that
the graph runs and what the base adapter carries. Nothing here is art acceptance or licence clearance.
Exact prompt IDs, hashes, graphs, uploads and the download receipts are in
[`execution-evidence.json`](execution-evidence.json); JPEG copies (quality 88) are under
[`examples/character-identity-pose-probes/`](../../../examples/character-identity-pose-probes/).

| Probe | Result | Wall time | What it shows |
|---|---|---|---|
| A — with the `aqua (konosuba)` character tag | [probe-A-tag](../../../examples/character-identity-pose-probes/probe-A-tag.jpg), completed | 111.1 s including cold loads | Continuous hair curtain, hair loop and ornament, gold upper-arm bands, navy pleated skirt with gold trim and lilac frill, white thigh-highs, V-topped navy boots; pose follows the skeleton. |
| B — same graph, no character tag | [probe-B-notag](../../../examples/character-identity-pose-probes/probe-B-notag.jpg), completed | 82.1 s | The design drifted (twin hair loops with yellow beads, a large back bow, corset lacing, yellow knee boots). |
| C — padded identity image | never executed | — | ComfyUI died at the checkpoint reload before any node ran (issue #89). |
| C2, C3 — padded identity image, weight 0.6 | executed, no output | 30 steps sampled | ComfyUI died in `partially_unload` during `VAEDecode`; no image was written (issue #89). Graphs retained. |
| D — weight 1.0 | never submitted | — | The sequential runner stopped after the crash. |

**Read A and B together, honestly.** WAI v17 knows the Danbooru tag `aqua (konosuba)`, and the supplied canon
matches that character item for item, so probe A carries a familiar-character prior; probe B is the
generalisable measurement, and it says the base IP-Adapter at weight 0.6 on a centre-cropped torso does not
carry an original design. The plus and plus-face adapters downloaded tonight (receipts in the evidence file)
are the next step for that route; the fixed-geometry Qwen route lands separately in PR #103.

Two Studio `qwen-2ref` attempts with the front and back canon bound as identity and costume references are
recorded in the same file: job `a2908800` ended **uncertain** (ComfyUI died while loading the GGUF; prompt ID
retained, not resubmitted) and job `f29937b7` **failed** on a host allocation at 87 % commit under the new
0.6 GB VRAM reserve (issue #77). The OpenPose preprocessor's first use downloaded three annotator weights
into the custom node's folder; their sizes and SHA-256 are recorded.
