# Runbook: from the research delivery to the first measured pilot

Run from the repository root with its supported Python/Pillow environment. Do not install archived requirements or alter ComfyUI/Torch. These commands are offline. Existing files are never overwritten; choose new output names. Preserve one writer per workspace.

## 1. Restore the original delivery

Download the already supplied `character-consistency-kit.zip` to this computer. Its exact identity and all 71 members are in `research/character-consistency/archive-lock.json`. Substitute its real local path below; the importer performs no network request.

```console
python scripts/character_archive.py "PATH/TO/character-consistency-kit.zip" --out experiments/runs/character-research-v1
```

The new directory contains `IMPORT-RECEIPT.json` and `character-consistency-kit/`. The full historical report, prompts, guide, original source PNGs, crops, schemas, pilot CSV and tools are preserved byte-for-byte. Open `character-consistency-kit/field-guide.html` in a browser only as an explicit user action. Imported code is never executed by the importer.

The original guide is a historical research tool, not the new Studio UI. A saved guide decision does not authorize a model job. Keep this archive in local backups; Git stores its checksums and integration code, not the large binary delivery.

## 2. Prove the media stage without a model

```console
python scripts/character_media.py inspect experiments/runs/character-research-v1/character-consistency-kit/sources/standard.png
python scripts/character_media.py extract --root experiments/runs/character-research-v1/character-consistency-kit --manifest experiments/runs/character-research-v1/character-consistency-kit/manifests/standard.json --out experiments/runs/character-standard-crops-v1
python scripts/character_media.py compose --extracted experiments/runs/character-standard-crops-v1 --out experiments/runs/character-standard-review-v1.png
```

The result is an opaque **review card** from supplied pixels, not new AI art or an animation. This demonstration template supports four views, two portraits and seven actions. The future production template with four portraits is a distinct W3 deliverable. Rectangular crops can contain adjacent artwork; inspect them before treating them as references.

For a reviewed candidate repair, export a grayscale L-mode PNG mask from the editor with exactly 0 outside the repair and 255 inside. Optional intermediate values blend. Then:

```console
python scripts/character_media.py protected-composite --source SOURCE.png --candidate CANDIDATE.png --mask GRAYSCALE-MASK.png --out NEW-COMPOSITE.png
```

This convention is **not** ComfyUI's inverse-alpha convention. Source/candidate must be RGB or RGBA PNGs with the same size and embedded ICC bytes. Empty masks and masks with no exactly protected pixels are rejected. Verify the printed receipt, seams and actual repair quality. No semantic improvement is inferred from exact outside-mask preservation.

## 3. Prepare a draft study and inspect blockers

The example separates identity, standard costume, full-figure representation and rendering style. It references the restored standard crops with real hashes. It deliberately remains draft and has no owner approval.

```console
python scripts/character_study.py plan --canon research/character-consistency/canon.example.json --study research/character-consistency/pilot.study.json --out experiments/runs/character-pilot-draft-v1.json
python scripts/character_study.py preflight --plan experiments/runs/character-pilot-draft-v1.json --workspace experiments/runs/character-research-v1/character-consistency-kit --out experiments/runs/character-pilot-preflight-v1.json
python scripts/character_study.py summarize --plan experiments/runs/character-pilot-draft-v1.json --records research/character-consistency/empty-records.json --workspace experiments/runs/character-research-v1/character-consistency-kit --out experiments/runs/character-pilot-empty-v1.json
```

Preflight's successful CLI exit means it wrote a report, **not** that generation is authorized. Read `reference_and_canon_checks_passed`, `blockers` and `submission_authorized` (always false here). A correctly restored example has one intended blocker: the draft design is not explicitly owner-approved. Empty measurements remain null; coverage zero is not evidence of a failed model.

## 4. Record an actual design decision, not an inferred one

Resolve hidden back construction and confirm the desired character/costume. For a new original character, replace descriptions/references and byte hashes; increment the canon revision. Keep all prior files. The ordinary next action is to prepare alternatives, not to invent what the owner accepted.

Only after the decision exists, record it with the actual reviewer and their note:

```console
python scripts/character_study.py attest-canon --canon PATH/TO/REVIEWED-CANON.json --reviewer ACTUAL-REVIEWER --reviewer-kind human --note "ACTUAL RECORDED DESIGN DECISION" --out experiments/runs/character-canon-approved-v1.json
python scripts/character_study.py plan --canon experiments/runs/character-canon-approved-v1.json --study research/character-consistency/pilot.study.json --out experiments/runs/character-pilot-approved-v1.json
```

An agent can instead use `--reviewer-kind agent`, which records selection but does not unlock the human-approved gate. The CLI cannot authenticate the person named. Changing design or references after approval invalidates it; create a new revision and retain prior decisions.

## 5. Produce case-level handoff evidence

Read a case ID from the new plan's `cases` array. IDs change when canon/request changes; never hardcode an ID from the draft into the approved plan.

```console
python scripts/character_study.py brief --plan experiments/runs/character-pilot-approved-v1.json --case CASE-ID-FROM-THAT-PLAN --out experiments/runs/character-case-brief-v1.json
python scripts/character_study.py handoff --plan experiments/runs/character-pilot-approved-v1.json --case CASE-ID-FROM-THAT-PLAN --workspace experiments/runs/character-research-v1/character-consistency-kit --out experiments/runs/character-case-handoff-v1.json
```

The brief conforms to the existing game-assets v1 route. The handoff pins the **current** real catalog entry and raw graph and lists reference uploads/roles in order. It supplies positive text and seed proposals only. It deliberately supplies no armed Studio submission payload. Complete actual upload, live nodes/models, resize/crop, batch-size-one and shared-budget preflight before normal Studio Prepare/Generate. Do not POST this handoff as a graph.

### Optional v2 portrait prompt scope

The v1 pilot and every retained v1 plan, brief and handoff remain byte-for-byte legacy artifacts. A new request with `schema_version: 2` may give a task a `prompt_scope` object. Each selected section is one of `identity`, `costume`, `representation` or `style`, with exactly a boolean `description` and an `invariant_indexes` list. A selected section must include its description or at least one zero-based invariant index. Unknown sections and fields, boolean indexes, duplicate indexes, out-of-range indexes and empty selections are rejected.

The compiler always renders section and invariant text in the canon's original order, regardless of the request object's key or index order. Omit `prompt_scope` from a v2 task to render the full legacy canon text. A scoped task changes its case and plan identity. It never supplies replacement text or new canon facts, and its generic game-asset brief remains schema v1.

`handoff` for a v2 plan is schema v2 and includes `prompt_context`: `all-canon` or `selected-canon`, plus the exact selected description (or `null`) and original index/text pairs. This is an audit record only; omitted canon text is never appended to the positive control. The prepared handoff still pins the full approved canon, references, catalog and graph, and still contains no submission payload.

The checked-in `research/character-consistency/portrait-prompt-scope.study.json` is a two-case, one-route, two-attempt planning example. It pairs the same `portrait-calm` reference, instruction, checks and seed for an all-canon wink edit and a selected-canon wink edit. It is a prompt-scope hypothesis only; it records no generation, neural cause or art approval.

The first primary-case import POSTs an object to `/api/production` with `character_plan`,
`character_handoff`, ordered uploaded `{reference_id,file}` entries, `name` and `max_seconds`.
It verifies the self-hash, canon approval attestation (not identity authentication), raw catalog/template
pins, exact approved references and slot roles before creating one ordinary planned comparison. It queues
nothing; Start remains explicit. Caller controls, batch settings, parents and attempt kinds are rejected.

Twelve attempts belong to the entire study, not each case brief. No extra image-producing warmups, repairs or blind retries are allowed by the pilot. Keep actual prompt IDs. Response loss means reconcile, not submit again. Follow #64/#65 and the existing game-assets agent contract.

## 6. Record attempts and reviews

For cases imported through Production, [collect saved study results](PRODUCTION-RESULTS.md)
to produce the records and summary directly from retained jobs and Workspace
outputs. It performs no generation and leaves reviews empty. The manual record
contract below remains available for explicit assessments and older evidence.

Records are a JSON array. Each record requires `id`, `plan_sha256`, `case_id`, `kind` (primary/repair/warmup), `state` (completed/failed/cancelled/submission_uncertain), `parent_attempt_id`, `prompt_id`, `output`, `execution_evidence`, `elapsed_seconds`, `cleanup_seconds`, and `review`.

Output/evidence references use `{ "path": "workspace-relative-file", "sha256": "actual-64-hex-digest" }`. Evidence is mandatory even for failures. Noncompleted `output` is null; retain partials through the evidence record. A completed neural attempt must keep its actual prompt ID. Measurements are finite nonnegative numbers or null. One record represents one expensive attempt; it is not proof the external executor obeyed the count.

Review is null or an object with `reviewer`, `reviewer_kind`, `decision` (selected/rejected/needs_review/accepted), `checks` (exact required IDs mapped to pass/fail/not_visible/uncertain), `note`, and `output_sha256`. Selected/accepted needs all required checks to pass. Accepted requires a human attestation; agent selection stays distinct. Retain earlier assessment files when changing decisions. Hashing a note cannot prove its truth.

```console
python scripts/character_study.py summarize --plan experiments/runs/character-pilot-approved-v1.json --records PATH/TO/ACTUAL-ATTEMPTS.json --workspace PATH/TO/WORKSPACE --out experiments/runs/character-pilot-results-v1.json
```

All referenced canon/evidence/output files must be inside that workspace. Place copies there with exact hashes or branch the canon explicitly; do not silently change reference paths after approval. Summaries reject stale hashes, duplicate primary attempts, wrong-parent repairs, budget overruns and attempts after unresolved uncertainty. A reconciled result is a new retained assessment snapshot, not deletion of the uncertain evidence.

## 7. Promote only the demonstrated layer

Run the offline tests and full repository checks. The two repository-contract tests exercise actual preset graphs and the existing brief validator in CI; synthetic local tests cannot replace them. Run actual workstation inference separately and record owner review separately again. W3/W4/W5 stay open until their own acceptance evidence exists.

```console
python -m unittest discover -s tests -p "test_character_*.py"
python -m unittest discover -s tests
python scripts/validate-repo.py
```

No current command performs unattended execution or critic inference. #65/#66 are deliberately explicit follow-ups. The existing HUMAN_TODO.md choices are unchanged, including Anima q-3 and the selected production brief.
