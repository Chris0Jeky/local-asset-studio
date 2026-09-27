# 09 · Ready-to-paste prompts for Claude Design

How to use: paste **Project context** once at the start of the Claude Design project (or attach `01`, `06`, `07` as
files). Then paste one prompt per session, in order, attaching the screenshots named under each prompt. Every prompt
also restates the rules that matter for it, so it still works on its own.

---

## Project context (paste once)

```text
You are designing the frontend of Local Asset Studio, a private single-user creative workbench that runs entirely on
one Windows PC (AMD RX 9070 XT, 16 GB VRAM). A local Python server on 127.0.0.1:8191 serves plain HTML/CSS/JS over a
locally installed ComfyUI. The owner makes original anime/fantasy illustrations and game assets: generate from a
brief, edit one thing in a picture, combine a character with another picture's pose, restyle, compare settings,
review outputs, reuse keepers, export sprites to Krita/Godot/Blender. Jobs take 16 seconds to 14+ minutes.

The owner called the current UI "pretty much unusable": too wordy, advisory guides, unclear comparisons, a library of
1,201 assets with 1,188 unreviewed and 0 keepers, locked buttons that never say why.

Hard rules for every design:
1. Nothing runs by itself: opening, choosing a recipe, switching task/skin/layout never generates, installs or
   switches engines. Generate/Start is always a separate explicit press.
2. Truthful job states: queued, waiting, submitting, running, completed, partial, failed, UNCERTAIN (sent but outcome
   not seen; never offer Retry), not submitted, abandoned; plus "tracking stopped" and "put away" (hidden, reversible).
3. Every disabled control shows an adjacent visible reason and, where possible, a fix. No hover-only explanations.
4. Executed, accepted (owner likes the art) and licensed (model terms allow the use) are three separate facts; never
   a single "approved" badge or star.
5. Keyboard-first review; every flow completable without a mouse; letter shortcuts never fire while typing.
6. Offline: no web fonts, CDN, remote icons or images. System font stack (Segoe UI Variable/Segoe UI, system-ui;
   Cascadia Code/Consolas for mono). Inline SVG icons.
7. Buildable as static HTML/CSS/JS; later Vue 3 islands compiled ahead of time. Express the design system as CSS
   custom properties so legacy plain-JS pages can use it.
8. WCAG 2.2 AA, visible focus, status by icon + text + shape, reduced motion honoured, forced colours supported,
   works at 1440x900 (reference) and 390x844.
9. Dark, calm, professional creative-tool feel; the output image is the brightest thing on screen. Optional "skins"
   (Atelier default, Arcade, Sakura, Retro Anime, Minimal Pro, Sci-Fi Noir) are token overrides over one component
   system, plus an optional decorative environment slot that is text-free and never clickable.
10. Short plain copy: what happened, what remains, next action. Details one click away. One vocabulary:
    Home, Make, Library, Runs, Setup; Recipe; Environment; Keeper / Needs work / Rejected / Unreviewed; Put away.
11. Use neutral original placeholder art (props, landscapes, abstract studies). No franchise characters, no real
    people, nothing suggestive.
```

---

## D0 · Design system foundations

Attach: `10-create-focus.jpg`, `17a`-`17f` skin shots, `01-overview.jpg`.

```text
Create the design system foundations for Local Asset Studio (see project context).

Deliver:
- Token sheet as CSS custom properties: surfaces (bg, surface-1..3, overlay, line, line-strong), text (text, muted,
  faint, on-accent), accent set (accent, hover, subtle, focus-ring), fixed semantic status colours (running,
  success, warning, error, unknown, neutral, muted/put-away) and review colours (keeper, needs-work, rejected,
  unreviewed), type scale 12/13/14/16/20/24/32 with weights 400/600, 4-px spacing scale, radii 4/8/12/999,
  elevation 0-3 plus a "dock" level, motion (fast 120-180 ms, panel 160-220 ms, scene <= 300 ms, all ~0 under
  reduced motion), density modes comfortable and compact.
- The Atelier skin as default (charcoal, cream, walnut, amber) and two overrides: Retro Anime "Night Shift"
  (graphite, desaturated rose/cyan, small amber) and Minimal Pro (graphite, ivory, cool daylight). Show that a skin
  changes at most 12 tokens and never the status colours.
- A component sheet: status chip for every job state (icon + text + shape, readable in monochrome), buttons
  (primary, secondary, ghost, danger) including a DISABLED-WITH-REASON pattern (reason text directly under or beside
  the button, linked for screen readers, with an optional fix link), text input, textarea, select, chip, card,
  disclosure ("Why?"), dialog, notice (info/success/warning/error), empty state (one line + one action),
  keyboard hint (kbd).
- A contrast table for text/muted/accent/status on each surface in all three skins (AA).
Today's UI uses 6 unrelated palettes (screenshots attached); replace them with this one system.
```

## D1 · App shell and navigation

Attach: `01-overview.jpg`, `02-command-finder.jpg`, `70`-`72` mobile shots, `62-spoken-briefs.jpg`, `42-guided-workflows.jpg`.

```text
Design the app shell for Local Asset Studio (see project context), using the D0 tokens.

Today there are 7 overlapping navigation systems and 3 page shells; labels drift ("Workspace" = "Asset library" =
"Your experiments"; "Experiments" = "Runs & review"). Replace them with one shell:
- Sidebar: Home, Make, Library, Runs, Setup, plus Prompt Lab under a small "Tools" group; collapsed (icons) and
  mobile drawer states; a small "Local by design" footer is optional.
- Top bar: breadcrumb; Environment chip (e.g. "Main library"); health pill with 8 states: Connecting, Checking
  ComfyUI, Readiness unavailable, Studio worker unavailable, ComfyUI offline, Checking node readiness, Recipe needs
  models, ComfyUI connected; a "GPU reserved by <holder> · 12 min" chip when held; a running-jobs indicator
  ("2 running · 1 unknown outcome") that opens Runs filtered.
- Command palette (Ctrl K): tools, recipes, assets, runs and actions ("Review unreviewed", "Open last result"),
  with keyboard navigation and an empty result.
- A "?" keyboard shortcut sheet.
Frames: 1440x900 desktop (expanded and collapsed sidebar), 390x844 closed and open drawer, palette open with results.
Show how an unreachable Studio API and an offline ComfyUI look in the shell without blocking the page.
```

## D2 · Make workspace (the Create screen)

Attach: `10-create-focus.jpg`, `11-create-focus-full.jpg`, `14-create-source-required.jpg`, `16-create-problems.jpg`, `16b-create-recent-runs.jpg`, `17e-create-immersive-retro-night-shift.jpg`, `72-mobile-create.jpg`, `81-live-create.jpg`.

```text
Design the Make workspace of Local Asset Studio (see project context), in the D1 shell with D0 tokens.

Purpose: turn a brief (and 0-3 source pictures) into a generation with an explicit Generate, then show the result in
place. Today the page is a long form rearranged by four scripts, the fixed run bar covers the prompt, the full
blocker list is hidden in a collapsed section, and results sit in a collapsed "Recent runs" list below.

Layout (1440x900 must show all of this without scrolling for a 1-reference recipe):
- Task lens chips: Create, Edit, Combine, Restyle, Pose, Animate, 3D. Selecting a lens filters recipes; it never
  changes the current recipe by itself.
- Recipe chip: name, family, "about 42 s on this PC" (or "no timing yet"), readiness; "Change" opens the picker (D6).
- Brief: large auto-growing textarea; "Avoid" as a sibling field when the recipe supports it.
- Sources board: numbered slots (0-3) with thumbnails, role labels (fixed by recipe or selectable), states: empty
  required, empty optional, attached, staged, unsupported extra ("This recipe reads 1 picture; picture 2 won't be
  used"); Pull from library; paste to attach.
- Parameters: one summary line ("768x1152 · 30 steps · seed 2026091103 · 0 adapters") that expands to controls and
  LoRA slots (strength, trigger word) with "Reset to recipe".
- Run dock: Generate (Ctrl+Enter), variations 1-4, New seed, Compare; estimate; when blocked, the first blocker plus
  "+2 more" and a fix button. It must never cover the field in focus; on 390x844 it collapses to one row.
- Results strip directly under the brief: this draft's runs as tiles (seed, time taken, Keep / Needs work /
  Rejected, Continue with this, Same seed / New seed), including running (elapsed + estimate + step if known),
  failed (diagnosis + suggested fix) and unknown outcome (retained receipt, "Check again", never Retry).
- Draft status: "Draft saved in this browser · 04:12"; "Another tab changed this draft" conflict.
States to draw: no recipe; blocked (missing reference, missing model with "Open Setup", other environment);
ready; submitting; running; completed with 4 seeds; failed; unknown outcome. Also 390x844.
Explanations go behind "Why?"; no more than ~120 words of instruction visible by default.
```

## D3 · Library and Review mode

Attach: `20-library.jpg`, `21-library-bulk-selection.jpg`, `22-asset-dialog.jpg`, `23-review-queue.jpg`, `80-live-overview.jpg`.

```text
Design the Library and its keyboard Review mode for Local Asset Studio (see project context).

Reality: 1,201 assets, 1,188 unreviewed, 0 keepers; most are agent-lab outputs titled "<recipe> · 1". Review today
happens one asset at a time inside a modal. Asset fields: title, prompt excerpt, recipe, seed, created, media type
(image/video/3D/audio), review (unreviewed/keeper/needs work/rejected), favourite, tags, notes, run label (agent vs
mine), collections, lineage, same-run siblings.

Deliver:
1. Library grid (compact and comfortable density): filters Source (Mine / Agent runs / All), type, sort, group by
   recipe/day/run with group headers and counts; sidebar views (All, Unreviewed, Keepers, Needs work, Favourites,
   Trash) and collections; selection with a grouped bulk bar (Decide · Organise · Export · Danger) instead of 17
   equal buttons; 11 empty states (e.g. no keepers yet, trash empty, no matching assets vs "couldn't load").
2. Asset side panel (grid stays visible): decision, reason chips (hands, face, style off, composition, anatomy,
   artifacts, crop), title, tags, notes, Continue with this verbs, lineage; unconfirmed-save and "changed elsewhere"
   conflict states.
3. Review mode: large preview + filmstrip; keys K keeper, W needs work, X rejected, S skip, left/right, 1-7 reason
   chips, Z undo, F favourite, Space 100% zoom; each decision shows saving -> saved (queue advances only after a
   confirmed save) or failed with retry; "Review this group" from a group header; progress "37 of 120".
Frames: grid 1440x900 with 60+ tiles; bulk selection; side panel; review mode; review mode at 390x844.
Decisions are the owner's selection, not art or licence approval; never auto-classify.
```

## D4 · Runs timeline (jobs + plans)

Attach: `16-create-problems.jpg`, `16b-create-recent-runs.jpg`, `30-runs-and-review.jpg`, `01-overview.jpg`.

```text
Design Runs for Local Asset Studio (see project context): one place for every generation job and every plan.

Today, jobs live in Create (collapsed "Problems" and "Recent runs"), plans live in "Runs & review", and the Overview
"desk" repeats stale items with no action. Old problems never leave.

Deliver a timeline/list grouped: Running · Needs your decision · Needs attention · Done · Put away (count).
Job statuses and their only allowed actions:
- queued / waiting / submitting / running: Inspect (show elapsed, estimate, step if known; no Cancel exists yet).
- completed: open outputs, Keep/Needs work/Rejected, Continue, Recipe.
- partial: Resume observation, Put away.
- failed: plain diagnosis (e.g. "Memory allocation failed - try a smaller size or fewer adapters"), Open as new
  draft, Recipe, Put away.
- uncertain ("Sent, outcome not seen"): Check again (read only), Stop watching (reason required), then Put away.
  Never Retry. Its own visual language, neither error nor success.
- not submitted: Abandon (reason), Open as draft. abandoned: Put away / Bring back.
- mixed batch: Check known receipts / Abandon the rest locally.
Plans (comparison, scene, voice, native export, 3D prop) with 15 statuses grouped into Ready to start, In progress,
Needs your decision, Needs attention, Done; show budget ("2 of 4 runs reserved") and time allowance; actions Start,
Stop after current stage, Extend time, Branch, Open compare board.
Detail panel: what happened, what is safe, one primary action; raw prompt IDs and engine errors behind "Details".
Frames: 1440x900 list + detail for a running job, an uncertain job, a failed job, a plan awaiting review; filters.
```

## D5 · Compare board (plans + blind review desk)

Attach: `30-runs-and-review.jpg`, `31-plan-comparison-dialog.jpg`, `34-review-desk.jpg`, `35-review-desk-no-project.jpg`.

```text
Design the Compare flow for Local Asset Studio (see project context): plan a bounded comparison, run it explicitly,
then decide blind.

1. Plan wizard: "Change one setting" (seed, adapter strength, guidance, steps, denoise) and values; the summary at
   the top ("3 candidates · 3 runs · about 2 min"); name; time allowance; Advanced: several settings. Prepare and
   Start are separate. The primary action must stay in view at 1440x900 (today it falls off the dialog).
2. Compare board: 2-4 candidates as equal columns (no visual ranking), blind by default (A/B/C/D, settings hidden),
   synced zoom and crop presets (whole, centre detail, upper half, custom), swap, background dark/light for alpha.
   Per candidate: verdict Keep / Needs work / Reject, 5 checks (pass/fail/not assessed), preference 1-5, cleanup
   seconds, notes. Keyboard: left/right focus, K/W/X verdict, 1-5 preference, B toggle blind, R reveal.
3. Decision: a pre-flight checklist ("Every candidate needs a verdict", "Only a kept candidate can be selected") that
   explains why Record decision is disabled; Reveal settings as the last, irreversible step with a styled
   confirmation; export evidence pack.
Frames: wizard; board blind; board revealed; decision recorded; board at 390x844 (stacked, swipe between candidates).
```

## D6 · Recipe picker with thumbnails

Attach: `12-create-recipe-picker.jpg`, `01-overview.jpg`.

```text
Design the recipe picker for Local Asset Studio (see project context). 89 presets / 67 authored recipes across
image (79), video (6) and 3D (4); families include FLUX.2 Klein, Qwen Image Edit, Krea 2, Anima, WAI/Illustrious,
Pony, NoobAI, Z-Image, Wan 2.2, TRELLIS, Hunyuan3D.

Today one dialog offers five competing ways to choose (task select, bundles banner, search + filters, "Help me
choose", text list) with paragraph descriptions and no thumbnails.

Deliver one picker: task lens filter (Create, Edit, Combine, Restyle, Pose, Animate, 3D) + search + family/modality
filters; recipe cards with an example thumbnail (and a no-thumbnail variant), input shape icons (words, 1-3 pictures,
pose skeleton), "about N s on this PC" or "no timing yet", readiness (ready / needs files / needs another
environment, each with its reason), verified mark, a one-line licence note where relevant ("non-commercial",
"excludes UK use"). Selecting a recipe when a draft exists shows a difference review: keeps your brief / replaces
settings / drops picture 2 / needs a pose picture; Cancel restores draft and focus. Keyboard: "/" search, arrows,
Enter choose, Esc close. Frames: grid, filtered, empty result, difference review, 390x844.
```

## D7 · Combine and pose

Attach: `14-create-source-required.jpg`, `15-create-source-picker.jpg`, `24-continue-with-this.jpg`.

```text
Design the Combine lens of Make for Local Asset Studio (see project context). Goal: put this character into another
picture's pose (or replace a character), and experiment quickly across engines.

Show two source tiles side by side (Character · Pose picture), with swap and replace; three short named fields
("Who is in picture 1", "The pose in a few words", "Clothes and colours") remembered per character; engine chips
(Copy Pose, Drawn skeleton, Depth map, Replace character, Pose-first 9B, Klein 4B), each with measured time or
"no timing yet" and a reason when it can't take the current sources; an optional "Draw the pose" panel (18 joints,
drag, select a joint and nudge with arrows, mark unknown, start from a standing figure or mirror, undo/redo, "Use
this pose"); a results-per-pair strip: each run's seeds next to both sources with Keep / Needs work / Same seed /
New seed; failed and unknown runs for this pair folded under "Problems (2)".
1440x900: sources, fields, engine chips, Generate and the latest results visible together. Also 390x844.
```

## D8 · Continue with this and lineage

Attach: `24-continue-with-this.jpg`, `16b-create-recent-runs.jpg`, `22-asset-dialog.jpg`.

```text
Design "Continue with this" for Local Asset Studio (see project context): every output tile and asset panel offers
verbs Edit, Refine, Restyle, Combine, Animate, Make 3D, Split figures, Upscale. Choosing one opens Make in that lens
with the picture on the board, a suggested destination recipe (changeable), prepared wording, and a lineage chip
("from Lantern study · seed 42"). Disabled verbs say why ("needs a mask route", "3D needs an image with a plain
background"). Nothing runs until Generate. Show: menu on a tile, menu in the asset panel, the prepared Make state,
lineage on the new asset.
```

## D9 · Empty, error and recovery states

Attach: `35-review-desk-no-project.jpg`, `16-create-problems.jpg`, `50-prompt-lab.jpg`.

```text
Design the complete set of system states for Local Asset Studio (see project context), each as a compact component
with one line "what happened", one line "what is safe", one action, and raw detail behind "Details":
Studio API unreachable; ComfyUI offline; Studio worker unavailable; readiness unknown / needs a fresh check;
environment switching; GPU reserved by another holder; missing model files (list, sizes, Download); failed job;
unknown outcome (retained receipt, Check again, never Retry); unconfirmed save (Check status before Retry exact
request; newer typing is not sent); "changed elsewhere" conflict (your draft / saved elsewhere / value when
opened); browser storage denied; filtered empty vs genuinely empty vs couldn't load; optional decorative media
failed (silent fallback). Show them in context: Make, Library, Runs, the shell. Include monochrome versions.
```

## D10 · Setup: models and environments

Attach: `40-models-and-setup.jpg`, `82-live-models.jpg`.

```text
Design Setup > Models & environments for Local Asset Studio (see project context). Environments: Main library
(8188), HiDream O1 isolated (8192), MiniMax H3 (8194), Qwen-Image 2.1 isolated (8196); one active at a time; Switch
is explicit and refused with a reason while work is running. Show environment cards (purpose, which recipes need
it, status, Switch); disk free with a reserved margin; curated model files (present - verify, missing, downloading
with progress, verified SHA-256, copy by hand), long paths truncated with copy; folders with "Open in Explorer";
installed weights search. Show reaching this page from a Make blocker and returning without losing the draft.
```

## D11 · Prompt help panel

Attach: `50-prompt-lab.jpg`.

```text
Design a "Help me write this" panel inside Make for Local Asset Studio (see project context). It compiles facets
(subject, style, keep, avoid, approved tags, motion) against the current recipe's prompt profile as you type, shows
exactly what the model will receive (positive / negative), and lists diagnostics as sentences with one-click fixes
("This recipe reads no negative prompt - keep 'blurry' as a review note"). Apply writes into the brief with a
visible diff and Undo. Saved briefs and picture analysis stay on a separate full page; show its slimmed layout too
(today it is 2,900 px tall and the brief starts 1,100 px down).
```

## D12 · Export wizard

Attach: `33-native-export-dialog.jpg`, `21-library-bulk-selection.jpg`.

```text
Design the export wizard for Local Asset Studio (see project context), started from a Library selection or
collection: format cards (Sprite atlas + timing, Layered artwork for Krita (ORA), Godot sprite project); frame strip
with drag and keyboard reorder, per-frame duration and layer name; anchors, filtering (nearest/linear), loop;
optional "Verify in local Godot/Krita"; canvas requirement check ("all frames must share a canvas") before Prepare;
Prepare and Start as separate actions; result view with files, measurements and verification outcome.
```

## D13 · Guided coach and assistance levels

Attach: `44-guided-path-active.jpg`, `42-guided-workflows.jpg`.

```text
Design guided help for Local Asset Studio (see project context). Replace the current coach panel that pushes the
workspace down with an anchored coach mark beside the target control: "Step 2 of 6 · Add a pose picture", one
sentence of why, observed evidence ("Recipe selected"), Next / Back / Pause, and a small step list. Guides never
generate or approve anything. Add an assistance setting (Guided, Studio, Expert) that changes how much explanation
shows, never what the user may do. Max ~40 words per step.
```

## D14 · Skins and environment pass

Attach: `17a`-`17f` skin shots, `13-create-appearance-menu.jpg`.

```text
Apply the D0 system to Make, Library and Runs in all six skins of Local Asset Studio (see project context): Atelier,
Arcade, Sakura, Retro Anime (Night Shift + Quiet Morning), Minimal Pro, Sci-Fi Noir. Add the optional environment
slot (shallow header or side wall) in Still and Subtle modes with placeholder rectangles where art will go; show the
Appearance popover (layout, skin, environment, Hide environment) and the rules: environment pauses during any
running or unknown job, reduced motion, hidden tab; art is never behind text, never clickable, never shows status.
Include a contrast check per skin.
```

## D15 · Workflow builder (expert)

Attach: `43-workflow-builder.jpg`, `42-guided-workflows.jpg`.

```text
Redesign the expert workflow builder of Local Asset Studio (see project context): node catalog with search, canvas
with pan / zoom / fit / minimap, node inspector wide enough for long prompt fields with an "Expand" editor, Steps
view as an alternative to Nodes, and one primary action per state: Check connections -> Save to Library -> Prepare
run ticket -> Run (explicit confirmation). Today there are ~30 buttons, most disabled with no reason; every disabled
step must name its precondition ("Save this workflow first").
```

## D16 · Scene, voice and Spoken Briefs in the shell

Attach: `60-scene-editor.jpg`, `61-voice-takes.jpg`, `62-spoken-briefs.jpg`.

```text
Bring the Scene editor, Voice takes and Spoken Briefs pages of Local Asset Studio (see project context) into the D1
shell with D0 tokens. No new features: restyle the scene list/timeline, the voice take form and saved takes (with
Generate CPU take, Cancel, audio player), and the Spoken Briefs archive player (chapters, transcript evidence table,
listening review). Keep their disabled reasons visible.
```
