# 01 · Product brief

Written 27 September 2026 from the code on `main` at `8a41edaa`, the live Studio on port 8191 (browsed read-only) and the
owner's recorded feedback. Anything marked **Proposal** is a design recommendation, not shipped behaviour or an owner decision.

## What it is

**Local Asset Studio** is a private, single-user creative workbench that runs entirely on one Windows PC. A small Python
server (port 8191, loopback only) serves a plain HTML/JS/CSS interface over a locally installed **ComfyUI** (the image,
video and 3D generation engine, port 8188). The Studio turns ComfyUI's node graphs into named **recipes** with human
controls, keeps every output in a local **asset library**, and hands finished pictures to native tools (Krita, Godot,
Blender).

| Fact | Value (source) |
| --- | --- |
| User | One person, the owner. No accounts, no sharing, no other consumers |
| Machine | Windows 11, AMD Radeon RX 9070 XT, 16 GB VRAM; host RAM pressure matters (heavy jobs refused above ~55 % commit) |
| Main use | Anime and fantasy illustration: original characters, restyles, pose transfers, combines; game assets (sprites, props) |
| Also | Short video (Wan 2.2, currently unreliable), 3D drafts (TRELLIS, Hunyuan3D), voice takes, scene assembly |
| Catalog | 89 presets (79 image, 6 video, 4 3D), 45 marked verified; 67 authored recipes (`presets/catalog.json`, `presets/recipes.json`) |
| Library today | 1,201 assets, 1,188 awaiting review, **0 keepers** (live Overview, 27 Sep 2026); most are agent-lab outputs |
| Job length | 16 s (FLUX.2 Klein restyle, warm) to 14+ minutes (Qwen edit, Krea 2 at full size); first model load is slower |

## Who and what they are trying to do

The owner is a technically fluent hobbyist making original anime/fantasy characters and game assets. They do not want
to learn ComfyUI graphs to get a result; they do want control when a result is close but wrong. Their words
(14 Sep 2026, `docs/UX-AUDIT-2026-09-14.md`): the Studio is "pretty much unusable"; Create is "not very helpful and
snappy"; guides are "very wordy"; *Plan a comparison* is "all over the place"; the library needs "an organisation
engine"; Prompt Lab's locked buttons "never say what is missing". On Combine (15 Sep, #422): they want something that
"lets you experiment easily, is intuitive, fault tolerant and adaptable" and "gives you all the right UI components,
information, examples, the important parts very clear and readable and accessible".

### Jobs to be done (ranked by observed use)

| # | When I... | I want to... | So that... |
| --- | --- | --- | --- |
| 1 | have an idea in words | pick a look and generate a small batch | I can see whether the idea works |
| 2 | have a picture I like but one thing is wrong | change that one thing and keep the rest | I don't lose the character |
| 3 | have a character and a pose/style picture | combine them (character in that pose / in that look) | I get the image in my head without drawing it |
| 4 | have dozens of new outputs | review fast with the keyboard, keep winners, tag why the rest failed | the library holds decisions, not noise |
| 5 | am unsure which setting matters | compare a few candidates changing one thing | I learn what works on this machine |
| 6 | have a keeper | reuse it: as reference, variation, animation, 3D, sprite export | one idea flows through the pipeline |
| 7 | a run failed or its outcome is unknown | see plainly what happened and what I can safely do | I never lose evidence or double-run a 10-minute job |
| 8 | need a model or a different engine | see what is missing and switch deliberately | recipes just work |
| 9 | want to go deeper | inspect or reshape the underlying workflow | I can learn ComfyUI only when useful |

## Principles (binding on every design)

1. **The work is the hero.** The picture being made and the brief dominate; chrome, art and explanation recede.
2. **One next action.** Each screen says what happened, what remains and the single next step. Explanations are one
   disclosure away, never a standing essay (the heaviest screens today show 400-600 words of instruction).
3. **Nothing runs by itself.** Opening a page, choosing a recipe, switching a task or a skin never submits a job,
   installs a model or switches an engine. Generate/Start is always a separate, explicit press.
4. **Truthful state.** Queued, running, completed, failed, **uncertain** and put away look different. Unknown is never
   shown as zero or green. An uncertain job is never offered as "Retry".
5. **Disabled means explained.** Every disabled control carries a visible, adjacent reason and a way to fix it
   (not hover-only).
6. **Three separate truths.** *Executed* (a job completed), *accepted* (the owner judged the art) and *licensed* (the
   model terms allow the use) are never merged into one badge or "approved" star.
7. **Keyboard-first review.** Deciding on outputs is a keyboard flow; the mouse is optional.
8. **Local by design.** Works fully offline; no web fonts, CDN, remote analytics or remote media by default.
9. **Calm under long jobs.** A 10-minute job needs honest progress and a place to wait, not spinners and ambient motion.
10. **One vocabulary.** One name per concept across every page (today: "Workspace", "Asset library" and "Your
    experiments" name the same thing).

## What "great" looks like (acceptance for the redesign)

| Measure | Today (measured or observed) | Target (Proposal) |
| --- | --- | --- |
| Clicks to a first Generate from the landing page | 2 (fixture) with ~450 words on screen | ≤ 2 with ≤ 120 words visible |
| Peak instruction words on one screen | 604 (workflow builder), 483 (3-reference Create) | ≤ 150 by default; rest behind "Why?" |
| Disabled controls without an adjacent reason | ≥ 25 found in code (see 05) | 0 |
| Page shells / colour palettes | 3 shells, 6 palettes (style, studio, review, spoken-briefs, workflow-studio CSS, Prompt Lab inline) | 1 shell, 1 token set, skins as token overrides |
| Review 20 outputs | dialog per asset, keyboard only inside the asset dialog | grid-level keyboard review, ≤ 1 key per decision |
| Generate reachable at 1440×900 and 390×844 | yes, but the fixed dock hides half the mobile screen | always reachable, never covering the input being edited |
| Owner verdict | "pretty much unusable" | the owner's next first-hand pass (HUMAN_TODO q-7) says it feels right |

## Non-goals

- Not a cloud product, not multi-user, no accounts, no sharing, no marketplace.
- Not a replacement for ComfyUI's node editor, Krita's painting or Blender's modelling; the Studio links out to them.
- No fake capability: no brush/mask UI without a real mask route, no "quality" slider shared across model families,
  no decorative progress, no invented VRAM readouts in art.
- No automatic generation, retry, model install or engine switch, ever.
- No change to the backend contracts to make a design easier (Python server, job store and APIs stay as they are).
- No judging or displaying of adult content in design references; designs use neutral placeholder art.
