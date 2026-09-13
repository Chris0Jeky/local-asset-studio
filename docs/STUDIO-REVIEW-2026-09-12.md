# Studio review — 12 September 2026

This reconciles the two session handoffs against local Git, GitHub and the running applications. The initial snapshot was `main == origin/main == 064d6026f54b77f19fb701cee5409d2a316c993f`, with a clean primary checkout and no open PRs. Claude's earlier `0769d02` handoff preceded the merge of Codex's #115; they describe successive states. This is a dated historical snapshot; use the [13 September GitHub reconciliation](reconciliation/2026-09-13-github.md) for the current PR and issue state.

## What was accomplished

| Area | Delivered behavior | Relevant PRs | Evidence boundary |
| --- | --- | --- | --- |
| Runtime planning | Measured VRAM/host-memory constraints; primary reserve changed to 0.6; documented heavy-job threshold raised to 32 GiB commit headroom | #99, #107 | The threshold was an operator rule, not enforced by the application at this snapshot. Native crashes were not fixed. |
| Image correction | Fooocus SDXL masked inpaint preset, corrected sampler latent and explicit inpaint-file requirements | #100 | Static and offline behavior tested. No recorded generation through the new preset. |
| Lineage | Per-input parent attribution survives reference replacement and saved setups/drafts | #101, #112 | Synthetic browser proof. Remaining availability-error case is #117. |
| Reference geometry | Qwen reference sizes and Picture-N semantics reflect the installed encoder | #103 | Geometry/receipt proof. Exact character consistency is not established. |
| Recovery records | Stop tracking preserves evidence; Gallery Resume observes known prompts; Production continuation requires explicit authorization | #105 | #105 had a late duplicate-dispatch defect; #114 fixes it. |
| Submission safety | Queued retained observations never become a fresh generation; malformed acceptance replies remain uncertain | #114, #115 | Offline causal tests and CI. They do not recover lost ComfyUI history. |
| Model inventory | 107 installed files with supported suffixes pinned by exact hash, size and path; unsupported installers refused | #109 | Hashes establish byte identity, not creator authentication or use rights. |
| Creative evidence | Two SDXL identity/pose outputs retained, with failed-probe recipes and accurate execution stages | #111 | A with the familiar-character tag was closer than B without it. This pair is confounded; it cannot establish that the tag alone caused the difference. |
| Test/docs corrections | Hermetic engine test and corrected claims, including FLUX dimension requirements and detail-pass settings | #90, #102 | Executable checks and corrected documentation. |

All thirteen PRs above were confirmed merged, with successful final-head check rollups. Several GitHub review threads still display unresolved even though replies classify them as fixed, tracked or declined; those UI badges do not mean an untriaged defect. Follow-ups include #95 worker failure-handler I/O, #104 dependency readiness, #106 host-commit enforcement, #110 failed/partial observation closure, #116 install-button eligibility and #117 lineage after a failed availability check.

The previous 893-test receipt means **893 tests run: 879 passed, 14 skipped**. It belongs to integration commit `9f97ab5`; the later final frontend-only integration had focused checks and fresh hosted CI. It is not evidence that 893 tests passed with another 14 skipped.

## Runtime reality

At initial inspection Studio listened on 8191 and ComfyUI on 8188, both online. ComfyUI's queue was empty. Studio retained completed and failed jobs alongside two uncertain records; stored job outcomes are not a count of approved images. The later full snapshot in `reconciliation/idle-model-cache-release/before.json` records 71 completed, 10 failed and two uncertain jobs.

The uncertain Qwen job `a2908800-7214-4caa-ad23-3844527cdf5d` retains prompt `f67b09af-08cb-47b6-aaa7-95a348ac57ab`. The uncertain portrait job `0cbaae1b-1134-548c-9e03-50bac00b75b9` retains prompt `5bcce6dc-60d5-4075-8c9a-be4416693a58`. An empty queue after a runtime restart does not settle either outcome and does not authorize a retry.

Under the owner's new runtime-repair request, a controlled ComfyUI restart preserved both recipes and unchanged public job records, then started the same runtime with one extra option: `--disable-pinned-memory`. Startup succeeded. About 12 GiB of committed memory was reclaimed; roughly 26 GiB headroom remained. This is startup and preservation proof, not yet a VAE-crash fix. Installed Python packages and ComfyUI source were not changed.

The diagnosis separates three failure classes: GGUF unpatch/mapped tensors, ordinary model/VAE unload, and safetensors/FP8 tensor moves. The GGUF stack has an exact upstream candidate in [ComfyUI-GGUF #445](https://github.com/city96/ComfyUI-GGUF/pull/445); it is an unmerged candidate, not an installed fix. Its original one-line workaround loses cleanup semantics and should not be used. Low host commit headroom is independently demonstrated; it does not explain every native access violation.

## New execution and recovery evidence

PR #125 added bounded opt-in recovery. A controlled stop of an idle ComfyUI initially exposed a Windows-specific fault: a one-second health deadline returned a timeout before the actual connection refusal arrived at about 2.04 seconds. PR #128 allows three seconds while retaining the process/work checks. With that fix deployed, the original test recovered through exactly one automatic launch, reconnected on loopback, left the queue empty and preserved both uncertain job records unchanged. It submitted no image. The new process uses `--disable-pinned-memory` and the 0.6 GB VRAM reserve. Native tensor-move crash recovery and prevention remain distinct.

The two screenshot-stack recipes from PR #127 then produced fresh outputs:

| Recipe | Result | Execution evidence | Visual inspection |
| --- | --- | --- | --- |
| WAI v17 + Noirpopwave 1.0 | `WAI-Illustration_00013_.png`, 832 x 1216 | job `2607afc1-84e8-4f46-ae43-a8042b1c6ae7`; prompt `c24ff30d-3932-4948-8c56-8ead32b10aef`; 38.26 seconds | Bold teal/amber poster treatment and coherent coat silhouette; requested handheld compass absent, lantern hand merits scrutiny. Owner chose **experiment only**. |
| Anima + Failleaf 0.5 + sky02 0.3 + BunnySlop v1 0.9 | `anima-artist-stack_00004_.png`, 832 x 1216 | job `c345a7e5-0f32-46d3-b09f-ac3628c77fd7`; prompt `e2195f08-5032-46ba-b965-0c5aac5b02f1`; 34.22 seconds | Softer dusk lighting and detailed cloth; two lanterns instead of the requested one. Owner chose **experiment only**. |

Both used seed `2026091201`, but their model families, prompts and settings differ, so they are demonstrations rather than a controlled causal comparison. Original PNGs remain in `C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio/`; full Studio recipes and inspection hashes are retained in the private session evidence. These runs exercise real inference and a model-family switch. They do not prove repeatability across seeds, close resemblance to the supplied sources, or a fix for all native crashes.

The browser screenshots provided later show prompt text and sampling settings even where the image API returned `meta: null`. The earlier missing-API result was a limitation of that response, not proof that the webpage had no prompt. Technical settings and exact version IDs are recorded for the additional modular baselines; copied source subject wording is not required.

PR #129 is now deployed with the local host-commit gate enabled. Its qualifying Qwen/FLUX.2 paths require 32 GiB before admission and immediately before each prompt submission. Live health exposed an actual 11.0 GiB reading, and a non-submitting check rejected the 1 MP FLUX route with no new job. The known follow-up in #106 is that low memory currently also blocks preview/recipe-check calls; retained prompt observation remains separate. Releasing the idle ComfyUI model cache through its own `/free` route recovered headroom to about 22.5 GiB without a process restart, job change or generation.

PR #126 is merged and deployed: Guided workflows provides installed-node discovery, graph editing and checked API export, plus registered-recipe tickets through the shared worker. Its ticket fix pins the actual experiments/runs roots so relocation cannot replay a prior dispatch. The integrated suite ran 942 tests, with 928 passing and 14 skipped. This is not full native ComfyUI visual-workflow parity; imported edited graphs remain export-only. PR #130 has since merged with shared document revisions, conflict checks and common agent commands; its integration ran 980 tests with 966 passing and 14 skipped. PR #132's process-identity hardening also merged after 988 tests (974 passed, 14 skipped). These two later changes are not yet in the running Studio at this snapshot. Named Step UI work in #131 remains under review.

The ten additional resource files have exact listing pins and are downloading into their model-role folders. Five now have completed local hash receipts: the Anima and Illustrious style adapters, Rapscallion, BunnySlop v5.56 and BunnyMid v1. Larger downloads remain incomplete. Do not treat a registry entry or `.part` file as an installed model. A 30-minute goal-scoped follow-up continues PR review and useful work, stays quiet when unchanged, and pauses when the goal ends.

## Decisions already supplied

- Anima direction: **pursue the new screenshot stack**.
- Pixel direction: **compass A**, seed `2026091103`; keep both originals.
- Brief: **fantasy character illustration pack**. See [the prepared brief](FANTASY-CHARACTER-BRIEF.md).
- Curation: the ornate witch with floating books and colourful witch holding a black cat were added to **Promising — needs correction** in Studio. Both stored image hashes and `needs_work` states verified; no image was regenerated.
- Paging: the owner authorized a fixed 64 GiB C: page file without automatic reboot. The configured initial/maximum values are now `65536` MiB; the effective allocation remains `40960` MiB until a later Windows restart. The original setting was backed up. This adds capacity and is not a native-crash cure.
- Character-consistency study: supplied standard costume, including the shown back view. This remains unchanged and separate from the new original-character brief.

These decisions do not approve unseen art or commercial use. The current remaining choices and their recorded answers are in [HUMAN_TODO.md](../HUMAN_TODO.md).

## Visual references

Preferred compass A, at its actual 128px export size:

![Preferred compass A](../experiments/curated/compass-first-batch/seed-2026091103-small.png)

Preserved alternate compass B:

![Compass B](../experiments/curated/compass-first-batch/seed-2026091104-small.png)

The two were generated with different seeds and the same LoRA settings. They are a preference comparison, not evidence of the LoRA's causal contribution.

Existing Anima examples are retained for comparison: [painterly field portrait](../examples/anime-fantasy-atelier/anima-artist-tags-no-adapters.jpg), [authored witch](../examples/anime-fantasy-atelier/anima-artist-stack-authored.jpg), [six-adapter witch](../examples/anime-fantasy-atelier/anima-reference-stack-1328x1776.jpg). The new screenshot direction is the owner's selected priority. The owner subsequently supplied [image 134076830](https://civitai.red/images/134076830) for technical analysis; its resource and settings investigation is recorded separately in the baseline guide.
