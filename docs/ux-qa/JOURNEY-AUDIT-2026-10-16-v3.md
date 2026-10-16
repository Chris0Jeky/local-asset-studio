# Local Asset Studio UX re-audit v3 (live 127.0.0.1:8191, main d2973fa0, 16 Oct 2026)

Earlier audits: `JOURNEY-AUDIT-2026-10-16.md` (v1, 27 problems) and `JOURNEY-AUDIT-2026-10-16-v2.md` (v2, on the
`docs/overnight-review-backlog-20261016` branch at the time of writing). v1 and v2 audited a checkout 119 commits behind
origin/main (v2 section 0); this pass audits the live Studio itself, freshly restarted on main d2973fa0 (the same code
v2 saw in its sandbox, plus the later waves: #1459 durable submission saves, #1475 blind compare, #1474 character tests).

## 0. Method and safety
- Python Playwright, headless Chromium, 1440x900 and 390x844 (mobile emulation), fresh browser contexts. Scripts and
  screenshots stay in the worktree's ignored `.runtime/ux-audit3/` (not committed).
- Every POST except `/api/estimate`, `/api/looks/prepare` and `/api/recipe-check` was intercepted and answered by the test
  harness (never sent). Blocked attempts: 0. Posts that reached the Studio: estimate, recipe-check, one looks/prepare (Make
  "Open in the full editor instead"). No job, review, character, look, asset or collection was written; the GPU lab agent's
  work was untouched. Generate, Make the final, Resume, Stop tracking, Keep and Not this were never pressed.
- Pictures in picker and library screens were blurred in the browser before capture, so no thumbnail was judged.
- Simulated (browser-side only, never written): (a) one Make run card was restored by seeding this throwaway context's
  localStorage with the existing job 0e926110 so run-card actions could be read; its tune was set to the draft step count to
  show "Make the final"; (b) one asset was shown as Kept in the page's memory to reveal "Make this my character...".
- The workspace has no saved characters (`GET /api/characters` returns an empty list), so "Your characters" is not on screen
  and could only be read from code (make.js:486-493).

## 1. The 27 original problems

| # | v1 problem | v3 | Evidence |
| --- | --- | --- | --- |
| 1 | Make pictures vanish from default library | FIXED | Live library: "77 assets - 1426 agent runs hidden"; the first six Mine cards are "Make · ..." assets (WAI Auto Face Detail, WAI v17 illustration). workspace.js:23 exempts the "Make · " prefix. |
| 2 | No model or LoRA choice in Make | FIXED | Tune this look: base model, adapters with strength sliders, steps, sampler, negative, seed (section 4). Friction in N2. |
| 3 | Cannot tweak a result in place | PARTLY | Edit and re-run, Make the final, Same words another look work in Make, but only for the last 6 runs of this browser (make.js:44-45). Library route still the old handoff (N3). |
| 4 | Disabled buttons without a reason | FIXED | Fix or upscale preselects Upscale 2x and prints one reason line per unavailable fix; run cards show reasons. |
| 5 | Picture goals leave Make | PARTLY | Fixed inside Make: goal, picture, composer, Generate, no Create hop. The Library's "Continue with this" still opens the old 18-recipe "Where should it go next?" dialog (N3). |
| 6 | Restyle has no look chooser | FIXED | 22 look pictures plus "Describe the look in words instead". |
| 7 | Pose needs two slots | FIXED | Character / Pose slots, picture or drawn figure, three plain fields (no brackets). Only two figures exist (N11). |
| 8 | Helper outputs shown as pictures | PARTLY | Masks filtered, search exists. Titles are prompt excerpt plus date, so 16 consecutive cards read "pixel art inventory icon, ch..." (N5). |
| 9 | Asset dialog form-first | FIXED | Picture at y=72 (648 px tall), Continue with this first at y=65 of the dialog. Residual: seam and parallax forms sit above Vary and Same recipe. |
| 10 | Same recipe, new seed does nothing | FIXED | Live: native confirm, then Full editor opens with "New seed 1287957063 prepared as one output ... Generate remains a separate press." Not a no-op (v1 saw an auto-dismissed confirm). |
| 11 | Default 4 pictures on slow looks | FIXED | Slow looks start at 1 picture; estimate turns warning colour above 10 min (4 x Dark baroque = "About 42 min", no confirm). |
| 12 | Quality vs speed not a control | FIXED | Tune Steps (Draft half / Finer 1.5x), "Draft first" checkbox, "Make the final" on a draft run (simulated draft state). |
| 13 | Generate below the fold | PARTLY | Single look with Tune open: sticky Generate at y=803-857 of 900 (measured at 3 scroll positions). Not so in Compare looks (N4) and on a phone's first screen no look is visible (N10). |
| 14 | Missing-model dead end | FIXED (not live) | No look is blocked tonight (23 of 23 ready), so only the target was checked: `/#models?need=<recipe>` renders "Files needed for ..." filtered cards. Real Install button not verified. |
| 15 | Models as inventory | FIXED | Search on top filters looks and cards; "What you can make" with thumbnails; Used by and trigger on cards. Page 1,867 px, then 2,678 px once the looks panel renders (N8). |
| 16 | Compare cannot compare | FIXED for looks | Compare toggle, 3 looks selected, 4th refused ("Three looks at most"), button "Generate 3 pictures", one estimate. Tunes cannot be compared (N7). |
| 17 | Naming collisions | PARTLY | Full editor h1 is now "Full editor - every setting for one recipe". Still "CREATE / PILOT THE NEXT PASS", "recipe", orange accent, `#create`. |
| 18 | Four what-do-you-want screens | PARTLY | `#overview` lands on Make. `#home` still serves the old Overview ("Pick up the thread", seven tiles starting with Start with an idea) by URL. |
| 19 | Overview numbers unusable | FIXED | `#home` shows 77 saved assets and "1426 agent runs are not counted". |
| 20 | Maintainer evidence leaks | FIXED | What this look uses: model, adapters with trigger, example; notes folded under "Details for maintainers". |
| 21 | Taxonomy bleed | FIXED | Anime character = 7 anime looks; Krea oil and Nijisis under Painted illustration; "Quick picture, any subject"; each goal ordered fast first, slow last. |
| 22 | Goal defaults | PARTLY | Scene -> Landscape, Game -> Square, Character -> Portrait. No seamless/parallax/transparent option and no pixel size in Make (pixel look shows "As designed 1024x1024"). |
| 23 | Ctrl+K indexes tools only | PARTLY | Finds goals and looks; "lora" -> Tune a look, "seed" -> Full editor, "download" -> Models & setup, "compare" -> Compare & review. "xilmo", "pearly", model files and pictures: no result. |
| 24 | Recipe picker modal | PARTLY | Search is focused, first cards at y~390, thumbnails on some. Still 67 prose cards. |
| 25 | Your pictures shows other sessions' proofs | FIXED | Fresh browser shows the empty-state line. (The pickers still do, N1.) |
| 26 | Mobile | PARTLY | Header shows Make; no horizontal overflow on Make, Models, Library, Full editor; Models opens with the environment switcher folded. Full editor sticky bar still covers 208 px of 844 (25%). |
| 27 | Full editor opens pre-filled | FIXED | Prompt and negative empty. |

Totals: 17 fixed, 10 partly, 0 not fixed, 0 regressed.

## 2. v2 findings (N1-N11) rechecked
| v2 | v3 | Evidence |
| --- | --- | --- |
| N1 live app behind origin/main | FIXED | This audit's live app is main d2973fa0. |
| N2 status line far from Generate | FIXED by code, press not run | make.js:243-245 puts `#makeStatus` under Generate inside `.make-go`. A real press was not made. |
| N3 Style strength hidden multiplier | FIXED | Tune shows "All adapters x 100%" and "1.00 -> 0.55" style arrows; the plain slider hides while Tune is open. |
| N4 Generate far down with Tune open | FIXED | Generate y=803 with Tune open (was about 1513). `.make-go` is sticky (make.css:80). |
| N5 adapters compatible by loader only | FIXED | "8 made for Anima come first. 4 from other families ... may not suit it"; list labels say "made for this model" or "JANIMA v1 (Anima), may not suit". |
| N6 compare cannot vary model or LoRA | NOT FIXED | make.js:759-760: looks compared "as made (no tune)". Kept as N7 below. |
| N7 Tune lost on reload | FIXED | Reload kept "Tuned: model One Obsession Anima v2.0 - +xilmo style (Anima) 0.55" and the typed scene. |
| N8 goal chips off the edge | FIXED | All 11 chips wrap on two rows at 1440. |
| N9 Fix face preselected while unavailable | FIXED | Upscale 2x preselected; Fix face / hands disabled with a line each. |
| N10 stale "Choose the pose first" | NOT RE-CHECKED | Needs a press. |
| N11 duplicates, two "Anima" | FIXED | Anima files shown as "Anima - anima-aesthetic-v1.1" / "anima-base-v1.0"; trigger words are not repeated (make.js:137). Animate lengths 0.7 s / 1.4 s unchanged. |

## 3. New problems, ranked

**N1 HIGH. The picture pickers list the whole library, so the lab agent's output buries yours.** `loadPictures()` takes
every image from `/api/workspace` with no source filter (make.js:668), unlike the Library, which hides agent runs by default
(workspace.js:23). Live: 1,485 images, 1,414 carry an agent `run_label`, and all newest 60 (the only ones shown) are
"Lab 1016c ..." pixel icons, pose skeletons and tags. The user's own 71 pictures are reachable only by guessing a search
word. Same grid is the pose picker (make.js:709). Fix: filter with `assetIsAgentRun` (default "Mine"), add an
"Include agent runs" link. S.

**N2 HIGH (flagship). Add an installed adapter fails unless the exact filename was picked from the browser datalist.**
Typing "xilmo", "xilmo style (Anima)" or "Xilmo" then Add gives "Choose an adapter from the list: ... is not an installed
adapter"; Enter in the field does nothing (make.js:191, 226-228; `compatible(look).includes(name)`). Fix: accept a unique
case-insensitive match on label or file, wrap the field in a form so Enter adds, or show a clickable list. S.

**N3 MEDIUM-HIGH. The Library route to tweak an existing picture is still the old one.** "Continue with this ->" opens the
"Where should it go next?" dialog (Edit / Refine / Restyle / Combine / Animate / Make 3D tabs, an 18-recipe destination
list) and ends in the Full editor (studio-workbench.js:888, 925). "Same recipe, new seed" asks with a native `confirm()`
(asset-family.js:56, asset-family-adapter.js:82) and also lands in the Full editor. Make's goals (make.js:859) are only
reachable from a Make run card. Fix: put "Open in Make: change / restyle / pose / fix / animate" at the top of the asset
dialog calling the same `data-make-from` path; replace the confirm with an inline notice. M.

**N4 MEDIUM. Compare looks hides its own composer.** After choosing 2-3 looks the scene box and Generate are about 560 px
below the cards (Generate top 1,390 of 900 at scroll 0); `layout()` excludes compare (make.js:250) and the compare click
never calls `focusScene()` (make.js:836-841). The status says "type one scene" without a visible field. Fix: scroll and
focus the scene box on the second selection; fold the gallery to chips while composing. S.

**N5 MEDIUM. Picture cards cannot be told apart.** `pictureLabel` = prompt excerpt + date (make.js:583) cut to one line
(make.css:50 nowrap + ellipsis). Live: 16 consecutive "pixel art inventory icon, ch... 16/10/2026"; four "Hand-painted anime
film background, the interior of a narro..."; Make pictures are titled by the same prompt text. Fix: look or recipe name,
time and index; wrap to two lines; title attribute. S.

**N6 MEDIUM. "Your pictures" is per browser.** The shelf is rebuilt from `studio.make` in localStorage, last 6 runs
(make.js:44-45, 812-816). A new browser, profile or cleared storage shows the empty line although the library holds the
Make pictures (six, "Make · ..." labelled). Keep, Fix, Make this my character and Make the final are gone with it. Fix:
seed the shelf from library assets whose `run_label` starts "Make · " (already identified in workspace.js:23). M.

**N7 MEDIUM. Compare cannot compare models, LoRA strengths or steps** (v2 N6 unchanged). The flagship tweak loop (same
words and seed, model A vs B, LoRA 0.4 vs 0.8) is still generate, look, repeat (make.js:759-760). Fix: a compare axis
(model / strength / steps) at one seed. M.

**N8 LOW-MEDIUM. Models & setup: layout jump and an alarming first screen.** "What you can make" renders about 3.9 s after
load and pushes "Model files" down 811 px (1,867 -> 2,678 px; app.js:728, 756). The first cards are "Missing (6)" Qwen-Image 2.1
pin-only files that no look needs (23 of 23 ready), then "Needs a check (166)" with a Verify button each. Fix: reserve
the looks panel height, show it first, fold pin-only files under "Optional". S.

**N9 LOW-MEDIUM. Sidebar numerals read as counts.** Library shows "03", Full editor "02", Compare "04" (studio-shell.js:7, the
fifth array item). Fix: real icons or none. S.

**N10 LOW. Phone first screen is all goal tiles.** At 390x844 the first look card sits at y=789 (11 tiles, 5 rows,
make.css:52). Fix: fold the six picture goals under a "From a picture you have" disclosure on narrow screens. S.

**N11 LOW. Only two stick figures** (Standing, Bent forward looking back) plus Mirror (pose-editor-core.js:19); the text
sends joint editing to the Full editor. M.

**N12 LOW. Soft validation.** Generate stays enabled with nothing chosen (restyle without a look, combine without a
pose); the reason appears only after the press (make.js:315, 623-629). The Vary hint reads "Prepare variations in the full
editor; Generate there starts them." (make.js:428): Vary leaves Make. S.

**N13 LOW. Meaningless adapter label.** The pixel look says "built-in adapter at 1" (make.js:296; `short('')`). S.

**N14 LOW. Base-model list is not family-aware.** An AniFox/Illustrious look offers Pony V6 and NoobAI as models with only
a licence label, while adapters get a "may not suit" warning (make.js:93-98, 186). S.

**N15 LOW. The character form opens inside a 285 px picture cell** of the results grid (make.css .make-actions), cramped
beside the next picture's buttons; "Your characters" is invisible until a character exists, so "Make this my character..."
(shown only after Keep, make.js:455) is the only way in. S.

## 4. Flagship journey now: "very high-end anime image, specific model + LoRAs, then tweak it"
First load at `/#make` on 1440x900, Anime character goal preselected (default Generate not pressed):

| Step | v1 (Full editor) | v2 (Make, sandbox) | v3 (Make, live) |
| --- | --- | --- | --- |
| Pick look | Full editor, Change recipe, search, card (3) | 1 | 1 (Flat pastel close-up; Generate sticky at y=803) |
| Describe | type | type | type scene |
| Open Tune | Fine-tune the recipe (1) | 1 | 1 (summary line; folded by default) |
| Switch model in family | slot dropdown | 1 | 1 (select; 2 alternates for this look, 4-6 for SDXL looks) |
| Add a LoRA | hand-type name | 1 click + type name | type "anima-xilmo-000020.safetensors" + pick from datalist + Add = 2 clicks + 1 typed (N2 for partial names) |
| Strength | strength box | not counted | 1 (slider; arrow keys; default 0.70 for the added adapter) |
| Draft first (optional) | no such thing | not counted | 1 checkbox, then "Make the final" on the draft card |
| Total before Generate | 6 clicks + 3 typed | 4 clicks + 2 typed | 6 clicks + 2 typed (5 + 1 when the typed name is exact); Generate always in view |

Like for like with v2 (which did not count strength or the datalist pick): 4 -> 4 clicks, plus the 2 things v2 left out.
Nothing is lost on reload: Tune and scene both came back after a page refresh. Confusion points: (1) a partial adapter name
fails (N2); (2) "No trigger word" under a style LoRA gives no hint of what it does; (3) the base-model list includes
other dialects without a warning (N14); (4) after Generate the picture lands beside the form on desktop, but this was not run.

Tweak paths after a picture exists (existing pictures only):
- Keep / Not this: one press each on a run card; "Make this my character..." appears after Keep and opens a three-field form
  (prefilled "who" from the words). View only; not saved.
- Draft first -> Make the final: checkbox in the composer, then "Make the final" on the draft card restores words and seed at the
  full step count and focuses Generate (simulated draft state; 1 click + Generate).
- Fix or upscale: 2 clicks (goal, picture); Upscale preselected; faces and hands refuse non-anime pictures with a reason.
- Restyle: 3 clicks (goal, picture, look picture) + optional colours; the shared gallery shows all 22 looks.
- Character in a new pose: goal, picture, "Draw the pose", figure = 4 clicks + 3 typed fields (who, clothes, pose words prefilled
  from the figure name); only two figures.
- Change a picture, Animate, Picture to 3D: 2 clicks + 1 text (3D none). Estimate shown (animate: "About 9 min").
- Compare looks: toggle + 2-3 looks = 3-4 clicks, then scroll to the scene box (N4).
- Ctrl+K: opens in one chord; "anima", "krea", "wai", "pixel" find looks; "lora" finds "Tune a look"; model files do not.
- Library: Mine is the default and includes Make pictures; picture at the top of the dialog; Continue with this is the old
  dialog (N3). Full editor: empty prompt, h1 "Full editor - every setting for one recipe", orange accent still.

## 5. Not verified
Real generation and its status line; Keep / Not this saving; saved characters, Your characters list, character edit,
line-up (no character exists); Make the final on a real draft run; a blocked look and a real Install download; Library
Keepers scope with kept Make pictures; run-history estimates beyond the numbers shown; browsers other than Chromium; a
double press on Generate; screen readers.
