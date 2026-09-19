# Narration Profile Contract Implementation Plan

> **For agentic workers:** use `superpowers:executing-plans` or `superpowers:subagent-driven-development`, apply test-driven development, and require exact-head verification before merge.

**Goal:** Give Spoken Briefs stable, inspectable narration-profile and delivery selection plus a deterministic qualification pack, without claiming that CI has generated or accepted a custom voice.

**Architecture:** A bounded checked-in catalogue defines reviewable profile intent. An optional local registry may supersede a profile only through an exact-hash compare-and-swap revision. Spoken Brief manifests and receipts bind the resolved profile, delivery, lexicon, mix, and speaker metadata. Execution is admitted before filesystem or network side effects. A separate zero-generation planner and report validator records candidate measurements, line evidence, long-form listening, and owner decisions. Recordings, model files, local paths, and private qualification evidence remain outside Git.

**Tech stack:** Python 3.12 standard library, JSON, existing Spoken Brief coordinator and Voice baseline, PowerShell, GitHub Actions on Ubuntu and Windows.

**Specification:** `docs/spoken-briefs/VOICE-PROFILE.md`, `research/voice-profiles/README.md`, issue #637, and Voice Lab issue #28.

## Global constraints

- Preserve the existing `/api/voice-baseline` producer and Production worker.
- Keep `speaker_id` classified as recipe metadata, not voice design or cloning.
- Permit experimental profiles in `plan`; refuse them in `run` before `_spoken`, lock, state, or Studio access.
- Bind every run to exact profile, delivery, lexicon, mix, and speaker metadata hashes.
- Require exact prior-hash provenance and a higher revision for local profile replacement.
- Keep references, recordings, reports, model weights, generated audio, and absolute local configuration outside Git.
- Perform no synthesis, model import, device probing, or network access during qualification planning.
- Require the Kokoro control, at least two measured non-control candidates, exact ordered evaluation lines, and a 300–600 second owner-reviewed long-form take for accepted report evidence.
- Match the repository's Python 3.12 floor and standard-library-first runtime.

---

## Task 1: Checked-in catalogue and strict resolver

**Files:**

- `research/voice-profiles/catalog.json`
- `research/voice-profiles/evaluation-set.json`
- `scripts/voice_profile.py`
- `tests/test_voice_profile_contract.py`

- [x] Write catalogue and local-override contracts before implementation.
- [x] Observe RED from the missing resolver on Ubuntu and Windows.
- [x] Validate bounded UTF-8 JSON with exact schemas, stable lowercase IDs, canonical hashes, deep copies, and acceptance-state consistency.
- [x] Check in the runnable `kokoro-af-heart-control-v1` control and non-runnable `ember-brief-v1` experiment.
- [x] Resolve versioned delivery, lexicon, mix, speaker metadata, and canonical binding identity.
- [x] Require a strictly higher revision and exact `supersedes_profile_sha256` before a local record replaces a checked-in profile.
- [x] Reject path-like reference IDs, malformed hashes, unknown fields, duplicate IDs, unsupported statuses, and inconsistent accepted/rejected records.
- [x] Admit only supported, runnable control/accepted bindings; explain experimental, rejected, unbound, and unsupported refusal.
- [x] Preserve canonical identity when the CLI redundantly supplies the profile's default speaker metadata.

## Task 2: Deterministic qualification plan and report validation

**Files:**

- `scripts/voice_profile_qualification.py`
- `tests/test_voice_profile_qualification.py`

- [x] Write deterministic-plan and evidence-report contracts before implementation.
- [x] Observe RED from the missing qualification module on Ubuntu and Windows.
- [x] Build a canonical plan containing profile/evaluation hashes, stable candidate roles, measurement names, exact line IDs, long-form bounds, and `generation_submitted: false`.
- [x] Include Qwen VoiceDesign exploration, Qwen reusable-reference reuse, IndexTTS 2.5 expressive comparison, and the Kokoro control in the programme.
- [x] Validate exact plan identity and immutable evaluation-set revision.
- [x] Require finite non-negative timing, memory, generated-duration, accepted-duration, and correction measurements.
- [x] Require every evaluation line in exact order with audio hash, independent-transcript hash, machine differences, owner ratings, decision, and notes.
- [x] Reject NaN, infinity, booleans as numbers, negative values, duplicate candidates, incomplete hashes, missing control, insufficient measured non-controls, and incomplete line coverage.
- [x] Require one selected measured non-control candidate and a 300–600 second end-to-end owner-reviewed long-form file.
- [x] Return a normalized report/long-form acceptance summary without mutating the source report or registry.

## Task 3: Spoken Brief profile binding and admission

**Files:**

- `scripts/spoken_brief.py`
- `scripts/spoken_brief_compile.py`
- `scripts/spoken_brief_runtime.py`
- `scripts/speak-handoff.ps1`
- `tests/test_spoken_brief_profile.py`

- [x] Write manifest, CLI, PowerShell, receipt, and no-side-effect admission contracts before implementation.
- [x] Bind the default Kokoro control during direct compilation so legacy recovery tooling and runtime commands derive the same manifest identity.
- [x] Make profile, delivery, profile revision, speaker metadata, lexicon, and mix part of the manifest hash.
- [x] Return the exact binding from `plan` and retain it in completed receipts/results.
- [x] Resolve and gate `run` before creating `_spoken`, acquiring a claim, writing state, or constructing `StudioClient`.
- [x] Permit `ember-brief-v1` preview planning while refusing execution as experimental/unbound.
- [x] Extend Python with `--profile-id`, `--delivery-id`, `--profile-registry`, and metadata-only `--speaker-id`.
- [x] Extend PowerShell with `ProfileId`, `DeliveryId`, `ProfileRegistry`, and optional `SpeakerId`, preserving direct argument forwarding.
- [x] Preserve completed-run read-only reuse under the exact same profile binding.
- [x] Run all prior Spoken Brief recovery, source-race, plan-drift, artifact, assembly, and transport contracts without regression.

## Task 4: Documentation, privacy boundary, and CI

**Files:**

- `.github/workflows/spoken-brief.yml`
- `.gitignore`
- `docs/spoken-briefs/VOICE-PROFILE.md`
- `research/voice-profiles/README.md`

- [x] Trigger focused CI for profile scripts, tests, catalogue/evaluation data, Spoken Brief integration, PowerShell, and documentation changes.
- [x] Run profile and Spoken Brief suites plus both CLI help contracts on Python 3.12 for Ubuntu and Windows.
- [x] Parse the PowerShell wrapper on Windows.
- [x] Document checked-in catalogue vs local registry, compare-and-swap replacement, selection commands, qualification planning, report validation, and promotion criteria.
- [x] Document that the current executable adapter remains the pinned Kokoro control and that custom identities still require a genuine producer adapter.
- [x] Ignore local `_voice_profiles/` evidence without ignoring checked-in `research/voice-profiles/` contracts.
- [x] Preserve the evidence boundary: offline contracts prove orchestration and records, not real model compatibility or subjective acceptance.

## Task 5: Exact-head review and publication

- [x] Confirm the pre-documentation implementation head passes focused Ubuntu/Windows contracts and the complete repository suite.
- [ ] Require `Spoken brief contracts` and repository-wide `Check studio` to pass on the final exact PR head.
- [ ] Inspect the final changed-file set for model binaries, audio, references, absolute private paths, generated `_spoken`/`_voice_profiles` data, and unrelated changes.
- [ ] Confirm the PR is mergeable and has no unresolved review threads.
- [ ] Update the PR body with exact-head verification and move it from draft to ready for review.

## Real-workstation proving boundary

After the contract PR lands:

1. create a qualification plan for `ember-brief-v1` under ignored `_voice_profiles/` storage;
2. provision each candidate through isolated, pinned environments under #28;
3. render the shared line set and retain exact configuration/audio/transcript evidence;
4. compare the Kokoro control with at least two non-control candidates, including the independent expressive route where feasible;
5. run the selected candidate through one real 5–10 minute Spoken Brief;
6. listen end to end and record identity, pronunciation, pacing, fatigue, and join findings;
7. validate the local report;
8. create a higher local profile revision that names the exact prior profile hash and a genuine producer adapter;
9. keep references, weights, audio, reports, and permission records out of Git.

A successful invocation, report parse, or CI run does not constitute creative acceptance.
