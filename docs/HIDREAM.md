# HiDream-O1 FP8: successful isolated experiment

The model is installed at `C:\AI\experiments\hidream-o1`, separate from the everyday studio. Its 8,805,764,784-byte weight file passed SHA-256 verification: `f212b6ec25fd0220ea821cdd11fe9b49b3a9b4cdfaaf55d2f432f2d2ba6bf810`.

Pinned model revision: `drbaph/HiDream-O1-Image-FP8@f554d59dba6bc536309f95ae152ca92321e14702`. Node revision: `Saganaki22/HiDream_O1-ComfyUI@1f1dd545faa3ea436aa2fc89f2a555f0cbc88651`.

## What actually happened

The isolated stack uses the existing ROCm Torch with Transformers 5.3.0, Tokenizers 0.22.2, Hugging Face Hub 1.28.0, Diffusers 0.40.0 and Accelerate 1.15.0 in an overlay. The primary ComfyUI packages were not changed. All eight custom node types imported.

The first run loaded 759 tensors but the sampler failed because the API graph omitted its dynamic image-count selector. The corrected graph supplies `image: "0"` for text-only generation. It completed with SDPA, FP8 weights/BF16 compute, eight steps and CFG 5. The node snapped the requested 512×512 resolution to **2048×2048**. Server execution after the cached model load took **32.839 seconds**; initial load and failed attempt took **276.95 seconds**.

![First HiDream lantern](../examples/gallery/hidream-o1-fp8.png)

The picture is recognizable and broadly follows the brief, with soft/painterly texture and imperfect fine structure. It is one feasibility sample, not proof that eight steps is the preferred quality configuration. The saved artifact is the final SaveImage PNG; a temporary JPEG preview is not the final output.

The everyday ComfyUI process also exited with a native access violation during the transition. Its root cause remains unresolved. The isolated server was stopped after the test and the primary studio restarted. Do not run both model families on the GPU simultaneously.

## Use it in Studio

Choose **HiDream O1 · isolated** in the environment selector and press **Switch
environment**. Studio checks local and remote queues before stopping the exact
configured idle service and starting HiDream. It refuses to stop another command
on the port or switch while a submission is unresolved. Return to **Main library**
for the other model families. Node imports can take about a minute.

The recipes are **HiDream O1 - 2K Anime Concept** and **Reference Restyle**, with
API and native ComfyUI graphs. Concept sizes use actual supported resolution
pairs. The reference recipe follows Image 1's aspect through native preprocessing
and uses ComfyUI V3's dotted `image.image_1` input. Controls expose 8, 20 and
50-step studies; 50 is the full model's published recommendation. Eight steps is
an experimental speed/quality choice.

On 11 September 2026 both ran through Studio: the 2048-square anime concept took
**184.697 seconds** including loading, prompt
`a784ab40-a48a-4013-9a1f-0e594f15b86d`; the lantern reference restyle took
**76.260 seconds**, prompt `c599a918-20fb-4e78-8dce-6ed8fd170362`. Both used eight
steps and retained final PNGs, temporary previews, seeds and runtime paths in
Workspace. These are distinct workloads and cache conditions, not a benchmark.
The graphs pass the running node/input contracts. Higher-step variants have not
been rendered in this pass. Art acceptance remains open.

The upstream Torch 2.9.x warning still applies to this ROCm installation. The
isolated dependency overlay is preserved. Switching adopts only the configured
service matching its Python executable, entry script, root and loopback port;
it can stop an idle instance launched with the same known launcher. Its queue
is rechecked immediately before stopping. Direct submissions through another
ComfyUI browser cannot be made atomic with a switch; finish those first.

Every job retains its backend URL/root, so switching does not redirect old
observation or media. An interrupted switch is recorded and never resumes on
page load. Use **Switch environment** to start a selected offline backend.
Switching never installs packages or submits generation. **Generate** remains
a separate action.

Sources: [custom node](https://github.com/Saganaki22/HiDream_O1-ComfyUI), [converted FP8 model](https://huggingface.co/drbaph/HiDream-O1-Image-FP8), [official model](https://huggingface.co/HiDream-ai/HiDream-O1-Image).
