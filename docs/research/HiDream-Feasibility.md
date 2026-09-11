# HiDream-O1 ComfyUI AMD feasibility (2026-09-11)

Read-only investigation. No weights downloaded and no files under `C:\\AI` changed.

## Pinned evidence

- Node `Saganaki22/HiDream_O1-ComfyUI`: commit `1f1dd545faa3ea436aa2fc89f2a555f0cbc88651` (remote main at check time).
- FP8 repo `drbaph/HiDream-O1-Image-FP8`: commit `f554d59dba6bc536309f95ae152ca92321e14702`; `model.safetensors` HTTP `X-Linked-Size=8,805,764,784` bytes (8.81 GB decimal; HF page rounds repo/model to 8.83/8.81 GB). ETag SHA256 `f212b6ec25fd0220ea821cdd11fe9b49b3a9b4cdfaaf55d2f432f2d2ba6bf810`.
- Official full repo `HiDream-ai/HiDream-O1-Image`: commit `0b0901d99f200389e138c61946af1185f5f49a13`; HF page reports 35.2 GB total, eight safetensor shards. Shard 1 is 4,962,686,568 bytes; shard 8 is 2,489,319,552 bytes. Full model is not viable as a 16 GB VRAM target.
- Existing portable runtime read-only probe: Python 3.12.10; `torch 2.9.1+rocm7.2.1`, HIP `7.2.53211-158bd99533`, CUDA API available and BF16 supported; `transformers 5.15.1`.

## Compatibility findings

The node requirements are unpinned: accelerate, diffusers, einops, huggingface_hub, numpy, pillow, safetensors, scipy, torch, torchvision, transformers>=4.57.1, typing_extensions, tqdm. README suggests Transformers 4.57.1–5.3 and warns that PyTorch 2.9.x is not recommended because of the Qwen3-VL issue. The installed Transformers 5.15.1 is outside that stated range, so loader/runtime success is unverified.

The node has an explicit `sdpa` backend and `auto` falls back to SDPA when FlashAttention is unavailable. FlashAttention and SageAttention are optional imports; their accelerator extensions are the main likely CUDA/NVIDIA incompatibility on AMD. Do not select `flash` or `sage` in the first experiment. There are no unconditional `.cuda()`/`device='cuda'` model moves in the node path; device comes from Comfy model management. The vendored Qwen file calls `torch.cuda.memory_allocated()` for memory logging (including an unguarded call at lines 1049), which ROCm exposes through PyTorch's CUDA-compatible API; this is not proof of full AMD correctness.

## Recommendation

Promising but experimental on this machine. The only sensible first candidate is the single-file Full FP8 repo (8.81 GB weights), with `precision=auto`, `attention=sdpa`, text-only, one image, and the smallest patch-aligned resolution accepted by the node. A 16 GB card has roughly 7.2 GB left after the file, so 2048x2048 / multi-reference / seam smoothing may OOM; use Comfy DynamicVRAM/offload if already available. Dev FP8 variants are also advertised at ~10–11 GB and may be preferable for text-to-image, but were not part of the requested metadata check.

An isolated experiment should clone this exact node commit into a disposable custom-node directory or worktree and use the existing portable interpreter only after resolving the Transformers mismatch in that isolation. Download the complete FP8 folder (support JSON/tokenizer files plus model.safetensors) only then. First gate is import/loader with `sdpa`; second is one low-resolution text-only generation. Treat any success as experimental until a real image completes without OOM or Qwen errors. Do not enable `download_if_missing` accidentally.

Sources: https://github.com/Saganaki22/HiDream_O1-ComfyUI ; https://huggingface.co/drbaph/HiDream-O1-Image-FP8 ; https://huggingface.co/HiDream-ai/HiDream-O1-Image ; https://github.com/QwenLM/Qwen3-VL/issues/1811

## Isolated preparation update

- `C:\\AI\\experiments\\hidream-o1\\ComfyUI` is a code-only copy made with `robocopy /E` excluding models, input, output, user, `.git`, `custom_nodes`, and `.venv`.
- Exact node commit is checked out detached under `custom_nodes\\HiDream_O1-ComfyUI`.
- Isolated target `ComfyUI\\python_packages` contains only `transformers==5.3.0`, `tokenizers==0.22.2`, and `huggingface_hub==1.28.0`, installed `--no-deps`; primary packages were untouched.
- Core import and full HiDream node import now succeed with the existing ROCm Torch. Isolated additions are `diffusers==0.40.0` and `accelerate==1.15.0`, both installed `--no-deps`; no Torch/NumPy duplicate was installed. Probe output registers eight nodes: ModelLoader, Conditioning, LoRA, DevSmoothing, Sampler, DatasetMaker, TrainConfig, and LoRATrainer.
- One authorized pinned snapshot download was started using `huggingface_hub.snapshot_download` into the isolated model directory. All ten small support files arrived. At the last check, process PID 33452 remained active, `model.safetensors` was absent from the target, and its `.incomplete` cache file was 0 bytes with a lock present; C: free space was 92.62 GB. Do not start another GPU server or generation while it remains active.
- Durable probe script: `work\\hidream-research\\isolated_probe.py`. Run from the isolated ComfyUI directory with `C:\\AI\\ComfyUI_windows_portable\\python_embeded\\python.exe work\\hidream-research\\isolated_probe.py` (it imports the isolated package target before the code copy).
- Experiment-local launcher bootstrap: `C:\\AI\\experiments\\hidream-o1\\bootstrap_probe.py`; invoke with `C:\\AI\\ComfyUI_windows_portable\\python_embeded\\python.exe C:\\AI\\experiments\\hidream-o1\\bootstrap_probe.py`. It is import-only and starts no server or generation.

## Graph for first manual workflow (after root coordinates)

`HiDream O1 Model Loader (attention=sdpa, precision=auto)` -> optional `HiDream O1 LoRA` -> optional `HiDream O1 Dev Smoothing` -> `HiDream O1 Sampler`.
`HiDream O1 Conditioning` (prompt, negative prompt) -> `HiDream O1 Sampler` conditioning input. For the first probe use no LoRA, no smoothing, zero reference images, and a low patch-aligned size.
