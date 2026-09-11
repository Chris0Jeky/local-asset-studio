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
