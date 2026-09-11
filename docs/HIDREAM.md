# HiDream-O1 FP8: successful isolated experiment

The model is installed at `C:\AI\experiments\hidream-o1`, separate from the everyday studio. Its 8,805,764,784-byte weight file passed SHA-256 verification: `f212b6ec25fd0220ea821cdd11fe9b49b3a9b4cdfaaf55d2f432f2d2ba6bf810`.

Pinned model revision: `drbaph/HiDream-O1-Image-FP8@f554d59dba6bc536309f95ae152ca92321e14702`. Node revision: `Saganaki22/HiDream_O1-ComfyUI@1f1dd545faa3ea436aa2fc89f2a555f0cbc88651`.

## What actually happened

The isolated stack uses the existing ROCm Torch with Transformers 5.3.0, Tokenizers 0.22.2, Hugging Face Hub 1.28.0, Diffusers 0.40.0 and Accelerate 1.15.0 in an overlay. The primary ComfyUI packages were not changed. All eight custom node types imported.

The first run loaded 759 tensors but the sampler failed because the API graph omitted its dynamic image-count selector. The corrected graph supplies `image: "0"` for text-only generation. It completed with SDPA, FP8 weights/BF16 compute, eight steps and CFG 5. The node snapped the requested 512×512 resolution to **2048×2048**. Server execution after the cached model load took **32.839 seconds**; initial load and failed attempt took **276.95 seconds**.

![First HiDream lantern](../examples/gallery/hidream-o1-fp8.png)

The picture is recognizable and broadly follows the brief, with soft/painterly texture and imperfect fine structure. It is one feasibility sample, not proof that eight steps is the preferred quality configuration. The saved artifact is the final SaveImage PNG; a temporary JPEG preview is not the final output.

The everyday ComfyUI process also exited with a native access violation during the transition. Its root cause remains unresolved. The isolated server was stopped after the test and the primary studio restarted. Do not run both model families on the GPU simultaneously.

## Run the experiment again

HiDream is **not in the 21-preset simplified interface yet**; it uses its separate advanced ComfyUI endpoint. Its API graph is at `workflows/experimental/hidream-o1-fp8-api.json`.

1. Finish existing jobs. Stop the primary ComfyUI using its existing Stop shortcut/control under `C:\AI`.
2. Start the isolated server from the repository:

```powershell
& C:\AI\ComfyUI_windows_portable\python_embeded\python.exe scripts/hidream-launch.py
```

3. Open `http://127.0.0.1:8192`. The nodes load from the isolated copy. For programmatic reproduction, submit the saved API graph to that endpoint's `/prompt` API. It is API JSON, not a drag-and-drop visual graph.
4. After jobs finish, stop this foreground server with Ctrl+C, then double-click **Asset Studio** to return to the normal presets.

The model warning about Torch 2.9.x still applies; one success does not eliminate it. The next bounded experiment is a higher-step comparison at the same brief and seed, followed by a reference edit. FLUX.2 dev 32B remains a separate later-stage plan.

Sources: [custom node](https://github.com/Saganaki22/HiDream_O1-ComfyUI), [converted FP8 model](https://huggingface.co/drbaph/HiDream-O1-Image-FP8), [official model](https://huggingface.co/HiDream-ai/HiDream-O1-Image).
