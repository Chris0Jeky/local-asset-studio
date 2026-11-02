# Agentic Evidence Lab Implementation Plan

> Agent execution: implement inline, task by task; preserve failing/passing test receipts. Do not start native or remote generation.

**Goal:** preserve research and ship a small evidence-first toolchain that later native adapters can consume.

**Architecture:** reuse `studio_workflow.core` finite JSON and hashing, existing bounded image handling, existing configured-executable convention. Add offline modules and a standalone stdlib-only Blender probe; no server/queue changes.

**Tech stack:** existing Python + Pillow; Blender `bpy` only inside the explicitly invoked probe.

**Spec:** `docs/superpowers/specs/2026-11-02-agentic-evidence-lab.md`.

## Global constraints
Source assets and existing environment installations are immutable. Public code and synthetic evidence only. Native tests remain pending unless executed on the exact machine/runtime. Research is not permission or baseline acceptance.

## Review focus
- Missing or altered images must not become a technical match.
- Same-count topology changes must be detected; object ordering alone must not be a change.
- Path traversal/symlink artifacts must not read unrelated files.
- Completed-report extraction must preserve originals and unresolved citations.
- Plans must use a configured executable and bind exact bytes without launching it.

## Tasks
- [x] 1. `studio_workflow/research_intake.py`; tests `test_research_intake.py`: exclusive, lossless report archive with integrity verification. Observe missing-feature failure, implement, run targeted tests.
- [x] 2. `studio_workflow/dcc_evidence.py`; tests `test_dcc_evidence.py`: strict artifact reader, scene comparison, PNG evidence comparison and content-pinned probe planning. Observe failures then implement.
- [x] 3. `scripts/blender_scene_probe.py`; tests `test_blender_scene_probe.py`: bounded, non-mutating inventory with actual API capability observations and explicit limitations. Native runtime proof remains open.
- [x] 4. `studio_workflow/dcc_lab.py` and `research/agentic-creation/programme.json`: working CLI, validated experiment catalogue and exact commands. Reuse existing owners; no parallel scheduler/MCP.
- [x] 5. Preserve both complete source archives privately; add synthesis/decision register, phased plan, environment and experiment contracts, public/private handoff. Run seeded synthetic comparison and record real outcomes.
- [ ] 6. Run focused tests, full suite attempt, repository validation, diff checks and self-review. Publish isolated review branches without touching unrelated PRs. Report limitations and owner decisions explicitly.

## Rulings
- Existing LAS resource admission and MCP implementation supersede the reports' assumption that these are missing.
- The installed compatibility anchor stays installed; no newer release is silently substituted.
- A persistent worker must first beat the fresh-process path on measured useful workloads with state recovery intact.
- Research suggestions never override the private workspace's prohibition on score-led sculpting.
