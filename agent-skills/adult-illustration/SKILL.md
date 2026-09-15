---
name: adult-illustration
description: Plan and implement the adult-only controlled anime illustration programme through static manifests, existing Studio services, finite qualification and explicit authority boundaries.
---
# Controlled adult illustration agent contract

Use this skill when working on #403–#413: model-independent adult illustration intent, exact route qualification, LoRA/control evidence, geometry, role-separated references, benchmarks, genre packs, training plans, finishing or shared agent commands.

Do **not** use it to bypass Prompt Lab, Workflow Studio, Production, Model Library, character consistency, Repair Studio, Krita or Blender. It does not authorize model downloads, package/runtime changes, neural execution, training, paid services, private-media publication, creative acceptance, rights clearance or promotion.

## Read first

1. `CLAUDE.md`, `AGENTS.md`, `CURRENT_STATE.md` and `HUMAN_TODO.md`.
2. `docs/adult-illustration/README.md`, `ARCHITECTURE.md`, `CONTROL-ONTOLOGY.md`, `EVALUATION.md` and `AGENT-CONTRACT.md`.
3. `research/adult-illustration/programme.json` and the manifest relevant to the issue.
4. Live #403 and the child issue being implemented.
5. Existing owner docs:
   - `docs/prompt-studio/`
   - `docs/workflow-studio/`
   - `docs/character-consistency/`
   - `docs/repair-studio/`
6. Exact current PRs, installed capability evidence and route files. Never infer installation from a research candidate or filename.

Run the offline gate before changing a manifest:

```console
python scripts/validate_adult_illustration.py
python -m unittest discover -s tests -p "test_adult_illustration.py" -v
```

## Use when / Do NOT use when

Use for:

- extending the model-independent control vocabulary through existing intent/setup records;
- adding exact route, adapter or pack evidence;
- planning finite comparisons with zero initial allowance;
- implementing inspect/compile/diff/prepare commands over existing shared services;
- adding synthetic adult-only/non-explicit fixtures and offline validation;
- routing work to the correct existing subsystem.

Do not use for:

- a new queue, model registry, project store, review database, executor or canvas;
- direct `/prompt` calls or a browser-clicking agent;
- automatic Civitai/Hugging Face/custom-node installation;
- visual inference of age, consent, identity, rights or artistic acceptance;
- converting an unsupported geometry/reference/mask control into prompt prose;
- resubmitting after response loss under a new identity;
- hiding real candidate count inside a batch or extending an allowance.

## Guardrails

- Every public fixture is synthetic, unambiguously adult and non-explicit.
- Research manifests declare `executable: false`, `authority: none` and zero authorized candidate cap.
- Adult status comes from reviewed owner/canon metadata, never pixels or a negative prompt.
- Multi-adult intimate tests require an explicit consent-context declaration.
- Semantics, geometry, appearance, pixel authority and evidence remain separate.
- A reference declares roles plus `take`/`ignore`; excess or ambiguous sources refuse.
- Geometry artifacts never grant pixel-write authority.
- Exact model/configuration evidence never generalizes to a family, quantisation or operating system.
- Successful execution, visual review, owner acceptance, rights review and promotion remain distinct.
- Unknown remains unknown. Changed source/model/graph/reference bytes make prior plans stale.
- Preserve expected revisions and request/ticket/job/prompt identities. Observe uncertain outcomes; do not replay blindly.
- Keep `HUMAN_TODO.md` decisions open.

## Workflow

1. Reconcile `main`, open PRs, issue ownership and current route evidence.
2. Choose one child issue and state the exact evidence gate.
3. Inspect existing typed services before creating a file or type.
4. For behaviour changes, write a failing test and confirm the expected failure.
5. Implement the smallest independently reviewable slice.
6. Run the focused test, this programme validator and repository-required checks.
7. Produce an exact diff/plan showing:
   - intent/control changes;
   - source/reference and geometry identities;
   - exact route/adapter evidence;
   - unsupported and unknown facts;
   - resource/candidate implications;
   - approval boundary.
8. Retain failure and stop on overlap, stale identity, unsupported capability, uncertain dispatch or exhausted cap.
9. Open a ready-for-review `codex/<topic>` PR. Use `Refs #N` unless the complete live issue acceptance is proven.

## Issue routing

| Work | Primary issue and existing owner |
| --- | --- |
| Intent/content/control ontology | #404 with #38/#120 |
| Exact generation/edit route | #405 with #9/#144/#302 |
| LoRA/slider qualification | #406 with #14/#144 |
| Pose/silhouette/depth/regions | #407 with #248/#120 |
| Multi-reference/multi-adult | #408 with #21/#232/#249 |
| Corpus and acceptance evidence | #409 with #10/#37/#72/#313 |
| Guided genre packs | #410 with #118/#120 |
| LoRA training | #411 with #9/#14/#65 |
| Repair/upscale/finishing | #412 with #243/#256/#257 |
| CLI/SDK/MCP projections | #413 with #123 |
| Dispatch/recovery | #10/#22/#122 |
| Resource admission/telemetry | #178/#302 |

## Dry handoff

A valid dry handoff may:

1. validate the static manifests;
2. inspect current capabilities and exact route evidence;
3. load or propose a revisioned intent diff;
4. bind reviewed source/geometry identities in a non-executing setup proposal;
5. compile and inspect a finite comparison plan with cap zero;
6. report missing prerequisites and the exact approval boundary.

It must finish with **zero neural jobs, zero downloads and zero runtime mutation**. A separately authorized execution later uses the existing Production/Workflow ticket path and retained identity; this skill supplies no alternate dispatch mechanism.

## Stop conditions

Stop and preserve evidence when the work overlaps an active PR; source/version/hash/graph identity is unknown; adult/content declarations are missing; adapter compatibility is guessed; route/resource support is unmeasured; source or expected revision changed; dispatch outcome is uncertain; the same failure persists without a changed hypothesis; or the requested action needs authority not present in the current issue.
