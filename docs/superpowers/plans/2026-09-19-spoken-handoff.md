# Spoken Handoff implementation plan

> **For agentic workers:** use `superpowers:executing-plans` or `superpowers:subagent-driven-development`, apply test-driven development, and require exact-head verification before merge.

**Goal:** Convert a `COMPRESSED.md` or `INDEX.md` handoff into one deterministic local narration WAV through the existing LAS Voice baseline without duplicate inference.

**Architecture:** A Python standard-library coordinator compiles bounded Markdown segments, persists an immutable schema-v2 manifest and durable mutable state, creates and reconciles ordinary Voice Production children through loopback HTTP, verifies Studio, producer, child-plan, artifact, and source provenance, and concatenates PCM frames with deterministic pauses. A thin PowerShell wrapper provides the one-command Windows route.

**Tech stack:** Python 3.12+, PowerShell, existing LAS loopback HTTP, Production, and Voice baseline, GitHub Actions on Ubuntu and Windows.

**Specification:** `docs/spoken-briefs/DESIGN.md`

## Global constraints

- Keep `COMPRESSED.md` or `INDEX.md` as source of truth and never rewrite it.
- Do not import a model, start Studio, install software, or access a non-loopback service.
- Start generation only from the explicit `run` command.
- Never replace a failed, interrupted, uncertain, or unconfirmed Voice request automatically.
- Persist and flush create intent before POST, and persist the returned project ID before Start.
- Use at most six lines, 1,500 characters, and 210 words per child batch, with at most 520 characters per line.
- Accept only exact-project, SHA-256-bound, 48 kHz mono PCM16 scene WAVs.
- Bind one run to exact source bytes, Studio workspace identity, child-plan hashes, and one producer fingerprint.
- Keep model weights, references, handoffs, and generated audio out of Git.
- Treat `speaker_id` as recipe metadata, not evidence of voice design or cloning.
- Match the repository's Python 3.12 floor and standard-library-first runtime.

---

## Task 1: Compile Markdown into stable bounded segments

**Files:**

- `scripts/spoken_brief.py`
- `scripts/spoken_brief_compile.py`
- `tests/test_spoken_brief_compile.py`

- [x] Resolve `COMPRESSED.md` before `INDEX.md`, while accepting a direct Markdown file.
- [x] Read at most 512 KiB and reject invalid UTF-8, NUL characters, empty projections, over 240 segments, and over 100,000 narrated characters.
- [x] Keep headings, prose, lists, table cells, and link labels while counting omitted front matter, fenced code, comments, and raw URLs.
- [x] Produce positional stable IDs, text SHA-256 values, block kinds, and explicit pauses.
- [x] Split on sentence boundaries first and use a word-aware hard fallback.
- [x] Preserve order while enforcing Voice batch limits.

## Task 2: Persist schema-v2 manifest and recovery state

**Files:**

- `scripts/spoken_brief_compile.py`
- `scripts/spoken_brief_transport.py`
- `tests/test_spoken_brief_recovery.py`
- `tests/test_spoken_brief_hardening.py`

- [x] Bind the manifest to canonical path, exact byte count and hash, compiler settings, speaker metadata, omissions, and segments.
- [x] Derive a unique `_spoken/<stem>-<manifest>/` run directory.
- [x] Validate exact ordered batch IDs and line IDs before any network use.
- [x] Retain full Studio endpoint and workspace identity.
- [x] Retain every child project ID and exact child plan SHA-256.
- [x] Retain one stable producer fingerprint across all children.
- [x] Reject malformed project IDs, hashes, artifact maps, aggregate statuses, and unsupported schemas.

## Task 3: Coordinate Voice children without duplicate creation

**Files:**

- `scripts/spoken_brief_runtime.py`
- `scripts/spoken_brief_transport.py`
- `tests/test_spoken_brief_runtime.py`
- `tests/test_spoken_brief_recovery.py`

- [x] Accept only canonical HTTP loopback endpoints and verify `/api/identity`.
- [x] Persist `creating` before `POST /api/voice-baseline`.
- [x] Distinguish explicit HTTP 4xx rejection from uncertain transport, HTTP 5xx, malformed identity, and lost-response outcomes.
- [x] Persist the returned project ID before Start.
- [x] Observe only known project IDs and block terminal failures or deadline expiry.
- [x] Reuse completed or active children rather than creating replacements.
- [x] Treat a missing create identity as `create-unconfirmed` and block later submissions.
- [x] Treat Start uncertainty as an unknown outcome on the known child, never as permission to create another child.

## Task 4: Verify signed plans and producer consistency

**Files:**

- `scripts/spoken_brief_transport.py`
- `scripts/spoken_brief_runtime.py`
- `tests/spoken_brief_fixture.py`
- `tests/test_spoken_brief_hardening.py`

- [x] Recompute the LAS canonical SHA-256 for each retained Voice plan.
- [x] Require exact `speaker_id` and ordered `[{id,text}]` lines before Start or artifact use.
- [x] Pin the first observed child plan hash and reject later drift.
- [x] Derive a producer fingerprint after excluding batch-specific name, lines, and creation time.
- [x] Block a producer change before starting a later child.
- [x] Model signed Voice plans and full Studio identities in the fake-loopback fixture.

## Task 5: Revalidate source and Studio identity at mutation boundaries

**Files:**

- `scripts/spoken_brief_compile.py`
- `scripts/spoken_brief_runtime.py`
- `tests/test_spoken_brief_hardening.py`
- `tests/test_spoken_brief_finalization.py`

- [x] Re-read and rehash the bounded source before create, Start, observation, artifact download, and final assembly.
- [x] Re-fetch and compare the complete Studio identity before the same boundaries.
- [x] Block a changed source, endpoint, workspace, identity version, child plan, or producer.
- [x] Recheck source bytes after local assembly.
- [x] Delete an unreceipted master and record `source-changed` if the source changes during assembly.

## Task 6: Exclude concurrent coordinators and persist intent durably

**Files:**

- `scripts/spoken_brief_transport.py`
- `tests/test_spoken_brief_recovery.py`
- `tests/test_spoken_brief_hardening.py`

- [x] Acquire `.spoken-brief.lock` with atomic `O_CREAT | O_EXCL` before network use.
- [x] Record process ID, manifest hash, and claim time.
- [x] Flush and `fsync` lock and JSON state intent before mutation.
- [x] Write JSON through unique temporary files followed by atomic replacement.
- [x] Never auto-expire a hard-kill claim.
- [x] Verify the persistence path on Linux and Windows.

## Task 7: Verify artifacts and assemble one archival WAV

**Files:**

- `scripts/spoken_brief_transport.py`
- `scripts/spoken_brief_runtime.py`
- `tests/test_spoken_brief_runtime.py`
- `tests/test_spoken_brief_recovery.py`
- `tests/test_spoken_brief_finalization.py`

- [x] Require one exact `voice/<segment-id>-scene.wav` artifact per segment.
- [x] Require an exact relative route under the retained project ID.
- [x] Verify complete SHA-256 evidence and downloaded bytes.
- [x] Require uncompressed 48 kHz mono PCM16 input.
- [x] Copy PCM frames directly and insert exact zero-valued pause frames.
- [x] Flush and `fsync` the temporary master, then atomically replace the target.
- [x] Stream input, output, and completed-reuse hashes rather than loading a long master fully into memory.
- [x] Publish a receipt containing source, Studio, producer, child plan, segment, input, and output evidence.
- [x] Return a matching completed run before constructing a Studio client.

## Task 8: Add the one-command Windows adapter

**Files:**

- `scripts/speak-handoff.ps1`
- `.github/workflows/spoken-brief.yml`
- `tests/test_spoken_brief_runtime.py`

- [x] Expose `Pack`, `BaseUrl`, `SpeakerId`, `PollSeconds`, `DeadlineMinutes`, and `PlanOnly`.
- [x] Resolve `LAS_PYTHON`, repository `.venv`, then `python` on `PATH`.
- [x] Forward direct argument arrays without `Invoke-Expression`.
- [x] Serialize numeric values with invariant culture and preserve the child exit code.
- [x] Parse the wrapper on Windows CI.

## Task 9: Document the product boundary and follow-on programme

**Files:**

- `docs/spoken-briefs/README.md`
- `docs/spoken-briefs/DESIGN.md`
- `docs/spoken-briefs/VOICE-PROFILE.md`
- `.gitignore`

- [x] Document the command, output layout, Markdown projection, evidence model, recovery table, and trust boundary.
- [x] Explain why raw concat, a second worker, one unbounded request, and OS narration are not the primary design.
- [x] Define the original `ember-brief-v1` profile qualification programme without claiming a character clone.
- [x] Keep generated `_spoken/` data out of Git.
- [x] Link #635 through #641 and preserve WAV-only scope for #636.

## Task 10: Verification and review

- [x] Observe RED for the added provenance, source-race, transport-shape, durability, and final-publication contracts before implementation.
- [x] Run `python -m unittest discover -s tests -p "test_spoken_brief*.py" -v` with 40 passing contracts on Ubuntu and Windows.
- [x] Run `python scripts/spoken_brief.py --help` on both operating-system families.
- [x] Parse `scripts/speak-handoff.ps1` on Windows.
- [x] Exercise one-batch, multi-batch, failed-child, uncertain-create, completed-reuse, source-drift, workspace-drift, plan-drift, and producer-drift paths through the fake loopback Studio.
- [ ] Require both `Spoken brief contracts` and repository-wide `Check studio` to pass on the final exact PR head after all documentation and review changes.
- [ ] Confirm no unresolved review threads, no accidental generated audio or private handoff content, and a mergeable PR before publication.

## Real-workstation proving boundary

CI uses synthetic PCM fixtures and does not contain the pinned model bundle. After merge, the configured workstation proving step is:

1. run `-PlanOnly` against one short real handoff;
2. inspect the spoken projection and omissions;
3. explicitly run generation;
4. verify the assembled WAV and retained receipt;
5. listen for pronunciation, pacing, fatigue, and identity defects;
6. record creative or transcript defects against #637 or #641.

A successful process exit proves integration, not subjective voice acceptance.
