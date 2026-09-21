# Experiments and native finishing

**Import images** in Workspace brings existing PNG/JPEG/WebP originals into the
same collection, lineage and source-export system. Importing does not generate.
**Build an articulated prop** in Experiments prepares a bounded authored chest:
separate body/lid, a rear hinge, open/hold/close keys, CPU inspection renders,
an editable BLEND and animated GLB. Start runs the fixed local Blender adapter.
The viewer plays its animation and the source pack retains the full recipe.
This is authored geometry, not automatic part segmentation or character rigging.

Open a recipe in **Create**, then choose **Plan comparison**. Compare one numeric
setting across up to four values. Preparing the plan checks current ComfyUI
nodes, selected model files and input images. It records the actual graph,
reference roles, model hashes, runtime information and a plan hash. It submits
nothing until **Start comparison** is pressed.

A live summary at the top of that dialog states the question in one line -
which setting, which values, on which recipe, how many graph runs and roughly
how long, reusing the measured per-run time Create already shows. Under the
fields, the arithmetic is spelled out (`3 values x 1 seed = 3 runs; 8
reserved`) and a total below the candidate count is refused before the plan is
prepared. The estimate is a reading of Create's measurement, never a second
estimator: with no measured history the summary says so instead of guessing.

Three actions under **Advanced: plan several settings from the library** use
`POST /api/experiments/plan`. **Inspect available settings** reads the current
recipe without replacing a local plan. **Plan from settings library** reads the
family entry in `presets/settings-kb.json` and offers a grid of the axes the
recipe can actually change — steps, sampler, scheduler, LoRA strengths — with
the first axis varying slowest and at most eight candidates. **Remix LoRA
weights** re-weights only the ordinary adapter slots that are already on: one
variant per slot at the top of the family ladder while the others support at
its bottom, plus one blend at the middle step. Slots that are off stay off and
are not injected into candidate controls or described as selected.

Each variant carries the rationale and the source URLs of the setting it
changes, and the plan records the SHA-256 of the knowledge base it was planned
against. Planning reserves nothing and submits nothing; the variants land in
the same dialog and **Prepare plan** validates every one of them exactly as it
validates a single-axis comparison. Remove a variant with ✕ to fit the
generation budget. Two variants that resolve to the same graph are refused:
different labels are not different work. Candidate cards show the variant label
instead of an axis value, and still hide it while comparing blind. Each card
states every fact once: the label, then only the settings the variant moves off
the open recipe, then its rationale and sources. The `description` field of the
plan response remains the full one-line summary (label, settings and rationale)
for non-browser readers; the browser composes its own card from the parts.

Studio uses its existing serial worker. Manual ComfyUI jobs finish first. Each
stage gets a durable identity before its job is created, and submission intent is
written before a POST. A lost response stays uncertain. Resume observes known
prompt IDs and may continue stages that never started; it does not guess that an
unknown submission failed or blindly send it again. There are no automatic
generation repairs. Failed stages remain explicit.

The original generation allowance is shared across branches. A start reserves its
graph runs atomically, and uncertain or stopped attempts retain those reservations.
The allowance counts graph executions, not individual sampler nodes or output
files. Time budgets and Stop apply between stages; a running remote job can finish
after the deadline. Timings include queue wait/loading where those occur and are
observations, not equal-compute model benchmarks.

Comparisons show neutral candidate letters and can hide settings. Every original
remains in Workspace. The contact sheet is only a thumbnail comparison; inspect
full outputs before choosing. **Choose** and **Needs another pass** record a
locally identified creative review. They do not authenticate a reviewer or decide
model rights, mesh quality or engine acceptance. A branch preserves its parent
plan and shares its budget while allowing a changed brief or reference.

Select images in **Workspace**, then **Create native export** for a sprite atlas,
OpenRaster image or Godot sprite project. Reorder sources, set per-frame durations
or layer names, and choose a common anchor. Images must share a canvas; Studio
does not resize or independently trim them. Exports include source snapshots,
recipes, conversion metadata, native files and a ZIP pack. Godot exports may
include one GLB and an actual headless import/playback check when a local Godot
executable is configured. ORA supports flat normal layers; it does not invent
layer masks, hidden anatomy, a rig or a timeline.

State is kept in `<experiments_root>/projects/projects.sqlite3` with per-plan
directories beside it. Plans and attempts survive server restarts. Failed native
directories are preserved for diagnosis. Existing directories are never reused
as a new export target. The API serves only recorded artifacts from these roots.

Current adapters are prepared catalog generation, comparison contact sheets,
atlas/ORA packaging, and Godot project import/playback. The larger research plans
remain design inputs: their arbitrary task names and embedded instructions are
not executable API commands.

## Inspect available settings without planning variants

In **Advanced: plan several settings from the library**, choose **Inspect available settings**.
The current recipe's bound axes are split into available choices and explicit unavailable rows,
with reasons for a held strength, a held family schedule, an alias sharing a held input,
or documented combo values that the recipe's current socket choices do not offer.
Inspection preserves existing variants, selected axes and the owner's budget draft, including an
invalid budget that still needs correction. It does not reserve or generate anything. Use
**Plan from settings library** or **Remix LoRA weights** separately to propose replacements.

The same read-only operation uses the existing endpoint:

```json
{"preset_id":"anima-artist-stack","controls":{},"mode":"inspect"}
```

Send that JSON to `POST /api/experiments/plan`. The response contains `axes_available`,
`axes_withheld`, the existing `knowledge_sha256`, `variants: []`, `generation_submitted: false`
and `reservation_created: false`. Inspection rejects `axes` and `limit`, because it does not
select a grid. Grid and remix responses expose the same explanatory projection; their existing
refusal and eight-candidate limits remain unchanged.

An unavailable row names its `control`, stable `code`, contributing
`accelerator_slots`/`accelerator_files` and a plain-text `message`. A filtered combo also
retains its documented and currently offered values, rather than disappearing. The inspector
and planner use one policy, not two compatibility
engines. Inactivity must be established for every relevant binding; an unknown strength is not
silently called zero. Matching a filename to a KB role is not installed-byte attestation, and
unknown files or embedded acceleration remain outside this correction. Inspection does not
certify an already-authored set of variants. Manual comparisons and generation admission are
unchanged.

Browser replies are scoped to the latest plan/inspection request and captured comparison recipe.
A replaced or closed dialog, cleared plan or removed candidate cannot be overwritten by an older
reply. Local clear/remove actions also finish the in-flight status instead of leaving a stale
“Reading…” message. A failed inspection keeps existing variants while removing stale advice and
selected axis identities. No inspection is
started on page load. Contract tests are `test_settings_inspection.py`,
`test_production_planner_inspection.py` and `production_planner_inspection.cjs`; the HTTP fixture
uses the production handler with temporary storage and no model execution.
