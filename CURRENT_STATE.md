# Current state — 11 September 2026

## Changed

Latest addition: five anime finishing presets and visual workflows (25-29), for a total of 29 presets and 29 visual workflows. Installed pinned Impact Pack/Subpack, face/hand detectors and the official Real-ESRGAN anime upscaler. [Detailing guide](docs/ANIME-DETAILING.md). All five graphs passed installed-node schema checks. CPU-only smoke execution loaded the upscaler and both detectors, produced a 128px image from a 32px synthetic input, and produced non-empty face/hand masks on the existing WAI example (15,128 and 3,920 nonzero pixels). No diffusion redraw was submitted. Nine regression tests, the 29-preset validator and pip check passed. After the user queue became empty, the primary backend was restarted and all new nodes loaded. Studio health reports no missing models/nodes, and browser selection enables the combined workflow. The CPU probe was stopped. Independent graph/source review found no CRITICAL/HIGH blocker. Corrected the inherited Animagine provenance note and obsolete overview counts from issue #5.

Latest slice: added three **Anime quality** presets and four editable workflows (21-24): WAI portrait, Animagine portrait, 1.5x refinement and ComfyUI-only masked repair. [Guide](docs/ANIME-QUALITY.md). That slice brought the catalog to 24 presets and 24 visual workflows. New graph schemas, enum/checkpoint names and links passed live-node validation; nine regression tests passed. Browser selection loads the new presets. The agent submitted no generation jobs; user experiments may already appear in the gallery and are not art acceptance.

Completed the serial download queue for FLUX.2 dev 32B Q4, its Mistral Q4 encoder and Xinsir Union SDXL (34.4 GiB total). All three SHA-256 values matched pinned metadata before installation. Portable entries are in models/installed-manifest.json. Runtime inference remains unverified.

Migrated the personal studio into this repository, preserving the original workspace. The local front end provides 29 preset recipes; 29 visual ComfyUI workflows remain available for deeper editing. Model weights and installed tools stay under `C:\AI`. The repository contains scripts, small examples, provenance, guides and selected findings. Local jobs/uploads/logs are ignored.

## Verified

Before this migration, 12 expansion configurations and the original SDXL/FLUX workflows rendered successfully. During migration, four more previously prepared presets rendered: photo-banner 26.595s, stylized-prop 15.126s, gentle-variation 5.942s, WAI-pose 21.649s. These are single server observations, not speed rankings or subjective approvals.

The earlier Lanternkeeper example includes 96 rendered frames, three animated GLBs, a packed atlas and a playable browser sample. Source copies are preserved here. Earlier validations are described in its README; they are not silently reclassified as new migration tests.

The desktop launcher started the studio and a repeat launch reused it. Nine regression tests and the 21-graph catalog validator passed. Independent code review found no remaining CRITICAL/HIGH blocker; root also corrected a stale completion label during browser testing. Actual browser interactions saved/restored a setup, imported a recipe, generated a two-image compass batch with distinct seeds and four output files, and pinned results for comparison. A reference image was uploaded through the file chooser and the gentle-edit job completed. All five returned images loaded in the browser with their expected dimensions; no browser error logs were observed. The full job recipe survives reload. Small selected samples are in `experiments/curated/compass-first-batch/`.

HiDream-O1 FP8 was installed in isolation and its 8.8GB weight SHA verified. Its corrected text-only graph completed an eight-step **2048×2048** render in 32.839s after model loading. The model snapped the requested 512px dimensions to 2048px. The initial loader/sampler attempt took 276.95s and failed on a missing dynamic selector; that graph error was corrected. See [HiDream findings](docs/HIDREAM.md).

## NOT verified

Qwen's 40-step preset remains prepared but not run. HiDream is not yet integrated into the simple studio and has not received higher-step or reference-edit quality comparisons. FLUX.2 dev 32B inference remains a later experiment; its Q4 weight and companion encoder are now installed and checksum-verified. Separate game-engine imports, faithful character in-betweens, character-LoRA training and interactive Krita generation are still outstanding. Full mobile/browser coverage and a fresh-machine installer are not claimed.

## Residual risk

One earlier Qwen-to-SDXL model switch crashed ComfyUI with a Windows access violation; the primary process also exited during the isolated HiDream transition. Root cause is unresolved. The isolated server was stopped and the primary successfully restarted before the browser tests. Heavy model runs can pressure RAM. Source-faithful animation and production-ready transparent pixel assets still require finishing and art review. NoobAI is hobby-only under author terms; WAI mirror provenance does not establish creator authentication or original commercial terms.

## Next work

1. Use the simple studio for a real brief and curate a controlled comparison.
2. Integrate the now-executed isolated HiDream model as an optional preset with safe backend switching, then compare higher steps and a reference edit.
3. Test the slow Qwen quality variant as an explicit long batch, compare with Lightning at the same brief, and assess benefit against time.
4. Add a focused character-consistency and animation study using approved key poses and fixed pivots.
5. Evaluate FLUX.2 dev 32B later with a separate encoder/offload plan and enough free disk/RAM.

[HUMAN_TODO.md](HUMAN_TODO.md) contains optional subjective choices. No complete commercial character pack is claimed.
