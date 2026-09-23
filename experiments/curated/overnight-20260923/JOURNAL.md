# Overnight lab journal (lab runner and judge), 23 September 2026

Worktree: `.claude/worktrees/agent-ab356a624a4a39b09`, branch `claude/overnight-lab-20260923` (from origin/main 8bc38a38).
Evidence root (in the worktree): `experiments/curated/overnight-20260923/<slug>/`; contact sheets `examples/overnight-20260923/`.
Journal location: the worktree isolation guard refuses Write/Edit on the main checkout's `.runtime/overnight/`, so this journal lives
at `<worktree>/.runtime/overnight/lab-journal.md` (asked `main` at 02:59 how to handle this and the lease note).

## 02:58 start

- Read PROTOCOL.md, CLAUDE.md, CURRENT_STATE head, the ten memory notes, the vram-spill krea_bench.py/json and qwen21-bench.json.
- Lease holder: coordinator (restart after #854). Waiting; no submissions. ComfyUI 8188 and Studio 8191 not answering at 02:58 (restart in progress, presumably).
- GGUF `krea2_turbo-Q5_K_M.gguf.part` at 6.82 GB of ~8.87 GB at 02:58.
- Observation: Qwen-Image 2.1 (6.9 GB diffusion) ran 0.68-1.0 s/step at 832x1248 once nothing spilled, while Krea 2 fp8 (12.5 GB loaded) ran 35.4 s/step
  with 474 MB shared. Hypothesis H1: fp8 Krea is still WDDM-thrashing (process 14.1 GB dedicated + dwm/others > 16 GB), so the 8.87 GB GGUF
  should be several times faster per step, not marginally. Test: same graph/seed, fp8 vs GGUF, record s/step + peak dedicated/shared.
- Also noticed: `z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors` (6.2 GB) is already installed while the `zimage` preset still uses bf16 (178 s warm). Census candidate.

Plan while waiting: adapt krea_bench.py into a general bench runner (any graph, any overrides, lease + queue guard, GPU sampling,
step-time parsing), a blind A/B renderer with sealed keys, and a crop helper for judging.

## 02:59-03:10 lease granted, tooling, speed census running

- 02:59:44 lease holder -> overnight-lab (coordinator; primary PID 56556 at --reserve-vram 0.6 --disable-pinned-memory). Coordinator owns lease-note
  writes; I SendMessage main at each experiment start/finish. Coordinator hard rule (SFW only, never open/judge adult images, excluded paths
  output/Studio/nsfw/, experiments/curated/nsfw-lab-*, examples/nsfw-lab/; explicit output -> "skipped: adult content"; save prompt IDs before
  polling; POST network error = unresolved, never retried) is built into labkit.py.
- Correction: my 03:08 "census start" message to main was a guessed time; the first census job was submitted at 03:02:07 (results.json).
- Tooling in `experiments/curated/overnight-20260923/`: labkit.py (guard, run_graph/run_studio, GPU timeline, /internal/logs, ws events for
  direct runs, seal/judge), crop.py, addjudge.py, phases.py.
- Census (speed-census/, Studio jobs at authored defaults): wai 50.3 s, anime 43.4 s, pony 42.3 s, noob 46.3 s, cstati 44.5 s, yumeflux 38.4 s,
  anima-portrait 34.2 s, anima-artist-stack 34.3 s, janima 32.2 s; zimage and krea-portrait pending.
- FINDING F1: every SDXL preset samples in 6-9 s (0.2-0.27 s/step) but the job takes 38-50 s: ~20 s cold checkpoint load + ~11 s VAEDecode
  during which 3-5 GB of the ComfyUI process sits in WDDM shared memory (ComfyUI first "Unloaded partially" 1.3-1.9 GB of the UNet). Anima
  (WanVAE) decodes in ~3 s with a brief 3 GB shared blip. Next: sdxl-vae-decode (VAEDecode vs VAEDecodeTiled 512/1024, cached latent).
- Judgements (open, not blind; census): wai fixable (2 lanterns, outfit drift), anime fixable (inset sheet), pony REJECT (faceless black
  silhouette head), noob fixable (fused fingers), cstati fixable (mitten hands), yumeflux fixable (mitten hand), anima-portrait fixable (no sword),
  anima-artist-stack fixable (cloak lattice mess), janima KEEP. Hands remain the dominant defect (5 of 9).

## 03:17-03:25 census done, PR #859; owner request for a showcase suite

- Census finished 03:17:55: zimage bf16 308 s (28.7 s/step, 715 MB shared while sampling), krea-portrait fp8 209 s (16.9 s/step, no
  sampling spill, 5.4 GB decode spill). Judged all 11 (3 keep, 7 fixable, 1 reject). README + phase table + git-safe sheet. PR #859.
- Owner request (~03:40 per PROTOCOL "Subjects"): famous characters, dynamic poses, non-nude #403-A4 fanservice for canonically adult
  characters only; images of famous/fanservice stay out of Git under output/Research/overnight-20260923/<exp>/ with index.html.
  Built suite.py: portrait (Makima), action (2B), duo (Tifa + Aerith), environment (OC), pinup-swim (Yor Forger), glamour (Raiden
  Shogun), hands (OC alchemist); seeds 2026092301-07; tag + prose dialects; SFW negatives always added. Exclusions: no Ellen Joe, no
  *_yande.re_* inputs.
- Krea fp8 without spill (16.9 s/step) changes H1: the GGUF may not be faster now; the A/B decides.
- Next: sdxl-vae-decode (branch claude/overnight-lab-vae-decode) once the coordinator says the Studio restart is done; then Krea A/B,
  Z-Image A/B, hand-fix (sources = WAI suite plain decodes).

## 03:24-04:00 VAE decode A/B done; #859 review fixes; Krea GGUF surprise

- sdxl-vae-decode (WAI, suite x plain/tiled512/tiled1024, 21 prompts, ws node timings): tiled512 decode 1.23-1.84 s, no spill on
  every case; plain 1.6-8.5 s, 2.3 GB spill on 2/7; tiled1024 9-17 s, 2.8-4.2 GB spill always. Pixel diff tiled512 vs plain mean
  1.5-2.3/255, no grid seams. Blind: all three decodes indistinguishable -> tie (4.31 each). Switch-condition test still to run.
- #859: Codex P1/P2 fixed (954a54a2; the census records' sampler_runs repaired, Anima s/step withdrawn as unverified; guard fails closed),
  review accuracy fixes 6d1a6e7a. ab_vae.py rode along in 954a54a2.
- Rubric corrections R1-R6 from the review judge adopted (R1 named defect needing fix -> <=3; R6 no taste calls between clean looks).
- Queue from coordinator after Krea A/B: (1) combine re-proofs on adult original pair (4 routes x 3 seeds, Studio), (2) q-32 LoRA retests
  (WAI Masterpiece 0.4, WAI Micro Details 0.5, NoobAI Flat Color 0.85, Pony Gothic Neon 0.85) vs no-LoRA, 3 seeds, (3) Klein restyle of the
  throne witch (allowed again) with "bare feet" + true colours (purple hair, blue eyes). Exclusions: Ellen Joe, yande.re files, Megumin sheet,
  KonoSuba group art.
- KREA: gguf-portrait (Q5_K_M) ran 112 s/step, 920 s total: ComfyUI kept 3.7 GB of the Krea text encoder resident next to the 8.8 GB GGUF
  and the process spilled 1.9 GB. Script stopped after that image (poller only; prompt finished; finalize() recorded it).
  fp8-portrait right after a TE load: 54 s/step, 819 MB shared while sampling (census had 17-19 s/step with 274 MB). dwm grew 0.97 -> 1.62 GB.
  fp8-probe (POST /free unload_models, cached conditioning, so the TE never loads): 13.3 s/it live. HYPOTHESIS H2: Krea speed is set by
  whether the text encoder was just resident in VRAM (fragmentation / unreturned blocks push the diffusion weights over the edge).
  Test next: gguf probe (no TE) and fp8 with CLIPLoader device=cpu (TE never in VRAM).

## 04:00-04:52 Krea finished (PR #873), VAE final (#868 9e005e48), q-32 done, Combine running

- krea-gguf: GGUF+CPU encoder 2.37-2.45 s/step, 77-101 s per new prompt, 38 s same text; fp8 38-66 s/step tonight (dwm grew);
  GGUF with GPU encoder 112 s/step (encoder co-resident). Blind tie 3 seeds + 4-way portrait; retro LoRA identical. Commit peak 62.8 %.
  PR #873 (stacked on #868) adds the pin + krea-portrait-gguf + krea-anime-atelier-gguf (verified:false; Studio proof after merge).
- GPU window for the coordinator's Qwen proofs: 04:32-~04:34 (switch refused, 2 s probe timeout bug); lease back to lab.
- VAE: after-switch rows (7 switches, 0.25 s sampling): tiled512 median 1.30 s vs plain 6.79 s, but tiled spilled 1.2 GB on 3/7.
  Claim qualified to "usually spill-free". Codex threads fixed + resolved. Final head 9e005e48.
- False alarm from the coordinator about famous characters in the VAE sheet: verified the committed blob is OC-only; no rewrite.
- q-32 (21 blind): WAI Masterpiece 0.4 / Micro Details 0.5 tie control (4.47); NoobAI Flat Color 3.93 vs 4.13 (tie); Pony Gothic Neon
  3.93 vs 4.00 (tie on mean, 1 reject: subject replaced). No youthful Pony faces. README not yet written.
- R7 in addjudge (only when a fix is named). judge_batch.py for batches (the worktree guard refuses $VAR command names).
- Combine re-proofs: pose source v1 REJECTED (bent-over rear view; not used); v2 seed 2026092346 (front wide stance, arm up); keypoints
  authored by eye; staged (character 906acc81..., pose b72d60be..., skeleton 46eee08a...). 12 Studio jobs running ~80 s each.
- Queue next: Klein restyle (9), hand-inpaint (15, mask staged via script), krea-refine foxes 0.25/0.35, Style+Pose pack re-proof,
  then own backlog: Z-Image fp8 A/B, Krea target stack on GGUF, hand-fix detailer, LoRA stacking.

## 04:52-05:10 Combine + q-32 done (PR #875); #868 merged; #873 retargeted to main; Qwen window

- Combine (12 Studio jobs 04:47-05:04): skeleton 3/3 keep; copypose 2 keep + 1 fixable; depth & cut88 1/3 keep each (blank face / dark
  featureless face on seeds 41 and 43, identical with and without the cut). GPU free for the coordinator at 05:04:41.
- q-32: all tie controls. README + sheet (OC only). PR #875 (branch claude/overnight-lab-combine-q32 from main).
- #873 review fixes eddf54ae. #868 merged as 2201997e.
- Next when GPU back: klein-restyle (9 Studio), hand-inpaint (stage + 15 Studio), krea-refine-foxes (stage + 6 Studio),
  stylepose-pack (stage + 18 Studio). The Studio restarted for Qwen: staged upload names should still resolve (ComfyUI input folder),
  but re-stage if a job rejects a reference.
- Hypothesis for later: depth-route face loss comes from the portrait->full-body scale gap; test = same route with a full-body
  character picture (pack step 2 render) as Picture to keep.

## 05:11 GPU back (primary PID 46488, Studio PID 21412)

- Chain started: krea atelier target stack on GGUF (timing for #873), hand-inpaint (stage + 15), klein-restyle (9).
- Decided to deprioritise LoRA stacking (backlog 4): #862 and q-32 show every single-LoRA "winner" ties its control, so pairs of ties
  are unlikely to show a measurable difference; GPU time goes to the correction pass and Z-Image speed instead.
- Prepared combine-scale (depth route with a full-body character picture, hypothesis: the face loss is a portrait->full-body scale gap).

## 05:10-05:50 GGUF proofs (#880), hand-inpaint (#881), restyle + scale (#883)

- #880: atelier target stack on GGUF 173 s (976da1a8) vs 828 s fp8; Studio proofs krea-portrait-gguf keep, krea-anime-atelier-gguf fixable
  (painted @NJSW33T watermark; 2/2 Niji runs on GGUF). verified:true. Review fixes 70718e11, Codex fixes 0c73c0a5 (runtime identity in
  labkit.run_studio, CURRENT_STATE section), merge with main 1f72723f.
- #881: hand-inpaint. masked 0.4 fixes 0/3, 0.6 3/3 but seam; feathered (GrowMask 12 + ImageBlur 24/8) 3/3 no seam (edge band 1.5-2.2 vs
  6.8-8.7). Preset default 0.4->0.6 + feather; visual graph rebuilt; judging was OPEN (key read before records; honest in README).
  Heads 0495114b -> 65cdfc3e -> 6ee9527f. Review judge's second judge (#882) agrees (seam gone 2/3, slight smear s62).
- #883: klein restyle BLIND: colours named fix drift 3/3; bare feet or stocking named fix the foot 3/3. combine-scale falsified scale hyp.
- Chain running: krea-refine foxes on fp8 (thrashing ~70 s/step, ~350 s per job) -> stylepose pack (18) -> zimage (13).
- Lesson: switching branches in this worktree while a chain runs swaps labkit.py under later chain steps; harmless tonight but
  keep the chain scripts' imports in mind. R8 adopted for correction passes (adherence = defect fixed, control = rest kept).

## 05:50-06:16 masked-repair proof (#885), foxes (#886), restyle/scale fixes (#883)

- #880 and #881 merged; Studio restarted (PID 43532). anime-masked-repair Studio proof: job 1f9b3e11, five digits, no seam -> #885.
- krea-refine foxes (6 Studio jobs, fp8 338-420 s each): 0.25 keeps 4 foxes 3/3 (keep, keep, fixable); 0.35 loses foxes 3/3 -> #886
  proposes default 0.25.
- #883 review + Codex fixes (14fd1224, 261320ab): IDs on judgements, partial blinding stated honestly, association not causation.
- Chain now: stylepose pack (18 Studio; first job 199 s cold, then ~20 s) -> hand-fix detailer (12) -> zimage (13) -> krea-trigger (8).
- Next if time: SDXL tiled-decode preset change for the 6 census presets + 6 Studio proofs.

## 06:10-06:30 foxes (#886), masked proof (#885), HOLD tiled (#888), hand-fix + stylepose (#890)

- krea-refine: default 0.35 -> 0.25 (#886; Codex fixes 107584d1: continuation test + CURRENT_STATE). IDs filled; labkit.judge now looks
  up job/prompt/original by sha256 and refuses unmatched images (--no-run for sealed sources) -> 6361bbd7.
- anime-masked-repair proof 1f9b3e11 keep -> #885 (+ CURRENT_STATE/README corrections 85cbc1c5).
- Coordinator decision (C) for SDXL tiled decode: HOLD PR #888 with the six presets verified:false; not merged tonight.
- hand-fix detector route: 0/4 fixed (misses, wrong hand, redraws six as six, off-style at 0.6). stylepose: poses hold, colours burn
  at style weight 0.7 -> all reject. PR #890.
- Z-Image fp8 + CPU encoder: 0.72 s/step (bf16 28.7), no spill, 37-76 s per image (CPU encode dominates). Running.
- Queue: zimage fp8 (GPU encoder) + bf16 pairs -> krea-trigger (8) -> stylepose weights 0.3/0.45 (6 Studio).

## 06:30-07:00 Z-Image A/B done (write-up ready), R8b fixes (#890 f120a112), trigger test running

- Z-Image: fp8-cpute 0.72-0.77 s/step, 37-76 s/image, no spill (7/7); fp8 GPU encoder 532 s (59 s/step, 2.6 GB spill: the 7.7 GB
  Qwen3-4B encoder stays resident); bf16-cpute sampling fine but the decode spills 1.8 GB (32-34 s). Blind tie on 3 cases (9 keeps).
  Proposal ready (.runtime/lab-scratch/zimage_fast.py): pin z-image-turbo-fp8-kj + a zimage-fast preset (verified:false).
  Apply after the chain finishes (the chain imports files from this worktree; do not switch branches while it runs).
- R8b: 10 hand-fix outputs rescored to reject; addjudge --correction-pass fixed|partial|untouched enforces it.
- Chain: krea-trigger (8 GGUF runs, ~2 min each) -> stylepose weights 0.3/0.45 (6 Studio jobs).

## 07:00-07:16 Z-Image, trigger, style weights -> PR #893

- #890 merged. #893 (from main): zimage-fast preset (fp8 + CPU encoder, verified:false) + pin; trigger test (trigger word painted
  wherever it sits; none 0/2); stylepose weights 0.45/0.3 remove the burn.
- GPU idle at 07:15. Candidate next jobs (priority): zimage-fast Studio proof after #893 merges; krea-refine-gguf variant timing;
  3-seed trigger confirmation + look A/B; LoRA stacking skipped (singles tie their controls).

## 07:14-07:25 krea-refine GGUF, #893 fixes, trigger follow-up + Klein split queued

- krea-refine GGUF+CPU encoder: 84 s first, 26-28 s cached vs fp8 338-373 s; blind pairs tie (keep 2 / reject 1 each; the reject is
  the seed-83 fox head, R8a). Written into krea-refine-foxes/README (final PR, stacked on #893).
- #893 fixes: a1b895ae (wording), 6aea8c3b (CURRENT_STATE section; Codex thread resolved).
- Running: trigger2 (12 GGUF prompts: start-1.0, none-1.0, start-0.7, none-0.0 x 3 seeds), then the Klein split (6 Studio jobs).
- Final branch claude/overnight-lab-final is stacked on #893's branch (krea-trigger files live there).
- Stop submitting by 08:25; final PR with JOURNAL.md; final report to main.

## 07:25-07:40 Wrap-up (the owner asked to save and shut down)

- #893 merged. zimage-fast Studio proof: job 4f5974cc (prompt 9bc91aa8), 56.8 s, 0.75 s/step, 79 MB shared, agent-judged keep
  -> `verified: true` with an execution note (bff141b9).
- Style+Pose seed 71 rescored under R9: WAI_00046_ and WAI_00043_ -> control 1, reject (a walking figure), with a note.
- PAUSE written at about 07:35 (`.runtime/lab-scratch/PAUSE`). The in-flight trigger follow-up finished (12/12, last prompt
  8803956c); nothing was cancelled or resubmitted. The Klein split was refused by the PAUSE: no split job exists.
- Trigger follow-up judged blind (12 records before the key): no trigger 0/3 text and the same look (style 5 on every seed);
  start-1.0 1/3; Niji 0.7 1/3; Niji off plainer 3/3 (the blind notes picked it each time). Over both runs: 0/5 untriggered vs
  3/5 triggered at the start.
- Final PR from claude/overnight-lab-final (stacked on #893, now merged): zimage-fast verified, krea-refine GGUF, the R9 rescore,
  the trigger follow-up, the Klein split code (not run), this journal as JOURNAL.md. No GPU or Studio job after 07:35.
