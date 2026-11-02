# Local render critic: measured trust boundary (2 Nov 2026)

The critic is `scripts/render_critic.py`. It is a stdlib-only client for a local `llama-server` vision model, plus a
pixel-diff gate. `scripts/critic_defect_scene.py` builds its calibration set. Executed evidence comes from the
frontier-lab lane of the 2–3 Nov R&D night. Lab media and raw results stay outside Git, in
`E:/local-asset-studio-labs/rnd-20261102/frontier-lab/`.

## Use it like this

- **With a reference render (parity checks: 4.5 vs 5.4, before vs after an edit), the pixel diff decides.** A pixel
  counts as changed when its largest channel difference exceeds 8. The candidate is changed when at least 20 pixels
  change across its views. It needs no GPU:

```bash
python scripts/render_critic.py check cand/view_front.png cand/view_back.png --reference ref/view_front.png ref/view_back.png --diff-only
```

  Views are matched by filename label. A candidate view with no matching reference view counts as changed. Without
  `--diff-only`, only a changed candidate goes to the model, which then names the defect. An unchanged candidate
  never reaches the model.
- **Without a reference, the model's verdict is a hint, not a gate.** See the table below: so far only `missing_texture`
  and `broken_weights` have held precision.
- **Renders cannot show everything.** Bone-twist loss, damage to skin weights or shape keys, and flipped normals under
  two-sided shading leave the pixels untouched. Keep manifest or structural gates for those (`scripts/blender_lab.py`).

## Measured

### Pixel gate

| set | defects found | false alarms | notes |
|---|---|---|---|
| seeded figures, `set-test` seeds 100–111 (8 defect types × 12) vs `clean-<seed>` | 96/96 | 0/12 | Negatives are 5.4α renders of the clean figures against 4.5.13 renders. Parity noise ≤ 2 px; smallest defect 171 px |
| blender-worker `known-bad-v1b-5.4.0-alpha` (lit, 4 views, 256 px) vs its control | 7/7 render-visible | 0/1 (4.5.13 control vs 5.4 control, ≤ 1 px per view) | The 5 render-invisible defects changed 0 px, matching the corpus's own deterministic baseline |

Recalibrate `DIFF_LEVEL` and `DIFF_MIN_PX` for another scene, sampler or denoiser. Cycles GPU repeats drift by up to
one level (see `BLENDER-BENCHMARK-2026-11-02.md`), and denoisers drift more.

### Model, reference-free

- Model: Qwen3.8-27B (Apache-2.0), ISTA-DASLab GSQ-RCO IQ3_XXS GGUF with the BF16 mmproj.
- Server: llama.cpp b12032 on ROCm0.
- Run: dev set, 27 samples, rubric v1.

| defect type | TP | FP | FN | precision | recall |
|---|---:|---:|---:|---:|---:|
| missing_texture | 3 | 0 | 0 | 1.0 | 1.0 |
| broken_weights | 2 | 0 | 1 | 1.0 | 0.67 |
| backside_hole | 1 | 0 | 2 | 1.0 | 0.33 |
| material_swap | 1 | 3 | 2 | 0.25 | 0.33 |
| asymmetry | 2 | 12 | 1 | 0.14 | 0.67 |
| omitted_mesh | 0 | 2 | 3 | 0.0 | 0.0 |
| flipped_normals | 0 | 1 | 3 | 0.0 | 0.0 |
| white_material | 0 | 0 | 3 | — | 0.0 |
| **any defect (sample level)** | 24 | 3 | 0 | 0.89 | 1.0 |

- **No sample-level discrimination:** the model flagged all three clean samples, so "anything wrong?" carries no
  information without a reference.
- **Stated confidence is uninformative:** it was always 0.90–0.95.
- **It often sees the defect but files it under the wrong type:** a missing eye was reported as asymmetry, and a
  flipped limb as asymmetry.
- **Rubric v2** (in the code) clarifies the taxonomy: a missing partner counts as omitted, not asymmetric; features seen
  from one side only are normal; pose is not asymmetry.
- **Stop list until v2 is measured:** asymmetry, omitted_mesh, flipped_normals, white_material and material_swap. Do
  not act on these labels reference-free.
- See the follow-up runs below. The held-out test set has not been run: the dev results made a test-set run of the
  reference-free labels pointless.

### Model, follow-up runs (2 Nov, 07:29–07:46)

- **Rubric v2, reference-free, dev set:** no improvement.
  - "asymmetry" is the model's fallback whenever it is unsure: 15 false alarms, every clean sample included.
  - The stop list stands. Usable reference-free: `missing_texture` (3/3) and `broken_weights` (precision 1.0, recall
    0.67). `backside_hole` also held precision 1.0 but caught only 1 of 3.
- **blender-worker corpus, with its control as reference:**
  - The gate flags 7/7 render-visible defects and 0/5 invisible ones.
  - The model then names 4 of the 5 mappable defects correctly: material mismatch, missing texture, missing UVs (as
    missing texture), omitted mesh. It labelled the mesh hole as `material_swap`.
  - On an asset it was never tuned on, the model is a useful *namer of a detected change*.
- **The same corpus without a reference:**
  - It flags all 13 entries, the clean control included.
  - Labels are right on 1 of 5.
  - It is not a detector.
- **Real 2D images (waifu-lab concepts and turnaround sheets, reference-free, a 2D sheet rubric):**
  - Both known defects were flagged, one of them under the wrong type.
  - 6 of 9 clean images were also flagged.
  - Not usable reference-free.

### Identity against the owner's Versus presses

- **Set:** contest "Anima reference methods", criterion "Most like the reference character". The owner made 68 presses:
  63 decided, 5 draws. The reference is the adapter's showcase `pilot_girl.jpg`.
- **Data access:** read from the Versus DB in read-only mode.
- **Qwen pairwise** (reference + A + B, 640 px):
  - 36/63 = 57.1 % agreement (one-sided p ≈ 0.16).
  - Flipping the A/B order changed its answer on 30 of 63 pairs.
  - On the 33 pairs where both orders agree, it matched the owner 20 times (60.6 %, p ≈ 0.11).
- **CCIP** (`scripts/identity_score.py`): 27/63 = 42.9 %, also indistinguishable from chance. Its differences bunch at
  0.185–0.212, and it ranks the owner's 11–2 winner near the bottom.
- **Neither is an identity critic for this criterion.**

### Second model: Gemma 4 12B QAT q4_0

Gemma 4 12B (Apache-2.0; `google/gemma-4-12B-it-qat-q4_0-gguf`, sha256 `93567e57…`) ran the same sets as Qwen.

| | Gemma 4 12B | Qwen3.8-27B |
|---|---|---|
| speed: `llama-bench` generation | **71.2 t/s on Vulkan**, 65.3 t/s on ROCm | 1.0 t/s on Vulkan, 7.9 t/s on ROCm |
| dev set, reference-free: missing texture | 2/3 | 3/3 |
| dev set, reference-free: asymmetry false alarms | 19 | 15 |
| corpus with its control as reference: correct labels | 2/5 | 4/5 |
| waifu-lab 2D images: clean images flagged | 2 of 9 | 6 of 9 |
| Versus pairwise: agreement with the owner | 33/63 | 36/63 |
| Versus pairwise: picks position A | 89 % | 33 % |
| Versus pairwise: same answer in both orders | 15 of 63 pairs | 33 of 63 pairs |

- **Speed:** the gap shows Qwen's slowness came from the GSQ-RCO quant, not the card.
- **Verdict:** Gemma 4 12B is faster but a weaker namer, so Qwen stays the critic model. A standard Qwen K-quant would
  probably give Qwen's judgement at Gemma's speed. It is untested: the download was not possible on that night's link.

## Runtime facts (this PC)

- **llama.cpp b12032:** the Windows ROCm 10.0 zip lacks `hipblas.dll`. It ran after copying `hipblas.dll`,
  `rocblas.dll` + `rocblas/`, `rocsolver.dll`, `libhipblaslt.dll` + `hipblaslt/` from ComfyUI's ROCm 7.2.1 wheel into
  the llama.cpp folder.
- **Pin one device:** the Vulkan build also sees the Intel iGPU and by default splits layers across both, which ran at
  about 1 token/s. Always pass `--device Vulkan0` or `ROCm0`.
- **Speed (`llama-bench`, GSQ IQ3_XXS 9.4 GiB, pinned):**
  - Vulkan: prompt 21 t/s, generation 1.0 t/s.
  - ROCm: prompt 114 t/s, generation 7.9 t/s.
  - Both are far below the card's bandwidth, which suggests this mixed-precision quant hits slow kernels.
  - In service, ROCm took about 30 s per 4-view sample (prompt 72 t/s, generation 4.5 t/s).
- **Host memory:** under ROCm, the server holds about 19 GB of private host memory whether or not the weights are mmapped:
  - default load: 19.1 GB private, 17.3 GB working set;
  - `--load-mode none`: 19.2 GB private, 10.7 GB working set.

  `serve` keeps `--load-mode none` (this build has no `--no-mmap`). Stop the server when not in use, because on a 32 GB
  machine that footprint crowds out other work.
- **Serving:**

```bash
python scripts/render_critic.py serve --exe <llama-server.exe> --model <gguf> --mmproj <mmproj.gguf> --device ROCm0
```

  The server listens on loopback 8290. Stop it when not in use.
- **Calibrating:**

```bash
python scripts/render_critic.py eval <set_dir> --out results.jsonl [--reference-root <dir>]
```

```bash
python scripts/render_critic.py score results.jsonl
```

  `score` reports per-type and sample-level precision and recall. Calibration sets come from
  `blender --factory-startup -b --python scripts/critic_defect_scene.py -- <out> <seed> <category>`.

## Calibration set caveat

The `broken_weights` fixture re-weights part of one body part to a distant bone, then rotates that bone. The bone's own
limb (and its hand or shoe) moves with it, so the sample carries a pose change on top of the stretched geometry. Its
pixel and model results therefore measure "weight explosion plus pose change", not the weight damage alone.

## Not verified

- The model on the held-out test set.
- Any model other than the GSQ Qwen. The planned shoot-out was cut short by about 170 KB/s Wi-Fi: Gemma 4 12B arrived
  corrupt, and Gemma 4 26B-A4B and a standard Qwen K-quant were not downloaded.
- Real renders.
- Higher image-token budgets (`--image-min-tokens`).
- Vulkan accuracy, which should match ROCm since the weights are the same but was not run.
