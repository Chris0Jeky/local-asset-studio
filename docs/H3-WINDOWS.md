# MiniMax H3 on this Windows Radeon installation

The isolated H3 route produced a complete short video on 11 September 2026.
The normal native safetensors loader remains incompatible on this installation;
Studio launches the working wrapper on a separate loopback port.

## Use it in Studio

1. Finish active jobs, then select **Model environment → H3 loader experiment →
   Switch environment**.
2. Choose **MiniMax H3 - Preview**. Its default is the tested 512×320, 39-frame,
   eight-step graph. Change the description or seed when you want a new shot.
3. Generate once and follow that job. The measured cold run took 6 minutes
   38 seconds for 1.625 seconds of video and stereo audio.
4. Return to **Main library** for other model families. Existing outputs and
   recipes remain in Workspace, including when the H3 backend is stopped.

The longer-shot and native-canvas variants remain experimental. The quality,
image-anchor and first/last recipes have not been rendered with this workaround.
Three-seed audition requests three full generations; it is not free cache reuse.

## What goes in which folder

These paths are beneath `C:/AI/ComfyUI_windows_portable/ComfyUI/models/` on the
configured PC. Studio's **Models & folders** view exposes the paths and status.

| Component | File location |
|---|---|
| Diffusion model, including the originally downloaded file | `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` |
| Text encoder | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| Video decoder | `vae/minimax_h3_video_vae_fp16.safetensors` |
| Audio decoder | `vae/minimax_h3_audio_vae_fp32.safetensors` |
| Eight-step preview adapter | `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` |

The backbone alone is not a complete pipeline. These five matched files are
installed and pinned in `models/library.json`. Input images are separate assets;
an image-to-video workflow also needs its requested image supplied. The native
source/template link remains on each Studio recipe. Owner confirmation of
eligible-territory use is recorded in HUMAN_TODO.md.

## Compatibility evidence and limits

The normal loader access-violated while opening/materializing the NVFP4 encoder.
`--disable-mmap` did not help because it acts after native tensor access.
The first stdlib copy-on-write encoder loader passed text inference, then native
opening of the 19.53 GiB diffusion file failed with Windows error 1455. Read-only
encoder mapping alone also reached that same failure.

The working opt-in wrapper intercepts exactly the encoder and FL2VA diffusion
paths for CPU loading, validates header extents, maps them read-only and retains
mapping references on tensor storage. Every other file keeps its normal loader.
No installed ComfyUI files, Torch/ROCm packages or Windows paging settings changed.
The process uses the normal legacy ModelPatcher and default non-in-place LoRA
patching. Custom nodes that mutate source tensor storage are outside this proof.

Separate construction probes recorded 2,054 encoder tensors and 932 diffusion
tensors. The diffusion probe constructed MiniMaxH3/ModelPatcher in 5.603 seconds
with a 4.30 GiB peak process working set. Runtime imports initialized CUDA; these
figures are construction measurements, not an inference memory benchmark.

The complete run retained job `3e03d7d9-aaed-4772-a385-cfaeb29e8873` and prompt
`49873807-fda1-4fe0-afdd-62b13f5329d8`: seed 2026091143, 398.096 seconds.
`Studio/H3-preview_00001_.mp4` contains 39 decoded H.264 frames at 512×320 and
32 kHz stereo AAC, both 1.625 seconds. SHA-256:
`24af39b10295de44182703bf5663bfc2bc23d339bbb1afe7c5b6463f6008a94d`.
First/middle/last frames were inspected and non-silent audio decoded. Audio quality
and creative acceptance were not assessed. The API defaults now exactly match
the retained executed graph; the visual workflow carries the same controls.

Source pins: ComfyUI `40c4fcdf513a4523e39d54a9d391908af8df8171`, Torch 2.9.1 with
ROCm 7.2.1, RX 9070 XT 16 GiB, 32 GiB system RAM and a 40 GiB paging file.
Transient pinning warnings remain in the runtime log. This is one demonstrated
configuration, not a guarantee across other drivers, models, nodes or resolutions.

The exact Seed Hunter graph is archived separately and still needs its custom
nodes, extra weights and execution proof. Native H3 success does not validate
its latent upscaler, continuation, interpolation or conditioning-cache behavior.
