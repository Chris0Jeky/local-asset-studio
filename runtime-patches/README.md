# Local CPU UV compatibility patch

`comfyui-cpu-uv.patch` changes only the small-chart LSCM solver call in native
ComfyUI UV unwrapping. The first TRELLIS trial reached `UnwrapMesh` and failed with
`HIPBLAS_STATUS_ALLOC_FAILED` in `hipblasDgetrfBatched` on Windows ROCm 7.2.1,
Torch 2.9.1 and RX 9070 XT. Its prompt ID is
`e621da7b-ddaf-45b6-9422-43c9ab75be91`.

The caller already supplies CPU NumPy chart arrays. Passing `torch.device("cpu")`
selects the existing NumPy FP64 solve instead of the HIP batched solver. GPU
segmentation, UV packing, result-device transfer and the PBR bake are preserved.
Large charts already use the CPU sparse solver. This trades CPU time for avoiding
the observed HIP allocation failure; it does not introduce another unwrap algorithm.

The patch was prepared for ComfyUI commit
`40c4fcdf513a4523e39d54a9d391908af8df8171`. Physical source-file SHA-256 values
before and after the change are in `comfyui-cpu-uv.json`. The untouched local
source backup is `.runtime/comfy-uv-original.py` in this Studio checkout.

This is a local compatibility patch, not a published upstream fix. A ComfyUI
update can replace it. Do not apply it blindly to a changed implementation or
overwrite unrelated edits. First compare the revision/hash and inspect the diff.
With the ComfyUI queue empty and its owned process stopped, the patch can be
checked and applied from the ComfyUI checkout:

```powershell
git apply --check "PATH_TO_STUDIO/runtime-patches/comfyui-cpu-uv.patch"
git apply "PATH_TO_STUDIO/runtime-patches/comfyui-cpu-uv.patch"
```

To undo only these lines, first use `git apply -R --check` with the same patch,
then `git apply -R`. A refusal means the file has changed and needs inspection;
do not use reset/restore to discard unrelated runtime changes. Restart the owned
ComfyUI process after applying or reversing the patch. New generation results and
remaining limitations are recorded in [CURRENT_STATE.md](../CURRENT_STATE.md).

## Runtime additions, 12 September 2026 (packages and launcher flag, no ComfyUI source edited)

Installed into `python_embeded` with `pip install "comfyui_manager==4.2.2" "python-socketio[client]>=5.8,<6"`.
Only new packages were added; nothing already installed (Torch, ROCm, transformers, huggingface-hub) was
upgraded — the `pip freeze` diff before/after is `.runtime/pip-freeze-{before,after}-manager-2026-09-12.txt`
in the Studio checkout and lists exactly: bidict 0.24.1, chardet 7.6.0, comfyui-manager 4.2.2,
cryptography 50.0.1, gitdb 4.0.12, GitPython 3.1.62, PyGithub 2.10.0, PyJWT 2.14.0, PyNaCl 1.6.2,
python-engineio 4.14.0, python-socketio 5.16.4, simple-websocket 1.1.0, smmap 5.0.3, toml 0.10.2, uv 0.12.13,
websocket-client 1.9.2, wsproto 1.3.2.

`C:/AI/Start-ComfyUI.ps1` gained `--enable-manager` at the end of its argument list. SHA-256 (first 16 hex)
before `873287a534d2ccaf`, after `526fcda531f6d7ad`; the untouched copy is `.runtime/Start-ComfyUI.ps1.before-manager`.
`custom_nodes/civitai-comfy-nodes` is a git clone at upstream commit `1bcb195` (7 September 2026).


## Launcher reserve-vram flag, 12 September 2026 (no ComfyUI source edited, no package changed)

`C:/AI/Start-ComfyUI.ps1` had exactly one token changed: `'--reserve-vram', '2'` became
`'--reserve-vram', '0.6'`. Nothing else in the argument list moved, and no file inside
`C:/AI/ComfyUI_windows_portable` was touched.

Why: `--reserve-vram` replaces ComfyUI's own default outright rather than adding to it, and that
default on this 16 GB Windows card is 600 MB + 100 MB (`comfy/model_management.py:863-867`). At 2 GB
the `qwen-image-edit-2511-Q4_K_M` unet (12,738.98 MB resident, measured) sat on the full/partial
load boundary: it loaded partially at 11,379.72 / 12,584.27 / 12,633.22 MB usable
(`C:/AI/logs/20260911-171055-error.log:282`, `20260912-043327-error.log:246,274`) and completely at
12,751.49 MB and above. A partial load is the head of the host-commit chain in #77 and of the
`0xC0000005` partial-unload crashes in #89. The derivation, the fit table and the commit gate are in
[`docs/RUNTIME-PRECONDITIONS.md`](../docs/RUNTIME-PRECONDITIONS.md).

SHA-256 before `526fcda531f6d7aded268e9f69ad3fa1bc643d05f7e74e65f5b32f902ddc604c`, after
`0c3fbc95bcb27444797eeffe08bb4047029a55f1ad352a9f979ed26bf8ea969e`. The untouched copy is
`C:/AI/Start-ComfyUI.ps1.bak-20260912-reserve2` (its hash is the "before" value above, and it is the
same file recorded as the "after" state of the `--enable-manager` entry).

To revert, with the ComfyUI queue empty and its owned process stopped:

```powershell
Copy-Item "C:/AI/Start-ComfyUI.ps1.bak-20260912-reserve2" "C:/AI/Start-ComfyUI.ps1" -Force
Get-FileHash "C:/AI/Start-ComfyUI.ps1" -Algorithm SHA256
```

`app/backends.py` carries the same value for the Studio-launched primary backend
(`PRIMARY_RESERVE_VRAM`). Revert both or neither: a change to one produces two different runtimes on
port 8188. `scripts/h3-launch.py` (8194) and `scripts/hidream-launch.py` (8192) are unchanged at 2.
Pre-existing and unrelated to this change: both launcher files also end with `--enable-manager`,
which `BackendManager.primary_argv` does not pass.

Outcome so far. The flag takes effect — the loader reported `13,870 / 14,250 MB usable` on PID 4916
(started 20:59:22) against `12,436 / 12,817 MB` at reserve 2. But the one Qwen job run since
(`f29937b7-478f-4598-b756-661305d18ed9`, prompt `0603c5be-0321-4325-ae5f-9a268b94d605`) failed at
44.93 s right after `Requested to load QwenImage` with `DefaultCPUAllocator: not enough memory
(4,377,600 bytes)` and printed no load line at all (`C:/AI/logs/20260912-205922-error.log`), while
host commit went 60 % → 87 % and `POST /free` did not release it. **Measured: the reserve does not
move the host-commit ceiling** (#77). The narrow exit test — `full load: True` for QwenImage at
832×1216 with two references — is still unobserved. Detail in
[`docs/RUNTIME-PRECONDITIONS.md`](../docs/RUNTIME-PRECONDITIONS.md) §7.

## Measured reserve and one launch path, 23 September 2026 (no ComfyUI source edited, no package changed)

`C:/AI/Start-ComfyUI.ps1` gained an optional `-ArgumentsFile` parameter (the Studio passes
`BackendManager.primary_argv` through it) and its standalone default became `--reserve-vram 4
--disable-pinned-memory` plus the existing flags. SHA-256 before `0c3fbc95bcb27444…` (kept as
`C:/AI/Start-ComfyUI.ps1.bak-20260923-reserve06`), after `ac8b40b650cb5883…`. Why, with the measurements:
[`docs/RUNTIME-PRECONDITIONS.md`](../docs/RUNTIME-PRECONDITIONS.md) §8.

