# Evaluation and qualification

## Objective

Measure whether a route or control produces **accepted distinct tasks with less failure and cleanup**, not whether its prompt looks sophisticated or selected examples are attractive.

## Corpus

The public machine-readable corpus is synthetic and non-executing. Real references and owner decisions stay in Workspace/ignored run evidence. Split held-out cases by identity, costume and source situation.

Required lanes include:

- original adult character from text;
- canon identity in a new outfit;
- identity in a new pose;
- identity plus separate pose;
- identity, outfit and style from separate references;
- silhouette/proportion control;
- difficult camera and foreshortening;
- material and lighting study;
- editorial/pin-up, fashion, swim, hot-spring, fantasy, sci-fi, street, comedy and action;
- two adults with a spatial relationship/contact;
- three-pose character sheet;
- local wardrobe edit;
- local anatomy/contact repair;
- conflicting references;
- already-correct anatomy;
- legitimate occlusion.

All subjects are declared adult through reviewed metadata. Public briefs remain non-explicit.

Named genre cases also bind fixed scenario outcomes; generic control IDs alone cannot qualify a pack. The street-fashion case requires one composed street outfit, a recognizable street-level urban setting, mixed urban practical lighting affecting subject and scene, and framing that keeps the outfit readable.

## Route smoke test

For every exact candidate configuration:

- fixed subset of tasks;
- two seeds/noise initialisations where the route supports them;
- route-native documented resolution/settings;
- batch accounting by actual candidate;
- no hidden rerolls;
- every failure retained.

The smoke test eliminates binding, resource, severe adherence and terms mismatches. It is not a quality ranking.

## Finalist comparison

Promote at most a small number of routes for deeper evaluation. Within one exact route compare:

1. unchanged short brief;
2. concise manually clarified brief;
3. profile-compiled prompt/instruction.

Keep source images, graph, model, resolution and non-prompt settings fixed. Across different architectures, report separate resource and output evidence rather than pretending an equal seed/step count is matched compute.

## Adapter qualification

For each adapter:

- fixed route, brief, seed and resolution;
- baseline weight 0;
- at least four bounded weights;
- several seeds and both ordinary/difficult poses;
- intended effect plus collateral checks;
- primary identity-adapter pair tests;
- full stack only after important pairs.

A slider is promoted only over an interval with acceptably ordered response. Record prompt dependence and variance; do not average incompatible behaviours into a “strength.”

## Measures

Do not collapse these into one score:

- subject count and hard constraints;
- adult/content envelope;
- identity per subject;
- body/silhouette;
- outfit, coverage and material;
- pose, camera, relationship and contact;
- intended reference transfer;
- leakage from ignored source facets;
- expression/gaze;
- scene, palette, lighting and style;
- anatomy as pass/fail/not-visible/uncertain;
- exact outside-mask preservation where applicable;
- final-size line and texture quality;
- accepted distinct tasks within cap;
- attempts, interactions, waiting and cleanup;
- cold/warm/model-switch time;
- peak VRAM, host RAM and Windows commit;
- refusal, unsupported control, no-op, OOM, crash and uncertain submission.

Null means unobserved, not zero.

## Result record contract

`research/adult-illustration/benchmark-result-example.json` is a synthetic, inert example of `studio.adult-illustration-benchmark-result/v1`. It demonstrates how evidence is retained without granting execution or promotion authority.

A result record:

- binds the exact benchmark-corpus and route-candidate Git blob identities;
- requires the corpus, route manifest and result to declare the same lowercase 40-hex source baseline;
- uses a real ISO calendar date rather than arbitrary date-shaped text;
- names the selected cases, phase, route and prompt variant;
- records a declared cap but does not create or expand an allowance;
- requires non-synthetic evidence to pin route configuration, graph, source set, external campaign and authorization references;
- retains one record for every actual candidate, including refusals, unsupported controls, no-ops, OOMs, crashes, binding faults, cancellations and uncertain submissions;
- requires contiguous candidate ordinals and exact attempted/retained/accepted accounting;
- counts uncertain submissions and failed batch members against the real candidate total;
- records candidate acceptance separately from human review, adult-envelope review, artistic acceptance and rights review;
- contains every corpus measurement exactly once;
- distinguishes `unobserved`, `not_applicable`, `observed` and `uncertain` measurements;
- requires observed ratios to use valid numerators/denominators and retained evidence;
- keeps decisions content-addressed but still requires human approval and evidence for consequential non-synthetic outcomes;
- requires route-promotion/rejection outcomes to target routes and control-rejection outcomes to target controls;
- always keeps `promotion_authorized: false`; a result describes evidence and never performs promotion.

Validate the checked-in example and its exact dependencies with:

```console
python scripts/validate_adult_illustration_benchmark_result.py
python -m unittest tests.test_adult_illustration_benchmark_result -v
python -m unittest tests.test_adult_illustration_benchmark_result_cli -v
python -m unittest tests.test_adult_illustration_benchmark_result_integrity -v
```

Changing the corpus or route manifest makes the example stale until it is explicitly reviewed and regenerated. Recomputing `result_id` cannot make inconsistent accounting, invented case/route IDs, hidden attempts, invalid measurements, baseline drift, malformed dates, mismatched decision targets or synthetic promotion valid.

## Automated assistance

Keypoints, OCR, segmentation overlap, pixel diffs, embeddings and VLM observations can support review. They cannot independently approve:

- artistic usefulness;
- identity correctness;
- adult status;
- consent;
- rights/licence;
- route promotion.

The model that generated a proposal is not its sole evaluator.

## Campaign and reliability

- Freeze manifest and cap before dispatch.
- Preview and validation create zero jobs.
- Use existing Production allowances and the shared coordinator.
- Persist dispatch intent and known prompt/job IDs.
- A lost response is observed by retained identity and never blindly replayed.
- Stop on confirmed binding/scope fault, uncertain dispatch, repeated same-hypothesis failure, native crash/OOM or exhausted cap.
- Keep failures, rejected candidates and manual work.

## Promotion decision

A report may:

- promote an exact route/control over a bounded scope;
- narrow its supported interval/tasks;
- keep it experimental;
- reject it;
- record insufficient evidence.

It names exact evidence and remaining uncertainty. It never generalises one configuration to a family, all adult content, all 16 GB systems or commercial suitability.
