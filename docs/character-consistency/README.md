# Character consistency: one complete production path

This programme turns an accepted design into repeatable character panels, then an editable and playable character pack. It extends #22, #14 and #21. It does not introduce another Studio, queue, model manager or painting application.

Start with [research and findings](RESEARCH.md), [goals and waypoints](ROADMAP.md), [architecture](ARCHITECTURE.md) and the [local-agent runbook](RUNBOOK.md). Work is tracked in #64 (the first live pilot), #65 (shared execution) and #66 (calibrated review/repair). The existing #23/#24 own native layered sources and engine playback.

## What this slice supplies

The companion implementation provides three offline Python commands:

- `scripts/character_archive.py`: verify and restore all 71 members of the original research delivery into a new local evidence directory. It performs no network access and never executes archived code.
- `scripts/character_study.py`: versioned identity/costume/representation/style canon; deterministic bounded study plans; source/approval preflight; existing game-asset brief projection; native-preset handoff preview; honest attempt/review accounting.
- `scripts/character_media.py`: measured PNG intake, pixel-exact rectangular extraction, deterministic review-card assembly and exact decoded-RGBA preservation outside an explicit repair mask.

These commands are offline building blocks. A successful plan, handoff or receipt does not submit a Comfy job, authenticate a reviewer, approve artwork or establish model rights. `handoff` deliberately contains `submission_payload: null`; #65 supplies the trusted runtime connection.

## First objective

Twelve image-producing attempts: the existing `qwen-1ref` and `flux-edit` routes, three tasks, two seeds. Establish whether either installed configuration can preserve a reviewed character well enough to justify a larger production study. This is not a statistically powered leaderboard or a proven local equivalent of Images 2.5.

The committed supplied-character canon is **draft**. Source images are evidence of the desired look, not blanket approval of hidden costume construction. Human approval, source rights and successful execution remain separate. An original character is required for the later generalization/commercial milestone.

## Original delivery and Git policy

The earlier delivery is `character-consistency-kit.zip`, 25,825,577 bytes, SHA-256 `528489fd0c37e2ae2e6a76666dd17c5d942af1a66fa1ba5fa6d096c2fcc0ace8`. It contains the full historical report and bibliography, self-contained interactive guide, original sheets, 33 review crops, two assembled cards, prompts, schema/brief examples, pilot CSV/JSON, tools and historical test evidence.

The repository rejects ZIP archives and operational evidence in Git. The new PR therefore stores the implementation, integrated research, strategy, source index and exact per-member archive lock as reviewable text. It does **not** commit the large original PNGs or base64-embedded guide. The importer restores all original files byte-for-byte outside Git from the user's existing download; it cannot download a ChatGPT sandbox URL. Keep that original download with your local project backups.

The archived material is a historical snapshot from `0ffec70b109396aaacb590f21367fc9cfa86a611`, including its then-correct statement that no GitHub write had occurred. This implementation was inspected against `2df49541b2caee100e9d5b23f27f5548b9ed5bda`. Archived code is preserved for provenance, not installed or used as the new production entry point.

## Evidence boundary

Current-session CPU proofs and tests are recorded in `research/character-consistency/OFFLINE-EVIDENCE.json`. Neural inference, workstation installation, reference upload, live queue integration, actual art acceptance and engine playback are not claimed by this slice. The original guide's visual examples derive from the user's supplied images, not new local model generations.

`HUMAN_TODO.md` remains authoritative and unchanged: optional pixel look, product brief, curation and Anima q-3 creative choices remain open. No permission, model installation or creative acceptance is inferred by importing the bundle.

## Controlled-edit extension

For anatomy corrections, costume variants and multi-character scenarios, start with [controlled editing](EDITING.md), the [working patch runbook](EDIT-RUNBOOK.md), [model/tool policy evidence](TOOL-POLICIES.md) and the [edit-yield benchmark](EDIT-BENCHMARK.md). The new `character_edit.py`, `character_edit_pixels.py` and `character_edit_demo.py` commands provide actor-bound plans and a source-preserving file-based bridge a local agent can use. The supplied `agent-skills/character-editing/SKILL.md` documents the operating contract.

The deterministic synthetic proof is executable now; native Krita/Studio/agent integration is #71 and actual neural edit-yield measurement is #72, extending #23/#65/#66. The extension adds no content classifier or hidden cloud fallback and does not certify unknown model behaviour as unrestricted.
