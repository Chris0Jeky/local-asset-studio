# Controlled Adult Illustration Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the non-executing contracts, validation and agent handoff required to implement #403 without duplicating existing Studio infrastructure.

**Architecture:** Static research manifests define intent/control vocabulary, route hypotheses, packs and benchmark cases. A stdlib validator proves structural invariants. Later runtime work projects these records through existing Prompt, Setup, Workflow and Production services.

**Tech Stack:** Python 3.12+ standard library, JSON, Markdown, unittest.

**Spec:** `docs/superpowers/specs/2026-09-15-controlled-adult-illustration-design.md`

## Global Constraints

- Public fixtures are synthetic, adult-only and non-explicit.
- Every research manifest declares `executable: false` and `authority: none`.
- No network, model, ComfyUI, Workspace or generation access in foundation tests.
- Reuse existing typed services; do not create persistence or execution.
- Test behaviour before implementation.
- Preserve `HUMAN_TODO.md`.

---

### Task 1: Publish programme and research contracts

**Files:**
- Create: `docs/adult-illustration/*.md`
- Create: `research/adult-illustration/*.json`

**Interfaces:**
- Produces: static `studio.adult-illustration-*/v0` documents consumed by Task 2.
- Consumes: live issues #403–#413 and existing architecture docs.

- [ ] Verify every JSON file parses with `python -m json.tool`.
- [ ] Check unique control, route, case and pack IDs.
- [ ] Check all documents state non-executing authority.
- [ ] Commit with issue references only; the programme remains open.

### Task 2: Add the failing validator tests

**Files:**
- Create: `tests/test_adult_illustration.py`

**Interfaces:**
- Produces: expected `validate_paths(root: Path) -> list[str]`.
- Consumes: Task 1 manifests.

- [ ] Write tests for the valid checked-in manifests.
- [ ] Write temporary-fixture tests for missing adult assertion, executable authority, duplicate IDs, unknown control, invalid evidence state, unbounded adapter range and non-zero authorized campaign allowance.
- [ ] Run `python -m unittest discover -s tests -p "test_adult_illustration.py" -v`.
- [ ] Confirm failure is caused by missing `scripts/validate_adult_illustration.py`.

### Task 3: Implement the minimal offline validator

**Files:**
- Create: `scripts/validate_adult_illustration.py`

**Interfaces:**
- Produces: `validate_paths(root: Path) -> list[str]` and a CLI returning 0/1.
- Consumes: JSON files from Task 1.

- [ ] Load bounded UTF-8 JSON without network or imports from app/runtime modules.
- [ ] Validate schema, kind, `executable`, `authority`, research date and baseline.
- [ ] Validate unique IDs and cross-references among controls, cases and packs.
- [ ] Validate route evidence order and source URL shape.
- [ ] Validate every benchmark subject is adult-declared and authorized attempt cap is zero in Git.
- [ ] Validate adapter template is unpromoted with bounded ordered weights.
- [ ] Run the focused tests and confirm all pass.
- [ ] Run `python scripts/validate_adult_illustration.py`.

### Task 4: Add the external agent skill

**Files:**
- Create: `agent-skills/adult-illustration/SKILL.md`

**Interfaces:**
- Produces: deterministic issue routing and stop conditions for development agents.
- Consumes: docs and validator from Tasks 1–3.

- [ ] Document inspect/validate/plan commands.
- [ ] Prohibit install, runtime mutation, generation and self-promotion.
- [ ] Route each subsystem to #404–#413 and existing owners.
- [ ] Add a dry-run handoff example with zero generation.

### Task 5: Verify and publish

**Files:**
- No new files.

**Interfaces:**
- Consumes: complete foundation branch.

- [ ] Run `python -m unittest discover -s tests -p "test_adult_illustration.py" -v`.
- [ ] Run `python scripts/validate_adult_illustration.py`.
- [ ] Run `python scripts/validate-repo.py` in a full checkout.
- [ ] Let hosted CI run the full suite.
- [ ] Inspect the PR patch and confirm no weights, private media, runtime files or execution authority.
- [ ] Open ready-for-review PRs with `Refs #403` through relevant child issues; do not close runtime/evidence issues.
