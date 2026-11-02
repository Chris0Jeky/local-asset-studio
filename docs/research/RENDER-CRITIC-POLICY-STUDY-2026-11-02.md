# Render-critic policy study: preserve small defects while investigating #1970

## Decision

Do **not** raise the production pixel threshold or silently apply a 0.4% fraction floor to the critic-only sentinel warning. The reported native clean-chest result (26 pixels across four lit views) is one observation, not a control distribution. The new tools make candidate policies reproducible and inspectable **without promoting one**.

This is a CPU-only synthetic experiment, not a Blender render, HIP/Vulkan benchmark, model critique or MIRA acceptance. Existing native jobs, MCP facade, resource admission and the sentinel remain the execution owners. No new queue, runtime package, GPU access or cloud call is introduced.

## Implemented interfaces

`scripts/render_critic_policy.py` provides:

- `decide(receipt, min_fraction)`: pure decision over the existing critic's raw `pixel_diff`, `view_sizes` and `pixel_policy`; returns a separate `las.render-critic-review-hypothesis.v1` record. It never mutates the receipt.
- `replay(receipt_path, out_path, min_fraction)`: bounded 2 MiB JSON input, duplicate/non-finite JSON-key/value refusal, SHA-256 identity of the exact read bytes, and exclusive creation of a new output. Missing, invalid or legacy dimension-less evidence is `incomplete` and requires review.
- Explicit CLI exit status: 0 means the **hypothetical policy** does not request review; 1 means it does; 2 means incomplete/invalid input. None means artistic acceptance or native visual parity.

The raw aggregate gate remains recorded `min_pixels` over recorded channel level. The exploratory floor checks **each view independently**, escalating if any exceeds the fraction; extra unchanged views cannot dilute a local change. A size mismatch always requires review. Raw `changed` is checked against the recorded counts/gate; contradictory receipts are incomplete. The tool does not authenticate externally supplied receipts or capture settings. Use existing asset/capture provenance for that trust boundary.

`below_floor` means exactly that, **not** "noise confirmed". `raw_gate_quiet` means the original pixel gate did not fire, not equality. Unsupported sample policies and missing dimensions are never repaired by inventing a default resolution.

`scripts/render_critic_study.py` creates a new owned-fixture directory, executes the real comparator with `diff_only=True`, and retains original reference/candidate PNGs, raw receipts, alternative decisions, implementation hashes, Python/Pillow versions and an HTML comparison table. It accepts at most the three fixed resolutions 96, 256 and 512. Repeated runs are deterministic in the same environment; existing output directories are refused.

## Executed study — 2 November 2026

Eight cases at each of three resolutions (24 related synthetic cases): unchanged, a seven-level sub-threshold change, 26 dispersed pixels across four views, coherent 25- and 171-pixel patches, a larger patch, alpha-only loss, and dimension mismatch. The dispersed case is labelled nuisance **by construction**; these are not measured samples of native Cycles noise. The coherent cases are labelled defects by their construction, not human assessment of real art.

| Hypothetical per-view floor | True positives | False positives | True negatives | False negatives | Incomplete |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 (raw gate) | 15 | 3 | 6 | 0 | 0 |
| 0.001 (0.1%) | 12 | 0 | 9 | 3 | 0 |
| 0.004 (0.4%) | 10 | 0 | 9 | 5 | 0 |

A 171-pixel patch is 1.8555% of a 96x96 view, 0.2609% of 256x256, and 0.0652% of 512x512. It survives the 0.4% policy only at 96px. This is a deliberate fixed-pixel counterexample, not a claim about equivalent world-space defects rendered at different resolutions. A 25-pixel patch is suppressed by that floor at every tested resolution.

The experiment **falsifies the proposal that removing the observed tiny alarm with a blanket fraction floor is automatically a safe improvement**. It does not prove the old policy is sufficiently sensitive, establish a production-optimal threshold, or estimate a population error rate. The 24 constructed variants are correlated and must not be presented as independent statistical trials.

## Reproduce without new installations or inference

From the repository root with its existing Python/Pillow environment:

```console
python -m unittest discover -s tests -p "test_render_critic*.py" -v
python scripts/render_critic_study.py --out-dir .runtime/critic-policy-study-NEW
python scripts/render_critic_policy.py replay .runtime/critic-policy-study-NEW/256-defect171/receipt.json --fraction 0.004 --out .runtime/critic-policy-decision-NEW.json
```

Open the study's `index.html` locally. The displayed front-view previews are 192px; raw receipts cover all four views. Inspect original files at native dimensions. Alpha loss can be invisible against a coincidentally matching page background. A replay result includes the original receipt hash; the source receipt and images remain unchanged.

For real retained native captures, use the existing `render_critic.py check ... --reference ... --diff-only` command with explicitly paired view lists to produce a new full receipt. The older sentinel's summarized `second_signal` lacks dimensions and is intentionally insufficient. Do not guess them from a file name or this study.

## Native qualification experiment (not executed by this pass)

**Question:** Can critic-only nuisance alarms be reduced while retaining meaningful small defects on held-out scenes?

**Hypothesis:** fixed capture conditions plus repeated control evidence, scored separately by view/pass/region, can distinguish nuisance differences better than a global changed-area threshold.

**Inputs:** the owned articulated chest and known-bad corpus already used by the lab; explicit configured Blender executable paths; source SHA-256; exact export settings; existing camera/light/color/render contract. Retain the installed versions and environment. Use copied assets only.

**Bound:** initially three repeated unchanged export/reimport runs per configured executable, plus one existing defective-corpus replay. Use the existing native process timeout/resource owner, not a new launcher or unleased parallel GPU workload. Record planned cost before starting. Stop on missing evidence, source mutation, job uncertainty, backend errors or resource refusal; never automatically resubmit an uncertain native run.

**Procedure:**

1. Freeze the scope before measurement: source/export/import identities, cameras, frame numbers, image size, engine/backend, seed, adaptive sampling and denoising settings, color transform and precision. Capture actual state; version labels alone are insufficient.
2. Retain source-versus-source repeated controls separately from source-versus-GLB-reimport controls. The latter include format/shader/geometry differences, not only random renderer noise.
3. Re-score retained lit images through the repaired critic offline, keeping every per-view count, image hash and size. Do not let a vision model decide whether missing evidence is complete.
4. Partition scene/pose families into policy-development and held-out evaluation sets **before** trying floors. Copies, resolutions and camera views of one case are not independent samples.
5. Include small material marks, thin silhouettes, alpha changes and wrong/missing parts. Report the raw detector and each proposed review policy separately; disclose suppressed true defects as well as cleared nuisance alarms.
6. Examine localization and repeated difference masks. A future per-region noise envelope is a research proposal, not implemented here: correlated edges, denoiser instability and occlusion can invalidate a naive noise mask.
7. Promote only an explicitly selected policy whose held-out trade-off is acceptable. Preserve the raw signal and implementation identity. Human artistic preference remains a separate decision.

**Success:** fewer confirmed nuisance reviews with no newly missed mandatory defect categories in the held-out set, complete receipts and unchanged sources. **Failure:** a small real defect is hidden, incomplete evidence is treated as clean, or apparent improvement exists only on the tuning set. **Next decision:** integrate an explicitly versioned policy at the existing sentinel boundary, or leave its conservative raw warning intact. #1970 remains open until native qualification.

## Research basis and limitations

- [Pillow Concepts](https://pillow.readthedocs.io/en/stable/handbook/concepts.html), checked 2 November 2026: RGB is an 8-bit-per-channel mode; it does not establish source precision. This motivated admission checks before interpreting decoded samples.
- [Pillow TIFF source](https://pillow.readthedocs.io/en/latest/_modules/PIL/TiffImagePlugin.html), checked 2 November 2026: the loader maps RGB16 TIFF to RGB; the new core regression verifies this with a handcrafted valid TIFF, not a mocked image.
- [Blender Cycles sampling patterns](https://developer.blender.org/docs/features/cycles/sampling_patterns/), checked 2 November 2026: adaptive sampling progressively allocates samples. Capture conditions matter; this source does not supply a LAS noise floor.
- [NIST exact binomial confidence limits](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm), checked 2 November 2026: small counts need appropriate uncertainty analysis. No confidence interval is assigned to this deliberately correlated fixture set.

These are implementation references and experimental reasoning, not a re-verification of every earlier research report's hardware or product claim.

## Saved-observation continuation

The [follow-up on truthful critic availability and saved-result replay](CRITIC-OBSERVATION-CONTINUATION-2026-11-02.md)
fixes #1977 without changing this experiment's thresholds. Its
[repository-retained observations](../../research/agentic-creation/critic-observations/README.md)
make every synthetic decision reproducible from Git. New sentinel results carry
complete observations; use the explicit `--input-kind sentinel` replay mode.
