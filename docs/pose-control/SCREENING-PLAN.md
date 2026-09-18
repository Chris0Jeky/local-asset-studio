# Corrected-pose screening plan contract

This is the executable **planning** slice of the eight-case protocol in
[`EXPERIMENTS.md`](EXPERIMENTS.md). It validates one frozen manifest and enumerates the campaign before
any model is loaded or any image attempt is reserved. It does not connect to the Studio, Production,
ComfyUI, the Workspace or a provider.

## What it guarantees

The compiler accepts only this campaign shape:

- eight cases in the reviewed order;
- three distinct route contracts: Klein geometry-reference, Copy Pose RGB and SDXL with a precomputed
  corrected skeleton;
- two first-pass cells per case and route;
- cases 1–7 use route-local `replicate_a` and `replicate_b` seeds;
- case 8 uses `baseline` and `variant` at the same route-local counterfactual seed;
- exactly **48** first-pass cells;
- zero repair, retry, warm-up or other image-producing slots;
- zero execution authority and zero generation submission.

The manifest must pin model, encoder, VAE, graph, node-set, runtime and reference-transform identities.
Klein also pins its renderer, Copy Pose pins its LoRA, and SDXL pins both ControlNet and renderer. The SDXL
route is accepted only as `bypass-precomputed-guide`; silently running the corrected guide back through a
pose detector is a contract failure.

The checked-in manifest is deliberately synthetic. Repeated-character hashes are not provider evidence or
installed-runtime qualification. Real source bytes remain outside Git. Before a campaign can run, a reviewed
preflight must replace every synthetic pin and local source reference with retained evidence from the exact
machine and route.

## Commands

```console
python scripts/pose_screening.py validate examples/pose-control/screening-manifest.json
python scripts/pose_screening.py plan examples/pose-control/screening-manifest.json --out screening-plan.json
python scripts/pose_screening.py validate-plan examples/pose-control/screening-manifest.json screening-plan.json
```

`plan` uses exclusive creation and will not overwrite an existing plan. `validate-plan` recompiles from the
manifest and requires exact equality, including order, route-local seeds, pair grouping and deterministic
identities. Every success and error record states that execution is unauthorized and generation was not
submitted.

## Data boundary

A plan cell identifies a case, source reference, route, input representation, slot and seed. It does not carry
private source bytes, a prepared graph, a Production reservation, a prompt ID or a job ID. `source_ref` is a
bounded identifier, not a path, URL or proof that a source was reviewed. A `plan_id` is a content identity,
not an approval.

The compiler also preserves the campaign stop conditions:

1. uncertain dispatch;
2. invalid binding;
3. runtime instability;
4. exhausted candidate cap.

Two consecutive repeats of the same defect remain the review threshold. That threshold does not grant an
automatic retry.

## What remains for issue #446

This slice delivers the machine-readable campaign definition, exact arithmetic, route/pin shape, deterministic
cell ledger and agent-safe validation CLI. It does **not** complete the issue. Remaining work is:

- qualify and pin the real installed route identities under #445;
- select and review the eight real source situations without committing private media;
- run the separately authorized 48-cell campaign through existing Studio/Production services;
- retain every reservation, actual attempt, failure class and timing component;
- complete per-axis human review and the final failure-inclusive report;
- leave HUMAN_TODO q-28 open until the owner reviews actual images.

No result from these software checks is artistic acceptance, route promotion, rights clearance or evidence of
a held-out success rate.
