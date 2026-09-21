# Finite qualification and acceptance protocol

This expands report pp. 20-23 into a staged design for existing Experiment Lab/Production owners. It is **planning, not an execution allowance**. The current 48-cell corrected-pose planner (#542/#446) and other existing campaign caps are not expanded by these examples.

## Stage the questions behind the pack

Start with the unreviewed fantasy-pack candidates in HUMAN_TODO q-30. Obtain an owner-selected identity and intended roles, or keep canon unresolved. Use the existing successful route as the baseline. Choose only the diagnostic that could change the next production decision. A full eight-task campaign is an optional later study, not the prerequisite for accepting four pack artifacts.

| Task from the paper | Fixed question and units that must be explicit | First adapted comparison and acceptance axes |
| --- | --- | --- |
| T01-anime-t2i | Original adult anime character, complex costume, hand-held prop and explicit lighting/environment. One frozen brief per cell. | Current accepted-pack route versus exact Aesthetic/Animagine candidate where needed. Costume, required prop, anatomy, composition and independent artistic review. |
| T02-known-character | Authorized/canon-known character without image references, characteristic outfit and prop. | Optional diagnostic, not required for an original-IP pack. Keep character/series vocabulary explicit; do not interpret recognition as rights clearance. |
| T03-original-identity | Approved canon in **three unseen scenes/angles**. Each scene is a subcase, not one hidden multi-output attempt. | Current Klein identity edit/replace route versus runtime-qualified Qwen; SDXL IP-Adapter or OmniGen2 only for a gap. Per-subject face, hair, costume and scene requirements; retained drift. |
| T04-character-pose | Same canon with unrelated target-pose input. Each held-out geometry pair is a separate case. | Current depth/skeleton/Copy Pose baselines, corrected SDXL guide and Qwen challenger. Camera, handedness, torso/limb geometry, costume/identity and leakage separately. Coordinate with #446, do not duplicate its campaign. |
| T05-character-outfit-style | Identity, outfit and style sources intentionally disagree in their donor subjects/palettes. | Native three-slot Qwen only after runtime proof; eligible alternative must represent all roles. Verify no source silently discarded; score role leakage and intended combination, not just attractiveness. |
| T06-two-character-contact | Two identities with specific action/contact and left/right assignment. | Native editor plus explicit multi-person pose when necessary. Count and individual identities, which hand/limb contacts whom, occlusion, anatomy and composition. |
| T07-scoped-edit | **Two separate subcases:** change one costume element; repair a defective hand. Both protect text/background/other content. | Existing protected compositor and measured repaint route, then an exact candidate if needed. Byte-exact effective protection, intended edit, seam quality and no new defects. Include an already-correct hand/legitimate occlusion control before broader automatic repair. |
| T08-character-sheet | Front, three-quarter, profile, back and two expressions from immutable canon. Each generated view counts; packing/layout is a separate operation. | Existing identity/edit/pose/finishing tools. Identity and design consistency per view, addressable figure extraction and reuse; no recursive generated-reference drift. |

## Preflight: zero image attempts

Freeze task/subcase IDs, eligible routes, exact controls/prompts, source identities, role-to-slot order, crop/resize/padding, masks, any guide/encoder artifacts, component hashes/revisions, graph twins, node versions, intended use and runtime fingerprint. Source metadata or a shape-valid synthetic hash is not actual machine attestation.

Record which checks are software contracts, which are resource observations, which require human judgement and which remain unknown. Do not treat native BF16 and Q4+Lightning as one route. Do not treat the same numeric seed as identical noise or difficulty across architectures; it is a repeatability identifier within the declared implementation.

Preflight must identify uncertainty before reservation. A missing weight pin, wrong guide representation, unresolved source roles, unknown canonical identity, incompatible runtime, unreviewed write mask or insufficient headroom produces a reason and no execution. Model acquisition/environment changes, when warranted, are separate operator operations.

## Close the budget before submission

The report proposes seeds **281715418, 918273645, 17012026**, one runtime smoke per route, three seeds per route/task, six T05 reference orders and three T03 crops (`unaltered`, `subject_crop`, `face_crop`). These are **proposed study settings**, not existing campaign authorization.

The report does not specify a single final attempt total: route eligibility, T03's scenes, T07's two subcases, T08's generated views, permutation seeds and whether baseline cells are reused all affect the count. Never label its plan “finite” while leaving these multipliers open.

Before execution, enumerate a unique ID for every **physical image-producing attempt slot**, with task, subcase, route, configuration, seed, source map, transform variant and phase. Calculate:

```text
first_pass = number of enumerated generation slots
hard_cap = first_pass + explicitly_reserved_infrastructure_retry_slots
```

Warmups, repeated cold runs, repair passes, face-restoration passes, alternate views and reference-preprocessing generation count when they produce images. Mere deterministic packing or a non-generative detector call should instead be recorded as a separate measured operation, not hidden in generation time. A retry pool needs both a global cap and a per-cell cap; “one retry” without a scope is ambiguous.

**Small screening example, not the full paper campaign:** two eligible routes, one T03 held-out scene and one T04 pair, three seeds each: `2 × (1 + 1) × 3 = 12` quality slots; two runtime smoke slots; at most two pooled infrastructure retries, no more than one per failed cell: hard cap **16**. This is explicitly a T03 screening subset, not completion of the paper's three-scene T03 task. It must fit within a separately approved allowance or not run.

For order sensitivity, choose one fixed seed and all six permutations, or enumerate every additional seed. Rebind ordinal language so role semantics remain constant. For crop sensitivity, hold route/seed/brief fixed while preserving crop metadata and subject occupancy. Reuse a baseline cell only when all of its identities match; record that it is one physical execution cited by multiple analyses, not multiple independent successes.

## Existing pose campaign is a separate contract

The merged `studio_workflow/pose_screening.py` planner defines **8 cases × 3 routes × 2 slots = 48** first-pass cells in three 16-cell route blocks. Cases 1-7 use route-local replicate seeds; case 8 uses distinct baseline/variant donor references at the same route-local counterfactual seed. It grants **zero retry, repair or warmup slots** and has no execution authority. Its checked-in manifest is synthetic.

Use that planner when asking its corrected-pose question. Do not insert the paper's three seeds, reference permutations, retries or Qwen routes into it and still call the result the same frozen campaign. A changed design needs a newly reviewed manifest and budget, while existing failure evidence remains attached to its original plan.

## Runtime smoke and phase evidence

A separately authorized smoke should answer a specific execution question, not produce a gallery. For Qwen, bind the Q4_K_M checkpoint, Lightning LoRA, multimodal encoder, VAE, graph, prompt/source configuration and runtime. Record outcome even when load fails before sampling.

Use existing `job_resources.py` observations and backend identity. Capture cold load, warm generation, switching, peak VRAM, process RSS, Windows commit, sample coverage and cleanup state only when actually observed. A first run after an established unloaded state can be labelled cold; a first receipt in a folder cannot. A queued Studio job's elapsed time is not pure warm generation time. Two-pass pose-then-face must include both passes and intermediate rejection.

Keep environment tuples distinct. For the Linux candidate, the official ROCm 10.0.0 Radeon row is Ubuntu 24.04.4/HWE 6.17, not the report's GA 6.8. Operator confirmation of the full driver/OS/torch/Comfy/custom-node tuple is still required. Preserve the working Windows baseline and do not perform a runtime upgrade as part of a quality comparison.

Cleanup evidence may include a requested `/free`, observed memory after a declared interval and whether an operator restart was needed. A request is not evidence that resources were released. No observer-driven restart, hidden cleanup retry, queue bypass or new memory sampler belongs here.

## Attempt outcomes, retention and stop rules

Use the existing durable plan/reservation/job identities. Preserve distinctions between a planned slot, admission refusal before dispatch, attempted execution, uncertain dispatch, known failure, generated artifact and completed review. Count admission refusals and reserved slots in their own denominators; a failed dispatched generation consumes its attempt. An OOM is not an unattractive image, and an unattractive image is not an infrastructure failure eligible for retry.

Retain every output and failure record. At minimum classify refusal/admission, OOM, host-commit refusal, worker crash, node error, timeout, wrong identity, wrong pose, role leakage, reference drift, bad anatomy, protected-pixel change and visual rejection. Preserve unknown reasons rather than guessing a failure class from filenames.

Stop for exhausted allowance, uncertain submission, runtime instability, invalid/stale bindings or the declared repeated-defect threshold. Uncertain submission triggers **read-only reconciliation**, never automatic resubmission. No “reroll until nice”, silent repair or discarded failure is permitted by this study design.

## Results: separate facts and judgements

| Layer | Record | Acceptance implication |
| --- | --- | --- |
| Hard contracts | Execution outcome, native slot coverage, required subject count, protected-pixel equality, required text/geometry where measurable | A failed required contract blocks acceptance for that task. Missing measurement remains unknown, not true. |
| Visual review | Identity, anatomy, style, composition, contact and requested change, with reviewer identity/method and uncertainty | Human or independent critic review; the proposing generator cannot be its only approving reviewer. A score is not user acceptance. |
| Owner choice | Role-specific accepted/needs-work/rejected decision and explanation | Only the owner makes the creative acceptance/canon choice. No HUMAN_TODO checkbox is inferred from tests or gallery selection. |
| Effort | Clarifications, prompt edits, source/role/crop edits, mask edits, attempts, operator seconds and tool/view switches | Compare end-to-end effort, including recovery and failed candidates, not just inference latency. |
| Resources | Queue wait, cold/warm execution, analysis, both edit passes, VRAM/RSS/commit peaks, sample gaps, cleanup/restart | Measures the exact route/configuration; no extrapolation from model size or a different OS. |
| Reuse | Accepted parent, derivative relationship, export/reload/continuation and actual downstream source use | The pack is useful only if the asset can be reused with lineage through the shipped Studio. |

OCR can inspect required lettering when a qualified backend exists; taggers can aid vocabulary checks; DWPose can report geometry; embeddings can flag gross drift. None is a sole aesthetic authority. Report detector limits and occlusion, and do not call observed tags the original prompt.

## Protected-pixel test contract

Define the **effective writable support** after every crop, resize, dilation, feather and alpha operation. Everything outside it must equal the decoded source's protected pixel values, including alpha and any required hidden RGB channels. Store source/mask hashes and the comparison method. A PNG re-encode need not preserve container-file bytes; distinguish file-byte identity from decoded RGBA equality.

The compositor applies only the candidate's authorized patch over the original. Tests must cover all-protected/all-writable masks, overlaps, feather boundaries, odd sizes, transparent pixels, candidate misalignment and stale source/mask identities. Also verify the intended change: an unchanged source trivially preserves protection but does not repair a hand. Keep already-correct hands and legitimate occlusion as negative controls for unnecessary repair.

## Promotion and maintenance

A route earns a task recommendation only when its exact evidence supports it and its user-facing limitations are visible. Keep runtime, visual acceptance and use-purpose review independent. Report accepted/attempted and reused/accepted counts per role, failure-inclusive time and remaining defects, not a global model ranking.

Changing weights, quantization, accelerator, encoder, graph, nodes, runtime, source ordering, transforms, prompt profile, intended use or canonical reference invalidates the relevant evidence projection. Preserve the historical result and explain the changed dimension rather than overwriting it. Requalification should answer that change, not automatically rerun every task.
