# Spoken Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert a `COMPRESSED.md` or `INDEX.md` handoff into one deterministic, locally assembled narration WAV through the existing LAS Voice baseline without duplicate inference.

**Architecture:** A standard-library coordinator compiles bounded Markdown segments, persists an immutable manifest and mutable batch state, creates and reconciles ordinary Voice Production projects through loopback HTTP, verifies their 48 kHz scene WAVs, and concatenates PCM frames with deterministic pauses. A thin PowerShell wrapper provides the one-command Windows path; future voice adapters and Studio UX reuse the coordinator contracts rather than replacing them.

**Tech Stack:** Python 3.12+ standard library, PowerShell, existing LAS loopback HTTP/Production/Voice baseline, GitHub Actions on Ubuntu and Windows.

**Spec:** `docs/spoken-briefs/DESIGN.md`

## Global Constraints

- Keep `COMPRESSED.md`/`INDEX.md` as source of truth; never rewrite the handoff.
- Do not import a model, start Studio, install software or access a non-loopback service.
- Generation starts only from the explicit `run` command.
- Never replace a failed, interrupted, uncertain or unconfirmed Voice request automatically.
- Persist the create marker before POST and the returned project ID before Start.
- Use at most six lines, 1,500 characters and 210 words per child batch; use at most 520 characters per line.
- Accept only project-scoped, SHA-256-bound, 48 kHz mono PCM16 scene WAVs.
- Keep model weights, reference recordings, handoffs and generated audio out of Git.
- Treat `speaker_id` as recipe metadata, not evidence of voice design or cloning.
- Match the repository's Python 3.12 floor and standard-library-first runtime.

---

### Task 1: Compile handoff Markdown into stable segments

**Files:**
- Create: `scripts/spoken_brief.py`, `scripts/spoken_brief_compile.py`, `scripts/spoken_brief_transport.py`, `scripts/spoken_brief_runtime.py`
- Test: `tests/test_spoken_brief_*.py`

**Interfaces:**
- Produces: `resolve_source(pack) -> Path`
- Produces: `compile_markdown(source: str, source_name: str) -> dict`
- Produces: `compile_source(source: Path, speaker_id: str) -> dict`
- Produces: `batch_segments(segments: list[dict]) -> list[list[dict]]`

- [x] **Step 1: Write failing source-selection and Markdown-projection tests**

Cover `COMPRESSED.md` preference, `INDEX.md` fallback, stable segment IDs, heading/list/table retention, link-label retention, and omission counts for front matter, fenced code, raw URLs and comments.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m unittest discover -s tests -p "test_spoken_brief*.py" -v
```

Expected before implementation: import failure for missing `spoken_brief`.

- [x] **Step 3: Implement bounded deterministic compilation**

Use positional IDs `segment-0001`, per-text SHA-256, sentence-first splitting, hard word-aware fallback, and explicit `pause_after_ms`. Refuse empty text, sources over 512 KiB, over 240 segments, over 100,000 narrated characters, invalid UTF-8 and invalid speaker IDs.

- [x] **Step 4: Add batch-limit tests and verify GREEN**

Assert every line is at most 520 characters and every batch obeys the six-line, 1,500-character and 210-word ceilings while retaining exact order.

### Task 2: Persist manifest/state and reject mismatched recovery

**Files:**
- Modify: `scripts/spoken_brief.py`
- Modify: `tests/test_spoken_brief.py`

**Interfaces:**
- Produces: `run_directory(source: Path, manifest_sha256: str) -> Path`
- Produces: `initial_state(manifest: dict) -> dict`
- Produces: `validate_state(state: dict, manifest: dict, batches: list[list[dict]]) -> None`
- Produces: `verify_project(project: dict, identifier: str, batch: list[dict], speaker_id: str) -> None`

- [x] **Step 1: Write a failing test for a retained state with the wrong batch shape**

The command must raise `SpokenBriefError` before contacting Studio when batch count, IDs or line IDs differ from the freshly compiled manifest.

- [x] **Step 2: Run and verify RED**

Expected before validation: the empty retained batch list reaches assembly and raises `StopIteration`.

- [x] **Step 3: Implement exact state and project-plan validation**

Validate schema, manifest hash, ordered batch IDs, ordered line IDs, project-ID syntax and artifact object shape. Before Start or artifact use, require a Voice project whose retained `speaker_id` and exact `[{id,text}]` lines equal the compiled batch.

- [x] **Step 4: Run the focused suite and verify GREEN**

Expected: mismatched state and mismatched project tests pass without mutation requests.

### Task 3: Coordinate child Voice projects without duplicate create

**Files:**
- Modify: `scripts/spoken_brief.py`
- Modify: `tests/test_spoken_brief.py`

**Interfaces:**
- Produces: `StudioClient(base_url, timeout)` with `get_json`, `post_json`, `get_bytes`
- Produces: `run(pack, base_url, speaker_id, poll_seconds, deadline_seconds) -> dict`
- Consumes: existing `/api/identity`, `/api/voice-baseline`, `/api/production/<id>/start`, project GET and file routes

- [x] **Step 1: Write failing fake-loopback tests**

Prove same-origin POST headers, one create per batch, exact speaker/line payload, retained terminal failure, no replacement, and read-only reuse after completion.

- [x] **Step 2: Implement loopback-only HTTP and child reconciliation**

Accept only plain HTTP `localhost`/`127.0.0.1`; verify Studio identity; persist `creating` before Create; distinguish explicit HTTP 4xx rejection from unknown transport/5xx outcomes; persist `project_id` before Start; poll only known IDs; block child terminal states and deadline expiry.

- [x] **Step 3: Write RED tests for malformed create identity and unconfirmed create recovery**

A malformed/lost create result must leave `create-unconfirmed`; a second command must make zero additional create requests.

- [x] **Step 4: Implement the pre-submit marker and verify GREEN**

Persist `creating`, convert every ambiguous create result to `create-unconfirmed`, and require manual reconciliation because no create request-key lookup exists.

### Task 4: Exclude concurrent coordinators

**Files:**
- Modify: `scripts/spoken_brief.py`
- Modify: `tests/test_spoken_brief.py`

**Interfaces:**
- Produces: `acquire_run_claim(run_dir: Path, manifest_sha256: str) -> Path`
- Produces: `release_run_claim(lock: Path) -> None`

- [x] **Step 1: Write a failing test with a pre-existing `.spoken-brief.lock`**

Assert the second invocation blocks before `/api/identity` or any mutation.

- [x] **Step 2: Implement an atomic `O_CREAT | O_EXCL` claim**

Record process ID, manifest hash and claim time. Remove in `finally`; never auto-expire a hard-kill claim.

- [x] **Step 3: Re-run the focused suite**

Expected: concurrent invocation test passes and all earlier recovery tests remain green.

### Task 5: Verify and assemble retained audio

**Files:**
- Modify: `scripts/spoken_brief.py`
- Modify: `tests/test_spoken_brief.py`

**Interfaces:**
- Produces: `artifact_for(project, segment_id, project_id) -> dict`
- Produces: `assemble_wav(entries: list[dict], output: Path) -> dict`

- [x] **Step 1: Write failing WAV and artifact-confinement tests**

Use generated WAV bytes to require exact frame ordering and inserted silence. Reject external/absolute artifact URLs and completed receipts pointing outside their run directory.

- [x] **Step 2: Implement project-scoped download verification**

Require one scene artifact per segment, a relative project file route, full SHA-256, matching downloaded bytes and uncompressed 48 kHz mono PCM16.

- [x] **Step 3: Implement direct PCM assembly and atomic replacement**

Write a temporary WAV, copy input frames without re-encoding, append exact zero frames for each pause, replace the target, and retain input/output hashes and sample counts.

- [x] **Step 4: Verify completed-output idempotence**

A matching receipt/output returns before creating a client. Missing output re-enters child reconciliation for safe reassembly; a changed hash or escaped path blocks.

### Task 6: Add the one-command Windows adapter

**Files:**
- Create: `scripts/speak-handoff.ps1`
- Modify: `tests/test_spoken_brief.py`

**Interfaces:**
- Consumes: `python scripts/spoken_brief.py plan|run ...`
- Produces: PowerShell parameters `Pack`, `BaseUrl`, `SpeakerId`, `PollSeconds`, `DeadlineMinutes`, `PlanOnly`

- [x] **Step 1: Write a wrapper contract test**

Require direct `& $python @arguments`, `-PlanOnly` mapping, invariant-culture numeric serialization and absence of `Invoke-Expression`.

- [x] **Step 2: Implement interpreter resolution and direct argument forwarding**

Resolve `LAS_PYTHON`, repository `.venv`, then `python` on `PATH`. Preserve the child process exit code.

- [x] **Step 3: Parse the wrapper on Windows CI**

Use `System.Management.Automation.Language.Parser.ParseFile` and fail on parser errors.

### Task 7: Document the product boundary and future programme

**Files:**
- Create: `docs/spoken-briefs/README.md`
- Create: `docs/spoken-briefs/DESIGN.md`
- Create: `docs/spoken-briefs/VOICE-PROFILE.md`
- Modify: `.gitignore`
- Create: `.github/workflows/spoken-brief.yml`

**Interfaces:**
- Documents: command, file layout, Markdown policy, recovery table and evidence boundary
- Documents: original soothing profile evaluation and acceptance gate
- Guards: `_spoken/` generated data excluded from Git

- [x] **Step 1: Record alternatives and the selected coordinator architecture**

Explain why raw concat, a new long-form executor and OS narration are insufficient as the primary design, and why child Voice projects plus PCM assembly preserve LAS recovery semantics.

- [x] **Step 2: Write operational documentation with exact commands**

Include `-PlanOnly`, normal run, output records, stale-lock handling, current Kokoro identity limitation and the real-workstation proving boundary.

- [x] **Step 3: Add the Voice profile brief and programme issue map**

Define `ember-brief-v1`, delivery presets, common evaluation lines, resource/quality measurements and the owner acceptance gate. Link #635–#641.

- [x] **Step 4: Add focused cross-platform CI**

Run the test file and CLI help on Python 3.12 for Ubuntu and Windows; parse the PowerShell wrapper on Windows. The repository-wide `check.yml` remains the full integration gate.

### Task 8: Verify before pull request

**Files:** all files above

- [x] **Step 1: Run focused behaviour tests**

```bash
python -m unittest discover -s tests -p "test_spoken_brief*.py" -v
```

Expected: 19 tests, zero failures.

- [x] **Step 2: Compile Python files**

```bash
python -m py_compile scripts/spoken_brief*.py tests/test_spoken_brief_*.py
```

Expected: exit 0.

- [x] **Step 3: Exercise CLI discovery**

```bash
python scripts/spoken_brief.py --help
```

Expected: exit 0 and `plan,run` subcommands shown.

- [ ] **Step 4: Require exact-head GitHub checks before merge**

After the PR branch exists, require the path-specific Ubuntu/Windows lane and repository-wide `Check studio` workflow to complete on that exact commit. Treat any skipped required path or stale earlier result as no evidence.
