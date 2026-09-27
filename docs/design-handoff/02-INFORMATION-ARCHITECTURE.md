# 02 · Information architecture

## Current sitemap (code truth, `main` 8a41edaa)

One Python server serves every page from `app/static/`. `index.html` is a single-page app with hash views; the other
pages are separate HTML files. `studio-shell.js` injects the shared sidebar and top bar into most pages and **deletes**
each page's own hand-written top bar.

| URL | Nav label (sidebar) | Other labels for the same place | Shell | Purpose |
| --- | --- | --- | --- | --- |
| `/#home` (default) | 01 Overview | — | shared | Stats, 7 task cards, "On your desk", recent assets |
| `/workflow-studio.html` | Guided workflows | Workflow Studio, "Workflow builder", "Headless & agents" | shared nav, **own CSS palette** | 7 guided paths, node-graph builder, run ticket, saved runs |
| `/#create` | 02 Create | "Generate" (Create sub-nav), "Follow the idea." | shared | Recipe, brief, sources, parameters, run dock, problems, recent runs |
| `/#assets` | 03 Asset library | "Workspace" (old nav, API, docs), "Your experiments" (sidebar heading), "YOUR CREATIVE LIBRARY" | shared | Grid, filters, collections, review queue, bulk actions, asset dialog |
| `/#production` | 04 Runs & review | "Experiments" (old nav, Review desk copy), "EXPERIMENTS & FINISHING" | shared | Plans: comparisons, scenes, voice, native exports, articulated props |
| `/review.html?project=<id>` | (none; reached from a plan) | "Review desk", "COMPARE" | shared | Blind side-by-side review, crops, assessment, decision, evidence export |
| `/prompt-lab.html` | Prompt Lab | — | shared nav, **own inline palette** | Brief → model-specific prompt; saved briefs; reference analysis |
| `/av.html?project=&asset_ids=` | Scene editor | "LOCAL SCENE EDITOR" | shared | Timeline of PNG/MP4/WAV sources, render |
| `/voice.html` | Voice takes | "Voice baseline" (old nav) | shared | CPU TTS take: prepare, generate, listen |
| `/spoken-briefs.html` | (not in sidebar) | "Spoken Briefs" | **own header, own palette, no Ctrl K** | Listen to narration archives, record listening review |
| `/#models` | Models & setup | "Models & folders" (old nav), "KNOW YOUR TOOLKIT" | shared | Model environment switch, disk, curated downloads, folders, inventory |
| `/#learn` | Workflow guide | "Workflow lab" (old nav, old tab title) | shared | Static explainer: fundamentals, experiment method, inspect a workflow JSON, 3D example |
| `/nsfw-lab.html` | (unlinked) | — | none | Local lab notes page; reachable only by typing its URL |

Query entries: `?guide=<id>&step=` (starts a guided path over Create), `?recipe_goal=` (opens the recipe picker with a
shortlist), `review.html?project=`, `av.html?asset_ids=`.

### Navigation systems in use today (7)

1. Sidebar (3 groups: Workspace, Creative tools, Studio; 10 links).
2. Top bar: breadcrumb, "Jump to a tool" (Ctrl K finder), health pill.
3. Create sub-nav in the Immersive layout (Generate / Guided workflows / Prompt Lab / Asset library / Runs & review).
4. Create stage track ("1 Prepare · 2 Run · 3 Review · 4 Reuse").
5. Overview flow map (Brief → Create → Review → Reuse) and tool links.
6. Workflow Studio hero tabs (Guided paths / Workflow builder / Headless & agents).
7. Spoken Briefs' own header links; plus the dead legacy top bar in the HTML.

Five ways to pick a recipe exist inside one dialog (task select, "Help me choose a recipe", "Explore creative bundles",
search + modality + collection filters, the list), plus the 7 Overview task cards and a second bundles button. The task
select and the shortlist use two different 7-item taxonomies.

## Object model (what the user manipulates)

| Object | What it is (plain words) | Key fields shown | States | Where it lives |
| --- | --- | --- | --- | --- |
| **Recipe** (preset / recipe) | A named, working starting point: model + graph + defaults | name, model family, modality, input shape (words / 1-3 pictures / pose), measured time, verified flag, licence note, required files, backend | ready · needs files · needs another environment · unverified | `presets/catalog.json` (89 presets), `presets/recipes.json` (67 authored recipes) |
| **Draft** | The unsaved brief + controls for one recipe in this browser | prompt, negative, controls, attached sources | saved in browser · another tab changed it · storage unavailable | browser `localStorage` |
| **Setup** | A named saved draft ("Saved setups") | name, recipe, controls | — | Workspace (server) |
| **Source / reference** | A picture attached to a numbered slot with a role | slot number, role (identity, pose, style, costume...), "use from" / "avoid" notes, size | empty required · attached · staged · unsupported extra | Create reference board |
| **Job / run** | One submission to ComfyUI | recipe, controls, seed, prompt IDs, elapsed, outputs, message, failure diagnosis | see 05 (10 statuses + stopped tracking + put away) | `experiments/runs/<job-id>/` |
| **Output** | A file a job produced | image/video/3D/audio, seed | → becomes an Asset | ComfyUI output folder |
| **Asset** | A library item with identity | title, recipe, prompt excerpt, seed, tags, notes, review, favourite, run label, lineage, same-run siblings, sha256 | review: unreviewed · keeper (`selected`) · needs work · rejected; favourite; trashed | Workspace SQLite + content-addressed store |
| **Collection** | A named group of assets (many-to-many) | name, description, count | — | Workspace |
| **Plan / study** | A bounded, reviewable piece of work: comparison, scene, voice take, native export, articulated prop | name, kind, axis + values or variants, budget (reserved/allowance), time allowance, stages | planned · queued · submitting · running · waiting · observing · rendering · awaiting review · reviewed · completed · partial · failed · uncertain · interrupted · stopped | `production.py` |
| **Candidate** | One stage of a comparison | label A/B/C/D, status, elapsed, output | Keeper / Needs work; Choose X | inside a plan |
| **Blind review** | Snapshot of candidates for unbiased comparison | alias, crop, verdict, checks, preference, cleanup seconds, decision | Not opened → Blind review → Settings revealed → Decision recorded | Review desk |
| **Export** | Native finishing output: sprite atlas + timing, layered ORA/Krita, Godot project, GLB | format, frames, anchor, filtering, verification | as plan states | Runs & review |
| **Brief** (Prompt Lab) | Creative intent compiled per model profile | brief, profile, facets, tags, avoid, references | built · blocked (with reasons) · saved revision | Workspace |
| **Model file / environment** | Weights and the ComfyUI install that loads them | filename, size, folder, sha256, source, licence | installed · missing · verify · downloading; environment: Main library 8188, HiDream 8192, H3 8194, Qwen 2.1 8196 | `models/library.json`, `app/backends.py` |
| **Guide** | A 4-6 step walkthrough over the real controls | step, observed evidence | step N of M · paused | `studio_workflow/guides.py` |
| **Bundle** | A curated look: recipe + LoRAs + settings + examples | ingredients, examples | — | `bundle-showcase.json` |

Relationships: Recipe → Draft → Job → Output → Asset → (Collection, Plan candidate, Source for the next Draft).
Lineage links an Asset to the Assets it was made from. A Plan reserves a budget of Jobs.

## Proposed IA (Proposal)

Goal: one shell, one vocabulary, four daily places and a quiet back room.

```
Studio (one shell, one palette, Ctrl K everywhere)
├── Home            what needs me now: running/uncertain jobs, review backlog, last result, start a task
├── Make            one workspace, task lens chips: Create · Edit · Combine · Restyle · Pose · Animate · 3D
│   ├── Recipe picker (one dialog: task → recipes with thumbnails, time, readiness)
│   ├── Brief + Sources board + Parameters drawer
│   ├── Run dock (Generate, estimate, first blocker + fix)
│   └── Results strip for this draft (seeds side by side with sources)
├── Library         all assets; Review mode (keyboard) is a mode of the grid, not a dialog
│   └── Asset detail (side panel): decision, why-chips, lineage, Continue with this
├── Runs            one timeline of every job and plan: Running · Needs attention · Done · Put away
│   ├── Compare (plans + blind review desk merged into one compare board)
│   └── Exports (sprite / Krita / Godot / Blender)
├── Prompt Lab      (becomes a panel of Make: "Help me write this"), kept as a full page only for saved briefs
└── Setup           models & environments, storage, guides, workflow builder, voice/scene tools, about
```

| Current place | Proposed home | Notes |
| --- | --- | --- |
| Overview | Home | Keep stats that lead to action; add running/uncertain jobs first |
| Create | Make | Task lenses replace the 7 task cards + task select + shortlist |
| Guided workflows (paths) | Make (inline coach) + Setup › Guides | A guide is an overlay on the real controls, not a separate page |
| Workflow builder | Setup › Workflow builder | Expert tool; keeps its own canvas |
| Asset library | Library | Review queue becomes Review mode |
| Runs & review | Runs | Jobs (today in Create › Problems / Recent runs) and Plans unified |
| Review desk | Runs › Compare | Same data, same blind rules; reachable directly |
| Prompt Lab | Make › "Help me write this" panel | Addresses #278 "hands off so the image is a couple of clicks away" |
| Scene editor, Voice takes, Spoken Briefs | Setup › Scene & voice (secondary) | Owner: scene editor "not needed now" |
| Models & setup, Workflow guide | Setup | Environment switch stays explicit and only here |
| NSFW lab | Unchanged, unlinked | Out of scope for design |

### One vocabulary (Proposal)

| Use | Instead of |
| --- | --- |
| Library | Workspace, Asset library, Your experiments, Your creative library |
| Runs | Runs & review, Experiments, Experiments & finishing |
| Keeper / Needs work / Rejected / Unreviewed | selected, Keep for consideration, Choose X, Needs another pass |
| Recipe | preset, recipe, workflow (for the user-facing starting point) |
| Environment | backend, model environment, runtime |
| Run | job, generation, graph run (graph run only in expert detail) |
| Unknown outcome | uncertain (keep the word in the detail line) |
| Put away / Bring back | acknowledge, archive, dispose |
