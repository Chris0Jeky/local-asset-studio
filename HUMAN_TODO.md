# Creative choices

The earlier creative choices and q-1 through q-6 below are answered. The configured page-file increase was restarted by the owner and verified at 64 GiB; no restart action remains.

- [x] Choose your preferred pixel-art direction: compass A, seed `2026091103` (owner, 12 September 2026). Both compass originals remain preserved; the two seeds are not a LoRA-on/off comparison and neither is accepted as a finished game asset.
- [x] Pick a focused production brief: **Fantasy character illustration pack** (owner, 12 September 2026). The prepared brief is in [FANTASY-CHARACTER-BRIEF.md](docs/FANTASY-CHARACTER-BRIEF.md); this selects the work, not finished-art acceptance.
- [x] Choose an initial private shortlist (owner, 12 September 2026): the ornate witch with floating books and colourful witch holding a black cat are in **Promising — needs correction**, both marked `needs_work`. Original hashes and membership were verified. This is not finished-art or commercial-use approval; future candidates still need review.

The live repository visibility was observed as **PUBLIC** on 13 September 2026. This records the observed state; it does not infer owner approval or a visibility change.

## Style + Pose recipes — open items

**q-27 — creative review of Restyle a picture (open).** You said the first Restyle result (throne witch through the Nova Style + Pose board with `file.png` as the style picture, job `69d3962b…`) was not good and supplied a target render (soft high-key light-novel finish, costume and throne kept). The route now leads with a new recipe, **Restyle a picture (WAI v17 + light-novel look)**: the picture is the starting latent (Denoise 0.85) and the pose source, WAI v17 with the Mishima Kurone LoRA at 0.8 and fixed finish terms give the look, a face pass cleans the eyes, and the style board ships OFF because at every weight tried (0.2–0.6) it tinted the costume towards the style picture's palette. Proving run through the page: job `0c13590c…`, 86 s; sheets `examples/style-pose/restyle-picture-proving.jpg` (source, style, your run, shipped recipe) and `restyle-picture-research.jpg` (the four deciding renders); evidence in `experiments/curated/style-pose-matrix/2026-09-14-restyle/`. Decide: (a) is this finish close enough to your target, or should *Momoko look instead of Mishima* be the default; (b) should the style board stay required when it is off by default (issue #351 would make it optional); (c) note q-26: Mishima Kurone and Momoko are artist-style LoRAs the artists did not license, so the recipe's default look depends on your answer there. **Later the same night** the route gained **Restyle a picture (FLUX.2 Klein 4B, keeps everything)**, listed first: no style board, no LoRA, the picture is the model's own reference and the prepared wording carries the look (edit its first sentence for another finish); on your throne witch it kept the wink, robe, throne and hat with the soft finish in about 20 s warm (job `db25b173…`, sheet `examples/style-pose/restyle-klein-proving.jpg`). Decide (d): should the Klein recipe lead the route (as shipped) or the WAI one; and whether the default finish sentence reads as the look you wanted. **Late the same night**, after your report that the edit "regenerates the same exact image" and that you wanted the pose of your second picture: a **Combine** route now exists (*Continue with this → Combine → Put this character in another picture's pose (FLUX.2 Klein 4B)*), which puts the witch into your Santa picture's pose while keeping her hat, robe and face (job `fb0eb95d…`, sheet `examples/style-pose/combine-klein-proving.jpg`; research sheet `combine-klein-research.jpg`). It asks you to fill two bracketed parts of the wording (who is in image 1; the pose in a few words) because the model ignores the pose picture without them. Decide (e): is that result the kind of thing you wanted from "the pose of the second image", and is filling two bracketed parts acceptable, or should the recipe guess the subject from the source description (which then also names the old pose and undid the transfer in research)? The look-from-a-picture recipe (*Restyle a picture in another picture's look*) is a measured compromise (colours or look, not both); tell me whether it earns its place. Agents do not tick this. Your own first run (`aebf406f…`, sheets `examples/style-pose/combine-klein-owner-run.jpg` and `combine-klein-owner-fix.jpg`) is the current evidence: the caps were the wording's fault and are gone; whether the pose follows closely enough is yours to judge. **(f)** The Combine route now leads with a FLUX.2 Klein 9B recipe (pose first, character swapped in; 4 of 4 seeds held your bent-over pose, sheet `examples/style-pose/combine-klein9b-pose-first.jpg`). The 9B model is released under the FLUX non-commercial licence (recorded, not re-read); the Studio labels it private-experiments-only. **Answered by the owner, 15 September 2026:** the non-commercial licence "is not an issue" for how these pictures are used (recorded from the owner's message; it is the owner's use decision, not a legal reading of the licence). The pose-first result is **not** the baseline meant: the owner wanted the pose changed completely (the SHARK character in the bent-over maid picture's pose) and got "something that goes in that direction, a much bigger step but not complete"; of all the renders, the Qwen Image Edit one (`Research/qwen-pose_00001_.png`, prompt `659e4504…`) most resembles the objective, but at 14.5 minutes it is too slow, and the Studio's workflow itself is in doubt for this kind of experimenting. The open work is tracked in the follow-up issue named in `CURRENT_STATE.md` (15 September, pose round two); (f) needs no further owner decision.


**q-26 — which of the seven new Illustrious LoRAs may the character pack use (open).** civitai's flags differ per file and are recorded in `models/library.json`: Mishima Kurone, Momoko and Konosuba SD8 allow Image/Rent/Sell; Glossy, Fantastic Days and Detail enhancer allow Image and Rent but not Sell; Shiny Nai allows Rent only (no Image, no Sell). The Mishima Kurone and Momoko files are artist-style LoRAs the artists did not license. Decide which are acceptable for the pack's intended use; the recipes accept any of them by filename. Agents do not tick this.

**q-25 — creative review of the Style + Pose results (open).** Three sheets: the six-checkpoint matrix
(`examples/style-pose/matrix/assessment-sheet.jpg`), the board LoRA sweep (`board-lora-sweep-wai.jpg`,
`board-lora-sweep-yumeflux.jpg`, `board-combine-probes.jpg`) the two verifying runs (`examples/style-pose/board-verify-*.jpg`) and the Nova comparison (`examples/style-pose/matrix/nova-vs-wai.jpg`),
evidence under `experiments/curated/style-pose-matrix/`. My reading: WAI v17 or YumeFlux, the board averaged at the
shipped 0.7, pose strength 0.9, Mishima Kurone 0.8 + Glossy 0.6. Decide whether that direction is right for the fantasy
character pack and whether the shipped defaults (style weight 0.7, pose strength 0.9) should change. Suggested action:
run the *3-seed audition* variant with your own pictures, then mark keeper / needs-work in the library. Agents do not
tick this.

## Anime & fantasy atelier — open items

**q-1 — koukouya Krea 2 style LoRA: done, 12 September 2026.** The owner supplied a civitai API key; it is stored
as the user-scope environment variable `CIVITAI_API_TOKEN` (not in the repository). `scripts/civitai-fetch.py`
installed `krea2_koukouya_style_c1-st3000.safetensors` with a receipt whose SHA-256 matches the listing
(`8cf2068c…`). Verified by the receipt in `.runtime/downloads/receipts.json` and the registry entry in
`models/library.json`, not inferred.

**q-2 — creative review of the atelier results: answered by the owner, 12 September 2026.** Recorded verbatim
in spirit under "Recorded owner decisions" below and in `docs/ANIME-FANTASY-ATELIER.md`. Nothing further to
decide here; the follow-up work (a correction pass for hands, faces and small details) is tracked in
`CURRENT_STATE.md`.

**q-3 — Anima direction: answered by the owner, 12 September 2026.** The owner chose: **"Pursue the new screenshot stack"**, superseding the older two-option comparison below as the immediate priority. The owner subsequently supplied `https://civitai.red/images/134076830` for technical analysis. Build compatible Anima and SDXL starting points from the resource metadata. This is a direction choice, not a claim of exact reproduction, art acceptance or licence clearance.

Historical comparison: three outputs exist on Anima base v1.0
(`anima-artist-stack-authored`, `anima-artist-tags-no-adapters`, `anima-reference-stack-1328x1776` in
`examples/anime-fantasy-atelier/`). The previous choices were the six-adapter
reference stack (civitai image 139608451) or the adapter-free painterly artist tags (`@synswt, @koukouya, @kyano`,
images 131843207–131843406). Execution is not art approval, and the six adapters' civitai terms are recorded,
not cleared.

**q-4 — page file: authorized, configured and restarted, 12–13 September 2026.** The owner explicitly answered: **"Authorize a fixed 64 GiB page file; do not reboot automatically"**. After backing up the original settings, the elevated helper set C: initial and maximum to `65536` MiB; both values were verified at 22:32 UTC. The owner later restarted Windows. A post-restart read confirmed `C:\pagefile.sys` at `65536` MiB and about 35.9 GiB of commit headroom, above the 32 GiB submission gate. This specific authorization supersedes the earlier owner-only restriction for this change; it does not authorize driver, package or other system changes, or prove a native-crash fix.

The requested recheck is complete. Each large Qwen/FLUX proving run still has to pass the live headroom gate at submission time. Rollback, if requested later, is the recorded original fixed `40960` MiB initial/maximum setting.

**Gate now deployed:** PR #129 implements the rule, and local `enforce_host_commit_headroom` is enabled. A non-submitting live check rejected an eligible 1 MP FLUX graph at 11.0 GiB headroom without creating a job. A later idle ComfyUI cache release recovered headroom to about 22.5 GiB, with the same process and unchanged jobs; this remains below the required threshold. The historical operator-only description below refers to the original handoff, not the current application.

Historical measurement: fixed 40 GB gives the ~73–77 GB commit limit that #77 and #89 hit. Measured 12 September
2026: `SizeStoredInPagingFiles` 41,943,040 KiB, commit limit 77,014,286,336 B; #77's failure was at
97 % committed, and a Qwen job at `--reserve-vram 0.6` still failed on a host allocation at 87 %
committed, so the VRAM reserve is measurably not the lever. The ≥32 GiB commit gate (raised from 20 GiB after the run above started at 29 GB headroom and still failed) is documented as
an operator rule in `docs/RUNTIME-PRECONDITIONS.md`; it is **not enforced by code** — nothing in
`app/` samples commit headroom before submitting at the original handoff. #77 says not to treat paging as a default fix. The later explicit owner decision and verified configuration above supersede this historical undecided option.

**q-5 — Hunyuan3D 2.1 territory (issue #26): closed, owner-confirmed 11 September 2026; recorded 14 September 2026.** In the [issue #26 owner comment](https://github.com/Chris0Jeky/local-asset-studio/issues/26#issuecomment-5637883899), Chris0Jeky stated: “I acknowledge this issue and I confirm that I do have authorisation as this will be used in authorised territory only. Account for that and move on without restricting models and capabilities.” This records owner-confirmed authorised-territory use for Hunyuan3D 2.1. It is not independent legal verification, blanket approval for other models or territories, a change to the published terms or new restrictions, or a new generation allowance.

**q-6 — three UX questions: answered by the owner, 14 September 2026.** The owner gave a first-hand statement in free text instead of the three questions; it is recorded and mapped to root causes in [docs/UX-AUDIT-2026-09-14.md](docs/UX-AUDIT-2026-09-14.md) and tracked as #278. In short: the Studio still feels unusable for the real goal; guided paths are wordy and advisory; Plan comparison and Runs & review are unexplained; the review loop lacks automation; Prompt Lab's locked buttons never say what is missing and its Create handoff never unlocked; the workflow builder's canvas and prompt field are clunky. Nothing here is a creative or licensing approval; the owner's next first-hand pass after the fixes is the verdict.

**q-7 — first-hand pass over the merged UX wave: open.** Seven PRs answered the 14 September statement (#278;
[docs/UX-AUDIT-2026-09-14.md](docs/UX-AUDIT-2026-09-14.md) lists what changed where). The Studio on 8191 already serves
them. Please try, in your own words: (1) Prompt Lab with a reference or an avoid term on the default profile, then
"Open Create with this prompt"; (2) Guided workflows → Edit or preserve a character; (3) Plan a comparison from a
recipe and read the summary line; (4) Asset library → Review next, with K / W / X / S; (5) the node builder's canvas
and a prompt field. Say what still feels wrong. Nothing here is a creative or licensing approval.

## Recorded owner decisions

**New WAI baseline, 13 September 2026:** the owner answered **"Keep only as an experiment"** for the teal-coat lanternkeeper, job `2607afc1-84e8-4f46-ae43-a8042b1c6ae7`, output `WAI-Illustration_00013_.png`. It remains outside the promising shortlist; successful execution is not creative acceptance.

**New Anima baseline, 13 September 2026:** the owner also answered **"Keep only as an experiment"** for job `c345a7e5-0f32-46d3-b09f-ac3628c77fd7`, output `anima-artist-stack_00004_.png`. It remains outside the shortlist; no duplicate-lantern correction is commissioned from that optional choice.

**Modular baselines, 13 September 2026:** the owner clarified that no sexual imagery will be produced and requested the referenced resources for creative freedom. Build architecture-compatible baseline graphs with independently editable style controls and optional correction, pose/reference and upscale stages. Resource listing names do not become prompt instructions.

**Modular Anima baseline choice, 13 September 2026:** the owner chose **B — softer cinematic shading** as the starting look for the fantasy-character pack. This selects the look only: both A (base) and B (first style) remain experiments, neither enters the private shortlist, and no art acceptance or licence decision is implied. The older lanternkeeper demonstrations remain experiment-only. The owner-controlled restart is complete; model execution and art acceptance remain separate gates.

**Character-consistency pilot canon, 12 September 2026:** In response to the choice of reference canon
for the twelve-case pilot, the owner answered: "Use the supplied standard costume, including its shown
back view". This selects the standard supplied design for the private reference-preservation study;
it does not approve generated outputs, other costume sets, model terms or commercial use. The exact
decision and revision-bound canon attestation are retained in `C:/AI/character-lab/pilot-20260912/`.

Recorded owner decisions, 11 September 2026: use free alternatives to NIJISIS
instead of spending Buzz; MiniMax H3 is being used from an eligible territory.
These decisions do not approve the generated art. The Workflow Lab expansion
requires no additional disk space at the current installed footprint.

**Superseded, 12 September 2026:** the owner downloaded the NIJISIS Krea 2 LoRA
(`NIJISIS_KREA_2_krea2_3274861_epoch_8.safetensors`, civitai model 2863875 version 3302337) and spent
the Buzz for it. The 11 September "use free alternatives instead of spending Buzz" note no longer
applies to this file; the free Comfy-Org and fal style adapters remain installed and in use alongside
it. Recorded from the owner's statement, not inferred from a download receipt. The other decisions
above stand.

**Owner's creative review, 12 September 2026 (q-2, recorded from the owner's message):**
`WAI-Illustration_00012_` okay-ish, not spectacular, some imperfections. `noob_00004_` has potential but six
fingers and the artistic side is not popping. `pony_00002_` a complete mess. `krea-anime-atelier_00001_`
genuinely great. `krea-style-lab_00001_` nice from afar, the foxes lose detail and their faces are morphed.
Probes: `witch-target-ersde-4step` very good; `witch-target-plus-baroque-oil-4step` good;
`witch-target-stack` very good; `witch-target-stack-4step` very good; `witch-nijisis-baseline` potential
but imperfect; `witch-nijisis-4step` very good; `witch-airy-watercolor-short-4step` good with a lot of
potential. Almost all carry some imperfection the owner would like a correction workflow for.
