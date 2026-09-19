# Narration Profile Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Spoken Briefs a stable, inspectable narration-profile selection contract and a deterministic qualification pack without claiming that CI has accepted a custom voice.

**Architecture:** Add a bounded JSON profile catalogue plus optional local revision registry, validated by a standard-library module. Spoken Brief planning binds a profile and delivery revision into its manifest; execution permits only a supported `voice-baseline` profile whose status is `control` or `accepted`, and refuses experimental or unbound profiles before loopback access. A separate qualification planner and report validator records shared scripts, candidate measurements, long-form evidence, and owner decisions while keeping recordings, weights, local paths, and generated audio outside Git.

**Tech Stack:** Python 3.12 standard library, JSON, existing Spoken Brief coordinator and Voice baseline, PowerShell, GitHub Actions on Ubuntu and Windows.

**Spec:** `docs/spoken-briefs/VOICE-PROFILE.md`, issue #637, and `docs/av-studio/AUDIO-VOICE.md`.

## Global Constraints

- Preserve the current `/api/voice-baseline` producer and Production worker; do not add another inference queue.
- Keep `speaker_id` explicitly classified as recipe metadata, not evidence of identity design or cloning.
- A profile may be previewed while experimental, but execution must fail before any Studio request unless its adapter is supported and its status is `control` or `accepted`.
- An `accepted` original profile must retain owner acceptance, qualification-report hash, long-form manifest/audio hashes, and reference asset/transcript/permission evidence.
- Checked-in records contain no absolute local paths, reference recordings, model weights, generated takes, or copyrighted show samples.
- Local registry replacement uses explicit compare-and-swap provenance: a higher revision must name the exact profile SHA-256 it supersedes.
- Qualification planning performs zero synthesis and zero network access.
- Qualification acceptance requires the same evaluation-set revision, the Kokoro control, at least two measured non-control candidates, and a 5–10 minute reviewed long-form brief.
- Existing `--speaker-id` commands remain valid; an override changes only the bound metadata and manifest identity.
- Match the repository's Python 3.12 floor and standard-library-first runtime.

## Review Focus

- A local registry attempting to replace a profile without the exact prior hash must be rejected rather than silently overriding it.
- NaN, infinity, booleans, negative durations, incomplete hashes, and duplicate candidate/line IDs must never enter qualification evidence.
- An experimental profile must be usable for `plan` but must not create a lock, state file, Studio client, or mutation request during `run`.
- A completed receipt must expose the exact profile/delivery binding that was part of the manifest identity.
- Profile catalogue paths and local registry contents must be bounded and treated strictly as data, never executable configuration.

---

### Task 1: Add the checked-in profile catalogue and strict resolver

**Files:**
- Create: `research/voice-profiles/catalog.json`
- Create: `research/voice-profiles/evaluation-set.json`
- Create: `scripts/voice_profile.py`
- Create: `tests/test_voice_profile_contract.py`

**Interfaces:**
- Produces: `load_catalog(path: Path | None = None) -> dict`
- Produces: `resolve_profile(profile_id: str, delivery_id: str, *, registry_path: Path | None = None, speaker_id: str | None = None) -> dict`
- Produces: `require_executable(binding: dict) -> None`
- Produces: `profile_digest(profile: dict) -> str`

- [ ] **Step 1: Write failing catalogue and override tests**

Cover the default Kokoro control, the unbound `ember-brief-v1` experimental record, stable canonical hashes, delivery selection, bounded UTF-8 JSON, duplicate IDs, unknown fields, path-like evidence, malformed hashes, and local compare-and-swap replacement.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m unittest tests.test_voice_profile_contract -v
```

Expected before implementation: import failure for `voice_profile`.

- [ ] **Step 3: Implement strict catalogue validation and resolution**

Use exact schemas, lowercase stable IDs, finite numeric validation, canonical JSON hashing, a 256 KiB input ceiling, and deep copies. Reject duplicate local IDs unless the replacement revision is higher and `supersedes_profile_sha256` matches the currently resolved record.

- [ ] **Step 4: Implement execution admission**

`require_executable()` accepts only adapter `voice-baseline`, `runnable: true`, and status `control` or `accepted`. It must explicitly state why experimental, rejected, unbound, or unsupported profiles cannot run.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: all profile-contract tests pass on Python 3.12.

### Task 2: Add deterministic qualification plans and evidence validation

**Files:**
- Create: `scripts/voice_profile_qualification.py`
- Create: `tests/test_voice_profile_qualification.py`

**Interfaces:**
- Consumes: `resolve_profile()` and `research/voice-profiles/evaluation-set.json`
- Produces: `build_plan(profile_id: str, *, registry_path: Path | None = None) -> dict`
- Produces: `validate_report(plan: dict, report: dict) -> dict`
- Produces CLI: `plan` and `validate`

- [ ] **Step 1: Write failing plan and report tests**

Require deterministic plan identity, zero-generation metadata, the shared evaluation lines, Qwen VoiceDesign/reuse, one independent expressive candidate, and the Kokoro control. Test exact match, duplicate candidates, missing control, only one measured non-control, invalid finite metrics, incomplete line coverage, missing hashes, long-form duration outside 300–600 seconds, owner rejection, and accepted evidence.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m unittest tests.test_voice_profile_qualification -v
```

Expected before implementation: import failure for `voice_profile_qualification`.

- [ ] **Step 3: Implement deterministic plan construction**

The plan records the profile/catalogue/evaluation hashes, stable candidate IDs, required measurement names, line IDs, long-form requirements, and `generation_submitted: false`. It does not start Studio, import a model, or inspect local devices.

- [ ] **Step 4: Implement strict report validation**

Validate exact plan identity, complete SHA-256 values, finite non-negative timings/memory/seconds, every evaluation line per measured candidate, separate machine and owner findings, at least two measured non-control candidates plus the control, and a 5–10 minute owner-reviewed long-form record. Return a normalized acceptance summary; never mutate the source report.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: all qualification tests pass.

### Task 3: Bind profiles into Spoken Brief manifests, execution, receipts, and CLI

**Files:**
- Modify: `scripts/spoken_brief.py`
- Modify: `scripts/spoken_brief_compile.py`
- Modify: `scripts/spoken_brief_runtime.py`
- Modify: `scripts/speak-handoff.ps1`
- Create: `tests/test_spoken_brief_profile.py`

**Interfaces:**
- Consumes: `resolve_profile()` and `require_executable()`
- Extends: `compile_source(..., voice_profile: dict | None = None) -> dict`
- Extends: `plan(..., profile_id, delivery_id, profile_registry, speaker_id) -> dict`
- Extends: `run(..., profile_id, delivery_id, profile_registry, speaker_id, ...) -> dict`

- [ ] **Step 1: Write failing manifest, CLI, and no-network admission tests**

Prove the default plan binds the Kokoro control, delivery/profile changes alter manifest identity, `--profile-id` and `--delivery-id` parse, PowerShell forwards direct arguments, speaker overrides are labelled metadata-only, experimental plans succeed, experimental runs fail before `StudioClient` construction and before `_spoken` state is created, and completed receipts retain the exact binding.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m unittest tests.test_spoken_brief_profile -v
```

Expected before implementation: missing profile arguments and binding fields.

- [ ] **Step 3: Add profile binding to compilation and planning**

Include a canonical `voice_profile` binding in the manifest only when supplied, preserving direct legacy `compile_source(source, speaker_id=...)` callers. Return profile ID, revision, status, delivery, hashes, adapter, runnable state, and metadata speaker ID from `plan`.

- [ ] **Step 4: Gate execution before local or network side effects**

Resolve and validate the profile before creating `_spoken`, acquiring a lock, constructing `StudioClient`, or writing state. Use the resolved speaker metadata in child payloads. Include the exact binding in receipts and command results.

- [ ] **Step 5: Extend Python and PowerShell CLIs**

Add `--profile-id`, `--delivery-id`, and `--profile-registry`; keep `--speaker-id` as an optional metadata override. The PowerShell wrapper adds `ProfileId`, `DeliveryId`, and `ProfileRegistry` and still forwards an argument array without evaluation.

- [ ] **Step 6: Run all focused contracts and verify GREEN**

Run:

```bash
python -m unittest discover -s tests -p "test_voice_profile*.py" -v
python -m unittest discover -s tests -p "test_spoken_brief*.py" -v
python scripts/spoken_brief.py --help
python scripts/voice_profile_qualification.py --help
```

Expected: zero failures.

### Task 4: Document the boundary and add cross-platform CI coverage

**Files:**
- Modify: `.github/workflows/spoken-brief.yml`
- Modify: `docs/spoken-briefs/VOICE-PROFILE.md`
- Modify: `docs/spoken-briefs/README.md`
- Modify: `.gitignore`

**Interfaces:**
- Documents: catalogue/local-registry split, commands, acceptance gate, current runnable control, and workstation proving steps
- Guards: local `_voice_profiles/` evidence excluded from Git

- [ ] **Step 1: Extend workflow paths and commands**

Trigger on `scripts/voice_profile*.py`, `tests/test_voice_profile*.py`, and `research/voice-profiles/**`; run both focused suites and both CLI help commands on Ubuntu and Windows.

- [ ] **Step 2: Document exact commands and evidence boundaries**

Explain profile/delivery selection, local registry CAS replacement, qualification-plan generation, report validation, why `ember-brief-v1` remains experimental, and why successful execution is not subjective acceptance.

- [ ] **Step 3: Ignore local qualification evidence**

Ignore `_voice_profiles/` directories without ignoring the checked-in `research/voice-profiles/` catalogue and evaluation set.

- [ ] **Step 4: Run final exact-head verification**

Require the path-specific Ubuntu/Windows workflow and repository-wide `Check studio` workflow on the exact final commit. Confirm no review threads, generated audio, local profile evidence, absolute paths, or model assets enter the PR.
