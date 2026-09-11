# Workflow Lab execution samples

These are selected agent-created tests from 11 September 2026, not a copy of the
user's full gallery. They preserve the same broad adult swordswoman/rainy-street
brief across three different image families, then animate the Krea result.

| Route | Sample | Controls |
|---|---|---|
| SDXL + LineAni | [Line art](../../../examples/workflow-lab/lineani.png) | 512×768, 20 steps, CFG 5, LoRA 0.8 |
| Anima Aesthetic 1.1 | [Illustration](../../../examples/workflow-lab/anima.png) | 512×768, 24 steps, CFG 4 |
| Krea Turbo FP8 + free retro adapter | [Retro anime](../../../examples/workflow-lab/krea.png) | 512×768, 8 steps, CFG 1 |
| Wan 2.2 image-to-video | [MP4](../../../examples/workflow-lab/wan-retro-anime.mp4) | Krea image, 512×768, 33 frames at 24fps, 20 steps |
| Hunyuan3D 2.1 | [Geometry GLB](../../../examples/workflow-lab/hunyuan-lantern.glb) | Starter lantern, 20 steps, octree 128 |
| TRELLIS.2 + explicit Blender finishing | [Trimmed PBR GLB](../../../examples/workflow-lab/trellis-lantern-trimmed.glb) | Native 512 shape / 1024 bake, then 3.5% bottom trim and 80k triangle target |

Seed: 2026091103; the TRELLIS transparent-reference variation uses 2026091104.
Exact prompts, per-submission graphs, IDs, controls and output
descriptors are in the adjacent `*-recipe.json` files. Artifact hashes and
observed timings are in [execution-evidence.json](execution-evidence.json).
Timings include differing cache/model-loading conditions and are not a benchmark.

The three images and a sampled Wan video frame were inspected. The video decodes
to 33 frames and loads in the Studio player. Hunyuan's GLB was inspected in the
interactive viewer and contains 80,924 triangles, one mesh and no image textures.
It is a geometry draft. These results do not establish art acceptance, all-angle
accuracy, reliable anatomy, clean topology, or commercial suitability.

Both native TRELLIS PBR outputs completed with the local CPU UV patch, but invented
a ground plane. Their originals remain under ComfyUI `output/Studio` because each
exceeds this repository's 10 MiB file cap. The exported recipes identify them.
The trimmed/reduced copy has 80,335 triangles, a UV set, base-color texture and
metallic/roughness texture. It was inspected in the Studio viewer. Its `.finish.json`
sidecar records the original/output hashes and exact settings. Trimming can leave
an open base and simplification can alter texture seams; game-engine suitability
has not been established. Blender emitted a shared-image sampler warning while
exporting; both texture slots remain present and visible appearance was checked.

To repeat on this PC, import the desired recipe in Studio. To transfer it, also
provide matching model files and input images. Wan uses the Krea PNG as its
reference; Hunyuan uses `examples/references/lantern-reference.png`. Uploaded input
filenames in the JSON are local references, not embedded image data. A changed
preset is deliberately rejected by exact recipe import; review it as a new
experiment instead of silently assuming a replay.

Rebuilding the generated catalog resets its execution flags. Keep these records
as historical evidence and re-establish evidence after changing the underlying
graph. MiniMax failures and untested variants are recorded in
[CURRENT_STATE.md](../../../CURRENT_STATE.md).
