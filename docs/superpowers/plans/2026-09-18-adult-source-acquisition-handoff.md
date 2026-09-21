# Adult Source Acquisition Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert one validated Adult Illustration provider snapshot and one explicit operator selection into a deterministic, inspectable, zero-network acquisition plan for the repository's existing checksum-gated downloader scripts.

**Architecture:** A pure standard-library planning module validates the stored snapshot fields needed for acquisition, selects exactly one checksum-pinned safetensors file, and emits a content-addressed plan whose handoff contains dry-run arguments only. A separate CLI reads bounded local JSON files, performs exclusive-create output, and never imports or invokes either downloader.

**Tech Stack:** Python 3.12 standard library, existing `studio_prompt.adult_illustration_source_intake`, existing `studio_workflow.model_contracts.FOLDERS`, `unittest`, GitHub Actions.

**Spec:** `docs/adult-illustration/SOURCE-INTAKE.md`, `docs/adult-illustration/SOURCE-SNAPSHOTS.md`, issue #433, and the source transport boundary in `docs/adult-illustration/SOURCE-TRANSPORT.md`.

## Global Constraints

- The implementation performs no network access, subprocess launch, model-byte download, installation, execution, generation or training.
- The plan may contain only dry-run arguments for `scripts/fetch-hf.py` or `scripts/civitai-fetch.py`.
- Exactly one provider file is selected per plan.
- The selected file must have a positive byte count, a lowercase 64-hex SHA-256 and a `.safetensors` path.
- Provider access must be public and the source record must be pinned; private, gated, disabled or synthetic records are refused.
- Destination folders come from `studio_workflow.model_contracts.FOLDERS`; destination filenames are plain bounded safetensors basenames.
- A terms-review reference is retained as an unverified human-decision pointer and never grants authority.
- Every emitted record keeps download, installation, execution, generation and training authority false.
- Output files use exclusive creation and local JSON inputs are bounded, regular, non-symlink files.

---

### Task 1: Define planning contracts with failing tests

**Files:**
- Create: `tests/test_adult_illustration_acquisition_plan.py`
- Create: `studio_prompt/adult_illustration_acquisition_plan.py`
- Create: `studio_prompt/_adult_illustration_acquisition_plan_impl.py`

**Interfaces:**
- Consumes: `read_snapshot_json(data: bytes) -> dict[str, Any]` and `studio_workflow.model_contracts.FOLDERS`.
- Produces: `AcquisitionSelection`, `prepare_acquisition_plan(snapshot, selection)`, `validate_acquisition_plan(plan, snapshot=None)`, and `render_acquisition_plan(plan)`.

- [ ] **Step 1: Write failing tests for a Hugging Face plan**

Create a public pinned snapshot fixture with one exact file. Assert that the plan retains repository, immutable commit, source path, byte count, SHA-256, destination and intended use; emits `scripts/fetch-hf.py` dry-run arguments; has a stable `plan_id`; and keeps every authority false.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python -m unittest tests.test_adult_illustration_acquisition_plan -v`

Expected: import failure because the planning module does not exist.

- [ ] **Step 3: Implement the minimal strict planner**

Add a frozen `AcquisitionSelection` dataclass and strict validators for provider identity, pinned/public state, unique file IDs, safetensors path, positive bytes, SHA-256, destination folder/name, intended use and optional review reference. Build deterministic provider-specific dry-run arguments and a SHA-256 `plan_id` over canonical JSON without the ID.

- [ ] **Step 4: Add Civitai coverage**

Use a public metadata snapshot with exact version and provider file IDs. Assert the handoff points to `scripts/civitai-fetch.py`, uses `--version-id`, `--file-id` and `--dry-run`, retains no token and marks transfer credentials as external and unresolved.

- [ ] **Step 5: Run the focused suite and confirm GREEN**

Run: `python -m unittest tests.test_adult_illustration_acquisition_plan -v`

Expected: all planning tests pass.

- [ ] **Step 6: Commit**

Commit message: `feat: add adult source acquisition plans`

### Task 2: Prove refusal and persisted-plan integrity

**Files:**
- Modify: `tests/test_adult_illustration_acquisition_plan.py`
- Modify: `studio_prompt/_adult_illustration_acquisition_plan_impl.py`

**Interfaces:**
- Consumes: Task 1 planner and renderer.
- Produces: structural and content-address validation suitable for persisted plans.

- [ ] **Step 1: Add failing adversarial tests**

Cover private/gated/disabled/synthetic sources, unknown or duplicate file IDs, preselected source rows, missing/invalid hash or size, unsafe source/destination paths, unsupported destination folders, unsupported file suffixes, overlong/free-form fields, and a structurally invalid plan whose attacker recomputed `plan_id`.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m unittest tests.test_adult_illustration_acquisition_plan -v`

Expected: at least the rehashed malformed-plan and one refusal test fail.

- [ ] **Step 3: Implement strict persisted-plan validation**

Validate exact top-level and nested field sets, provider-specific handoff script/argument equality, gate states, authority fields, file/destination identities, bounds, deterministic ordering and the canonical `plan_id`. When a snapshot is supplied, recompute its canonical SHA-256 and require every selected source field to match.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `python -m unittest tests.test_adult_illustration_acquisition_plan -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Commit message: `test: harden adult acquisition plan validation`

### Task 3: Add the local-only CLI

**Files:**
- Create: `scripts/studio_adult_illustration_acquisition_plan.py`
- Create: `tests/test_adult_illustration_acquisition_plan_cli.py`

**Interfaces:**
- Consumes: Task 1 public planner/validator/renderer.
- Produces: `prepare` and `validate` local-only CLI commands.

- [ ] **Step 1: Write failing CLI tests**

Test bounded snapshot/plan reads, `prepare`, `validate`, stdout operation, exclusive-create output, refusal of symlink inputs and occupied or invalid outputs, structured zero-authority errors, and exact byte preservation when a second write is refused.

- [ ] **Step 2: Run CLI tests and confirm RED**

Run: `python -m unittest tests.test_adult_illustration_acquisition_plan_cli -v`

Expected: import failure because the script does not exist.

- [ ] **Step 3: Implement the CLI**

Parse only local paths and scalar selection fields. Read at most 4 MiB per JSON input, reject links/non-files, preflight output before planning, emit canonical formatted JSON, and catch bounded validation/IO failures into machine-readable false-authority errors. Do not import downloader scripts or any network module.

- [ ] **Step 4: Run CLI and planning suites**

Run: `python -m unittest tests.test_adult_illustration_acquisition_plan tests.test_adult_illustration_acquisition_plan_cli -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Commit message: `feat: add local adult acquisition plan CLI`

### Task 4: Document and route verification

**Files:**
- Create: `docs/adult-illustration/ACQUISITION-HANDOFF.md`
- Modify: `docs/adult-illustration/README.md`
- Modify: `docs/adult-illustration/SOURCE-INTAKE.md`
- Modify: `.github/workflows/prompt-studio.yml`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: operator/agent runbook and cross-platform CI coverage.

- [ ] **Step 1: Document the trust boundary**

Describe snapshot versus plan versus transfer versus inventory/qualification; exact supported fields; human terms review; dry-run-only handoff; deterministic identities; blocked source states; and remaining approval gates.

- [ ] **Step 2: Add navigation and CI routing**

Link the handoff from the Adult Illustration index and source-intake guide. Route the new module, CLI, tests and docs through Prompt Studio. Add `python scripts/studio_adult_illustration_acquisition_plan.py --help` only; CI must not run a downloader.

- [ ] **Step 3: Run final verification**

Run:
- `python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v`
- `python scripts/studio_adult_illustration_acquisition_plan.py --help`
- `python scripts/validate-repo.py`

Expected: all focused tests and repository validation pass with no network or download activity.

- [ ] **Step 4: Commit and prepare review evidence**

Commit message: `docs: define adult acquisition handoff`

Update the PR body with RED/GREEN evidence, exact workflow results, dependency order and unresolved human gates.
