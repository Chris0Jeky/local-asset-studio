# Reference qualification contract — P35-B-20261125-1

This is a behavioral evidence component. The existing `studio_workflow.qualification` module owns static catalog/graph/model provenance, and the route compiler owns native bindings. This module consumes their frozen identities and declared observations. It cannot submit generation, authenticate a human, change a Library mark, accept an asset for a project, or clear a licence.

## API and frozen suite

The stdlib-only Python 3.12+ module exposes `canonical_hash`, `loads`, `validate_suite`, `resolve_roles`, `calibrate_metric`, `score_case`, `summarize`, `automatic_metrics`, and `rubric_fingerprint`. Values are bounded finite JSON; duplicate JSON keys, non-string object keys, NaN/infinity, booleans as scores, invalid identities and stale hashes refuse. Canonical JSON uses sorted keys, compact separators, `ensure_ascii=False`, UTF-8 and no trailing newline.

`suite.json` is an authored plan, containing no image pixels or invented execution evidence. It contains exactly two cases in each of ten families, three placeholder canon characters A/B/C, three shared seeds (`2026112501`–`2026112503`), and the four route IDs supplied by the route owner. The complete denominator is **20 × 3 × 4 = 240 trials**, or 60 per route and six per family per route. These are bounded pilot counts, not a statistical guarantee of generalization.

Suite shape:

```text
schema, id, evidence_mode, canon[], routes[], route_pins{}, seeds[], minimum_score, cases[]
canon row: id, label, reference_sha256
case: id, family, title, brief, subject_ids[], references[], [route_inputs{}]
reference: id, subject_id|null, roles[], sha256|null, source_group, claims{}
```

Supported evidence modes are `planned`, `synthetic`, `prospective`, and `owner_library`. Planned and synthetic evidence cannot produce `qualification_complete`. Missing reference bytes and route pins remain null and block readiness. A complete family needs at least two cases; the supplied suite has exactly two. Cases may record optional actual `route_inputs`, keyed by route ID, whose lists include `source_group` and an actual SHA-256; native representation/file/renderer fields are retained and hashed, while the route owner validates their binding. This prevents a corrected skeleton's bytes from disappearing behind the original RGB donor identity.

`validate_suite(suite)` returns `suite`, `suite_sha256`, `trials`, `coverage`, `blockers`, `ready`, and explicit false authority flags. Each expanded trial contains:

```text
id, suite_sha256, case_sha256, references_sha256, case_id,
route_id, route_sha256, seed, rubric_sha256, case, minimum_score,
[route_inputs_sha256]
```

The trial ID hashes all of those identity fields except the full `case` copy and `minimum_score`. The latter is bound by `rubric_sha256`, which hashes the complete axis names, anchors, schema and minimum score. The entire actual-input map is already in the case and suite hashes; the per-route actual-input hash is also included when present.

`resolve_roles(references, route)` accepts a capability projection `{id, supported_roles, max_references, per_subject}` from the route owner. It normalizes outfit to the existing costume vocabulary, preserves subject IDs, and reports explicit metadata contradictions for the same subject/role/attribute. Distinct subjects do not create a conflict merely because they differ. Unsupported roles, capacity excess, unresolved image bytes and unsupported per-subject conditioning block a runnable result. It never guesses conflicts from imagery and never silently reassigns scene/detail/style to another role. A semantic role declaration does not prove native enforcement of that role.

## Review and receipt adapter

`score_case(expanded_trial, receipt)` accepts:

```text
trial_id
status: completed | failed | cancelled | submission_uncertain | unsupported
lineage: suite_sha256, case_sha256, references_sha256, route_sha256,
         seed, rubric_sha256, [route_inputs_sha256]
         + completed outputs: graph_sha256, model_set_sha256,
           preprocessing_sha256, settings_sha256, environment_sha256,
           job_id, prompt_id
output_sha256: SHA-256 | null
review: object | null
cost: attempts, retry_count, runtime_seconds, peak_vram_bytes,
      peak_ram_bytes, operator_seconds
reason: nonempty text
[automatic: observation object]
```

Incomplete execution has no completed output or output review. Unsupported cells have zero attempts/retries and null or zero generation resource measurements. Unknown costs are null; retries account for every additional attempt. The collector must retain the underlying attempt ledger, failed jobs, uncertain submissions and measurement receipts. A count supplied to this pure evaluator is a declaration, not independent verification of that ledger.

The review object contains `reviewer_id`, `reviewer_kind` (`human` or `agent`), `reviewer_role` (`owner`, `reviewer`, or `agent`), `output_sha256`, `case_sha256`, `scores`, and `notes`. `scores` is a map from every declared subject ID to all six axes. Multi-character identity and outfit checks cannot be collapsed into a single average. Every score is an integer **0–4**, or null when unobserved:

| Axis | 0 anchor | 3 anchor | 4 anchor |
|---|---|---|---|
| Identity | Different or swapped subject | Recognizable; minor repair | Strong declared identity match |
| Outfit/detail | Wrong outfit or required detail absent | Required outfit/details mostly faithful | All distinguishing details retained |
| Pose/geometry | Different pose or camera | Pose/camera meet brief with minor errors | Strong declared pose/camera match |
| Style | Conflicting style | Requested style largely consistent | Strong consistent style |
| Anatomy/contact | Broken topology or impossible contact | Plausible body, contact and support | Coherent anatomy, occlusion, contact and support |
| Composition | Wrong framing, scene or arrangement | Composition/scene mostly met | Strong framing, scene and subject-position adherence |

Intermediate anchors are stored in `ANCHORS` and participate in rubric identity. The conservative minimum across subjects is reported separately for every axis. No weighted overall score can compensate for a failed axis. Missing subjects/axes, null scores and agent observations do not become a human rubric pass. Local reviewer names remain declarations, not authentication. A human reviewer passing the rubric does not become an owner Keep, project acceptance, or licence decision.

Failures produce specific repair recommendations for geometry, identity drift, costume/detail loss, style, anatomy/contact and composition. Every recommendation requires a new candidate and preserving accepted regions; it grants no write or execution authority. Actual protected masks and pixel checks belong in the repair evidence.

## Owner calibration and kill rule

Existing Library vocabulary maps `selected` → Keep and `rejected` → Not this. `needs_work` and `unreviewed` are retained as explicit exclusions from the frozen binary cohort, with counts. The Workspace mark itself does not record authenticated ownership; Review Desk reviewer declarations are also not authentication. An agent verdict or an unspecified reviewer must not be imported as an owner mark.

`calibrate_metric(spec, rows)` requires a frozen specification with:

```text
schema: studio.metric-calibration/v1
id, kind, source, threshold, direction, frozen_at, holdout_revealed_at,
development_groups[], cohort[], owner_declaration|null, spec_sha256,
[rubric_sha256], [scope]
cohort row: asset_id, output_sha256, source_group, split,
            owner_mark, owner_id, label_source, [route_id], [family]
prediction row: asset_id, output_sha256, source_group,
                value|null, spec_sha256, scored_at
```

Kinds are `subjective_rubric`, `geometry`, `palette` or `protection`. Sources are `synthetic` or `owner_library`. `spec_sha256` hashes the specification with that field removed. Training, tuning and holdout source groups cannot overlap; identical output bytes and duplicate/contradictory asset marks refuse. Crops, repairs, resizes and descendants must share a source group when the corpus is prepared. The algorithm can check declared groups and exact duplicate bytes, but cannot discover undeclared visual ancestry without those source records.

Freeze the metric and threshold before scoring holdout, score blind to the holdout labels, then reveal labels. Prediction timestamps must fall after freeze and before reveal. Changing a threshold requires a newly frozen protocol and untouched holdout; rehashing after inspecting the old holdout is not valid evidence. Use actual source-captured timestamps and blinded review events, not invented timestamps.

The frozen holdout denominator includes missing and abstained predictions. A complete result needs both labels (at least two rows each); this minimum is a mechanical guard, not a claim of statistical power. Agreement is null when predictions are incomplete. The report exposes false passes separately. **One disagreement of either direction on any available frozen-spec owner mark, including training or tuning rows, disables the candidate metric.** Agreement itself retains the heldout denominator. No average accuracy threshold overrides that kill rule.

An owner declaration binds `owner_id`, the cohort's `snapshot_sha256`, actual statement text and its `statement_sha256`, `source_reference`, `kind=recorded_owner_statement`, and `confirms_own_marks=true`. These fields must come from the actual owner's recorded statement about their existing marks. This pure function does not authenticate the statement: `owner_authenticated` is always false. Synthetic fixtures cannot enable gating, even when their predictions agree perfectly. No owner corpus or declaration was available in this build.

Only a concordant subjective rubric with declared owner evidence can enable the screening flag, and it must name the exact `rubric_sha256`. Its frozen `scope` must contain `suite_sha256`, `route_ids`, `families`, `implementation_sha256`, `preprocessing_sha256`, `model_sha256`, and `method`. `method=human_rubric` explicitly declares no automated model (`model_sha256=null`); `automated_metric` requires an actual model hash. The implementation/preprocessing/model identities must come from the measurement producer's receipt; a hash declaration by itself does not verify those bytes.

Each scoped route/family pair must contain both Keep and Not this holdout marks, with their route/family recorded on the cohort rows. A narrow or foreign-scope calibration cannot qualify the broader suite. `summarize` requires exact suite identity and the complete named route/family coverage, recomputes calibration from its retained `inputs`, checks rubric identity and ignores a caller's forged `gating_enabled` flag. Geometry, palette and pixel-protection metrics remain diagnostic. Screening never grants autonomous artistic acceptance.

## Reports, measurements and remaining limits

`summarize(full_suite, receipts, calibration=None)` re-enumerates the complete suite; callers cannot supply a shortened trial list as the denominator. It rejects duplicate/unknown receipts and repeated completed-output hashes across distinct cells, reports every route and every named family, preserves failures/cancellations/uncertain/missing/unsupported trials, and requires all planned family trials to meet the human rubric before reporting complete qualification. Unsupported multi-character cells remain visible for the present single-subject routes. Costs expose observed sums/counts and null complete totals when evidence is missing. First-pass rates require one attempt and no retry. All output review, execution, owner acceptance and rights states remain distinct.

`automatic_metrics` calculates only supplied observations: PCK uses the declared reference bounding-box diagonal, confidence/visibility metadata and no Procrustes or fitted alignment; low confidence or insufficient visible evidence returns null. Silhouette IoU compares supplied binary grids and empty unions return null. Palette delta is Euclidean ΔE76 over supplied Lab values; it is not image quality or an extracted style score. Protected pixels require matching sRGB RGBA8 canvases, explicit binary protection and exact equality; changed canvas shape refuses and an empty protected region returns null. Inputs must come from the frozen reference/measurement protocol; the function neither detects pose nor authenticates supplied masks or pixels.

The deterministic demonstrations and tests prove software behavior only. They contain synthetic numbers and placeholder identities, with no generations or inspected owner artwork. Wider full-repository testing, actual local execution, actual owner calibration, native route qualification and project acceptance remain separate evidence.
