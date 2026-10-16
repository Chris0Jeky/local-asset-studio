# Local Asset Studio UX re-audit v2 (16 Oct 2026)

## 0. Read this first: what was actually audited
The live Studio at 127.0.0.1:8191 does NOT serve tonight rework. The served checkout is
the primary local-asset-studio checkout at 7b5ef21b; git status -sb says
"main...origin/main [behind 119]" (origin/main was then 3471636d, #1441). Live checks (jlive.py): no #makeTune,
/static/make.js is 257 lines, How many defaults to 4, Models and setup is 23,358 px tall (was 23,400).
So the live app is still the first audit app.

To audit the rework I ran origin/main 3471636d from a detached worktree (C:/las-ux2, now removed) on port 8291:
its own Python process (so the per-recipe model field exists and Tune works), an isolated empty experiments root
(C:/las-ux2-exp, removed), a config pointing at the same ComfyUI (read-only use), Host/Origin checks patched to 8291
in the launcher only (run_server.py in this folder; no tracked file touched), the repo examples/ copied in so look
thumbnails load, and 8 SFW pictures imported through the Studio own import API so picture goals had something to pick.
Server stopped, worktree and scratch store removed. Live 8191 was only read (jlive.py).

Safety: POST /api/jobs and prepare-then-jobs were aborted by page.route; blocked attempts were recorded and their
request bodies read; no job reached either server. Side effects on the sandbox only: POST /api/estimate,
/api/looks/prepare, /api/assets/reference, /api/upload, /api/assets/import. The Lab 1016b runs were not touched.
No explicit images were opened.

Sandbox artifacts (not UX findings):
(a) Krea looks estimate "About 21-42 s" against the label "slow, about 10-17 min" because the sandbox has no run
history (the first audit on the live store saw "About 36 min" for 4);
(b) pictures are titled seed-xxxx.png because they were imported;
(c) imported pictures have no recorded recipe, so Vary, Fix face and Same recipe, new seed could not be exercised end to end;
(d) Make-labelled library assets were simulated by rewriting the /api/workspace response in the browser (j10.py).

## 1. First audit: 27 problems
1. Make pictures hidden from library: FIXED. workspace.js:21 exempts the "Make" label prefix; with simulated labels Mine showed 3 Make + 3 unlabelled and hid 2 agent runs. Not tested with real Make assets.
2. No model/LoRA choice in Make: FIXED. Tune this look: base model, LoRAs, steps, sampler, negative, seed.
3. Cannot tweak a result: PARTLY. Edit and re-run restores model, LoRA + strength, seed lock, shape, count (verified), but only for the last 6 runs of this browser; Library path unchanged; no per-picture tweak.
4. Disabled buttons without reason: PARTLY. Result cards now hide inapplicable actions and the Vary hint is honest; Fix or upscale still defaults to the unavailable "Fix face" and says "Use Continue with this" (not a Make control).
5. Picture goals leave Make: FIXED. goal, picture, Generate, all in Make.
6. Restyle has no look chooser: FIXED. 22 looks as pictures, or describe in words.
7. Pose needs two slots: FIXED. Character / Pose slots, picture or drawn figure, placeholders became fields.
8. Helper outputs shown as pictures: FIXED in Make pickers (mask filtered by filename, title = words + date, search). Library not rechecked.
9. Asset dialog form-first: FIXED. Picture at y=72, Continue first (desktop and 390 px). Residual: seam and parallax forms sit above Vary / Same recipe; the sticky save bar overlaps the last control.
10. Same recipe, new seed no-op: LIKELY AUDIT ARTIFACT. The headless browser auto-dismissed the native confirm(); commit 49a698dd now says "Not prepared: the confirmation was declined". Accept path not verified (no recipe asset in sandbox).
11. Default 4 pictures on slow looks: FIXED. Slow looks default to 1; estimate turns warning colour above 10 min. No confirm.
12. Quality vs speed not a control: PARTLY. Steps Draft (half) / Finer (1.5x) in Tune; no Draft-to-Final path.
13. Generate below the fold: PARTLY. Goals collapse and results sit beside the form; sticky Generate only works inside its own column (see N4).
14. Missing-model dead end: FIXED (simulated via /api/health). Warning links to #models?need=RECIPE, which lists only the needed files with Source link, target folder, copy buttons. A real Install button was not verified (the files here are pin-only).
15. Models as inventory: FIXED. 2,717 px instead of 23,400; search on top filters looks and cards; "What you can make" with thumbnails (23 of 23 ready); Used by and trigger on cards.
16. Compare cannot compare: FIXED for looks only (see N6).
17. Naming collisions: PARTLY. Make says "look" throughout, "Compare and review" is plain. Full editor still "Follow the idea.", "recipe", "saved look", orange accent.
18. Four what-do-you-want screens: MOSTLY FIXED. #overview now lands on Make; Guided workflows is "Workflow builder" under Advanced.
19. Overview numbers unusable: FIXED by removal.
20. Maintainer evidence leaks: FIXED. Model, adapters with trigger, example; notes behind "Details for maintainers".
21. Taxonomy bleed: NOT FIXED. Krea oil/Nijisis still under Anime character; "Fast general picture, you describe it all"; no sort.
22. Goal defaults: NOT FIXED. "Wide fantasy scenery" defaults to portrait 832x1216; pixel icon 1024x1024, no pixel size.
23. Ctrl+K: PARTLY. Finds goals and look names (anime, restyle, watercolour); "wai", "krea", "noob", "lora", "tune" give "No match".
24. Recipe picker modal: NOT FIXED. Unchanged (recipe-picker.png).
25. Your pictures shows other sessions proofs: FIXED. Empty state text.
26. Mobile: MOSTLY FIXED. Header shows Make (not Create); 390 px layouts have no horizontal overflow. Create sticky bar not rechecked.
27. Full editor opens pre-filled: FIXED. Empty prompt.
Regressed: none found.

## 2. Clicks before Generate (then / now; Generate itself not counted)
- J1 Make look: 2 / 2 (look, type). Flagship (anime + chosen model + LoRA): 6 + 3 typed, in Full editor / 4 clicks (look, open Tune, model, Add) + 2 typed (scene, LoRA name), in Make.
- J2 tweak: new words 2 (re-seeds) / 1 (Edit and re-run keeps seed, model, LoRA) + typing; same seed: impossible / 1, same browser only; Library route unchanged (not re-measured).
- J3 restyle 4 + wording edit / 3 (goal, picture, look). J4 pose ~7 + 2 placeholder edits / 3 + 3-4 typed fields.
- J5 scene 3 / 2. J6 pixel icon 3 / 2. J7 product photo 3 / 2.
- J8 3D 4 / 2. J9 animate 4 / 2 + motion text. Change one thing: 2 clicks + text.
- J10 from Make runs 2 / 1; from Library >=5 / open asset 1 (picture visible, Continue first); Same recipe path not verified.
- J11 dead end after 2-3 / 3 (look, link, filtered page with source and path).
- J12 ~6, separate cards / compare toggle + 2-3 looks = 3-4, one side-by-side card.

## 3. New problems and remaining ones (ranked)
N1 HIGH (process, not UX). Live 8191 serves a checkout 119 commits behind origin/main, so the owner sees none of tonight work. Fix: git pull --ff-only in the primary checkout, then restart the Studio when no work is active (owner action; I did neither). S.

N2 MEDIUM-HIGH. make.js:163 puts #makeStatus at the top of the page, while Generate sits far below. Measured: after pressing Generate its status is at y=-871 (1440x900, Tune open) and y=-1177 (390x844). Progress and errors (including a refused submit) are invisible; on mobile the new run card is about 280 px below the button (y 1120 vs Generate 836), so a successful press would look like nothing happened, and Generate re-enables at once (finally block, make.js:279), inviting a double submit of a 10-17 min job. The mobile success path is inferred from geometry and code, not run (no submitting). Fix: put the status line inside .make-go, scroll the new card into view on narrow screens, keep Generate disabled until the job id returns. S.

N3 MEDIUM. Style strength multiplies the Tune per-adapter strengths without saying so. Krea target stack, Style strength 150%, Tune rows all show 1.00, payload lora 1.5, lora2 1.5, lora3 1.5; the run card "Tuned:" line omits it. make.js:98 (r.strength*scale) and :211. Fix: hide the slider when Tune lists adapters, or show effective values and include them in the summary. S.

N4 MEDIUM. With Tune open, Generate is at page y about 1513 (1440x900), out of view until about 800 px of scrolling. At 1100 px and wider the composer is one column (make.css:59, .make-composer grid-template-columns:1fr), so .make-go position:sticky (make.css:73) only sticks inside the short side block that sits below Tune. The flagship path is the one that loses the sticky bar. Seed lock is also split: Seed field in Tune, the "Different pictures each time" switch far below it near Generate. Fix: make .make-go a direct child of .make-composer. S.

N5 MEDIUM. "Add an installed adapter" is compatible by loader type, not base family (make.js:78 compatible()). A WAI/Illustrious look lists 21 adapters including Pony ("Gothic Neon", "Hands v1.0"), NoobAI and generic SDXL ones, with only a family label, no warning, no preview, no purpose text. Fix: two groups, "Made for WAI v17" and "Other SDXL families, may not suit"; show a one-line purpose. S.

N6 MEDIUM. Compare looks runs each look as made (make.js:546 comment: no tune). The flagship tweak loop (same look and seed, model A vs B, LoRA 0.4 vs 0.8) still means generate, eyeball, repeat. Fix: compare axis = model / steps / LoRA strength at one seed. M.

N7 MEDIUM. Tune is in memory (state.tune): a reload loses model, LoRA stack and steps (verified); only finished runs keep theirs. Fix: persist per look in localStorage next to studio.make. S.

N8 LOW-MEDIUM. In focused mode the goal chips are one non-wrapping row (make.css .make-focused .make-goals): "Animate a picture" and "Picture to 3D" are off the right edge behind a thin scrollbar at 1440 px. After a look click the focus scroll leaves "Describe your picture" under the sticky header. Fix: wrap chips, scroll-margin-top. S.

N9 LOW. Fix or upscale preselects an unavailable "Fix face" (make.js default state.fix = face) with Generate disabled; the reason text names "Continue with this". Fix: preselect the first available option; reword. S.

N10 LOW. Stale status ("Choose the pose first...") stays after the pose is chosen. S.

N11 LOW. Items 21, 22, 24 above; Tune shows two entries named "Anima" (different files); an added adapter trigger duplicates words already in the prompt ("masterpiece" x3 in the sent text); animate lengths are 0.7 s and 1.4 s. S each.

Server-side caveat: the per-recipe model field was present in my fresh Python; with the old process the Tune model list, labels and adapter filter would degrade. Not tested.

## 4. Verdict
See the final message. Screenshots, scripts (j*.py, lib2.py, run_server.py) and server.log are in this folder.

## Not verified
Real generation; Vary and Fix face on a recipe-made picture; Library Same recipe, new seed accept path; a real Install download; run-history-based estimates; Create mobile sticky bar; browsers other than Chromium; a double-press on Generate.
