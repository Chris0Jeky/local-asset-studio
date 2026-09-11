# Prompt Lab: intent before syntax

Research and implementation snapshot: **11 September 2026**, based on main `f6e046b03cf553d4c75e958f128e51804daa6e52`. All files are additive. Default launchers, generation queues, models and presets remain unchanged. Read [research](MODEL-RESEARCH.md), [architecture](ARCHITECTURE.md), [reconstruction](RECONSTRUCTION.md) and [handoff](HANDOFF.md).

## What works now

A pure Python compiler preserves a typed creative brief and projects it into nine explicit model profiles. It returns native field drafts, reference-slot maps, coverage, unresolved requirements and content hashes. Optional local vision/text analysis produces **reviewable proposals**, not silent edits. Locked fields and exact speech/lyrics remain protected. A bounded PNG metadata inspector recovers embedded claims without executing workflows. A graph handoff changes only explicitly registered text inputs, not sampling/model settings. A small UI runs on the existing Studio handler through an opt-in launcher.

The profiles cover SDXL prose, approved Animagine4 tags, positive-only FLUX2, Qwen Edit2511 three-image conditioning, Wan2.2 I2V motion, Qwen3-TTS VoiceDesign, ACE-Step1.5 music, a sound-description route and image-only TRELLIS2. Scope and limitations are in each profile; no generic fallback pretends to support an unknown model.

**Evidence boundary:** compiler, metadata, simulated helper responses, real loopback transport and UI interactions were tested here. No helper model or new image/audio/video inference was run on the user's workstation. A correctly formatted prompt is not a demonstrated quality improvement. Source-page review is not a model installation or benchmark.

## Use from the repository root

```console
python scripts/studio_prompt.py profiles
python scripts/studio_prompt.py compile examples/prompt-studio/portrait.json --profile sdxl-prose-v1 --out experiments/runs/portrait-prompt.json
python scripts/studio_prompt.py inspect-png path/to/example.png --out metadata-claims.json
python -m unittest discover -s tests -p 'test_studio_prompt*.py' -v
```

Output parent folders must exist. Files are exclusive-create: choose a new name rather than overwrite evidence. The compiler and parser use the standard library; Pillow is optional for image analysis preparation.

For the page, wait for active work to finish, then deliberately stop the current Studio process using its normal controls. Run:

```console
python scripts/start_prompt_studio.py --repo-root .
```

Open `http://127.0.0.1:8191/prompt-lab.html`. The launcher refuses an occupied port rather than killing another process. It wraps the actual existing handler and creates the original Studio worker; it is not a second queue or a replacement app. The ordinary desktop launcher is unchanged. Returning to it restores the normal startup path. Page load, compilation, import, helper-proposal acceptance and graph preview never submit generation.

## Optional local helper

First install/review a suitable model and runner separately. Use the **exact name reported by that local runner**, not an assumed model alias. The CLI never pulls models.

```console
python scripts/studio_prompt.py request-helper examples/prompt-studio/portrait.json --model YOUR_INSTALLED_MODEL --out helper-request.json
python scripts/studio_prompt.py run-helper examples/prompt-studio/portrait.json --model YOUR_INSTALLED_MODEL --workspace path/to/job --idle-confirmed --cache --out helper-result.json
python scripts/studio_prompt.py apply examples/prompt-studio/portrait.json helper-result.json --accept facets.lighting --out revised-brief.json
```

Add `--images` when the reference files are present in the workspace. Up to three images are prepared at bounded analysis size, with their hashes verified. Paths are not sent to the model. The bridge uses only `127.0.0.1`, verifies an installed model digest, disables streaming, requests structured JSON and asks for unload after the call. Cloud-labelled/remote models, redirects and automatic retries are rejected.

The workspace lock prevents simultaneous helper calls **only in that workspace**. `--idle-confirmed` is a declaration, not a global GPU lock. A socket timeout cannot certify server-side cancellation. Local transport cannot prove the runner itself has no external integrations. Inspect runner settings and use the shared coordinator before unattended concurrent use.

## Review and handoff

Exported briefs remain model-independent. Imported proposals can be accepted field by field; stale proposals and locked changes are rejected. References carry role, take/ignore instructions and exact hashes. The UI records images but does not upload them to Comfy. Real multi-reference graph binding remains a separate integration with issue21.

The opt-in `/api/prompt/bind` operation verifies actual preset text bindings and raw template bytes, then returns a normal Studio submission payload without submitting it. It currently handles reference-free text-only projections and rejects companion bindings it does not implement. Pure CLI `bind` produces a graph preview; its canonical hash is not the raw-file hash required by Studio's existing submission guard.
