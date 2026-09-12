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

Two buttons in that dialog plan several documented settings at once, through
`POST /api/experiments/plan`. **Plan from settings library** reads the family
entry for this recipe in `presets/settings-kb.json` and offers a grid of the
axes the recipe can actually change — steps, sampler, scheduler, LoRA strengths
— with the first axis varying slowest and at most eight candidates. **Remix
LoRA weights** re-weights only the adapter slots that are already on: one
variant per slot at the top of the family ladder while the others support at
its bottom, plus one blend at the middle step. Slots that are off stay off.

Each variant carries the rationale and the source URLs of the setting it
changes, and the plan records the SHA-256 of the knowledge base it was planned
against. Planning reserves nothing and submits nothing; the variants land in
the same dialog and **Prepare plan** validates every one of them exactly as it
validates a single-axis comparison. Remove a variant with ✕ to fit the
generation budget. Two variants that resolve to the same graph are refused:
different labels are not different work. Candidate cards show the variant label
instead of an axis value, and still hide it while comparing blind.

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
