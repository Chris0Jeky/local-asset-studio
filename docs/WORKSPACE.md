# Your asset workspace

**Import images** adds your existing PNG/JPEG/WebP originals without generation.
Select images and use **Create native export** to arrange their order, layer
names or frame timings, then prepare and explicitly Start the plan in
Experiments. [Native exports](NATIVE-EXPORTS.md) include ORA/Krita documents,
sprite atlases and actual Godot import/playback checks.

Open **Workspace** in the Studio to browse images, video, audio and 3D outputs.
Search matches titles, recipe names, tags and notes. Media and date filters help
find a study among repeated experiments.

Create a collection with **＋**, select assets using their checkboxes, and choose
**Add to collection**. An asset can belong to multiple collections. Removing a
collection leaves the assets available in All assets.

**Group by** arranges the grid into sections by recipe, day or run, each with a
count. The choice is remembered in this browser only; it changes nothing that is
saved with an asset.

Open an asset to rename it, tag it, record notes or choose a review state.
**Selected** is your creative selection; it does not certify model licensing,
anatomy, topology or engine import. Favorites are a separate shortcut. The
**reason chips** under Review (hands, face, style off, composition, anatomy,
artifacts, crop) add or remove ordinary tags, so a Needs work decision carries a
reason without typing; they save with the asset, not on their own. **Same run**
lists the other outputs of the same job so you can compare them without leaving
the dialog.

**Review next (n unreviewed)** opens the newest unreviewed asset in the current
view as a queue. The dialog then shows *k of n* and accepts <kbd>K</kbd> keeper,
<kbd>W</kbd> needs work, <kbd>X</kbd> rejected, <kbd>S</kbd> skip and the arrow
keys; shortcuts are ignored while you are typing in a field. Each decision is the
ordinary Save details write, with the same revision guard, and only a confirmed
save advances the queue: an unconfirmed or conflicting save keeps that asset on
screen with its evidence. Skipping saves nothing.

With assets selected, **Mark selected: Keeper / Needs work / Rejected** applies
the same single-asset save to each one, three at a time, and reports progress.
Anything that fails is listed with whether it was refused or merely unconfirmed;
no retry is sent for you. The four review states are unchanged.

**Move to Trash** removes an asset from the regular views. Open Trash and choose
**Restore** to bring it back with its collections, notes and recipe. Trash is
recoverable and does not reclaim disk space: source files and snapshots remain.
There is no automatic purge.

Select assets and choose **Export pack** for a ZIP containing originals, complete
generation recipes and a manifest with hashes, provenance, tags and notes.
Exports are drafts until reviewed for their intended use. **Edit image**,
**Animate**, **Make 3D** and **Upscale** attach the selected asset to a recipe;
the separate Generate action starts the job. The parent asset is retained as
lineage on new jobs.

Media is copied into a content-addressed store under the configured
`experiments_root/workspace/media`. Organization lives in `workspace/assets.sqlite3`.
Back up the whole experiments directory, including uploads and runs, to retain
recipes and their input references. Models and the ComfyUI installation remain
separate dependencies. Existing outputs are indexed without executing workflows.

Saved setups now live in the same workspace database. Existing browser setups
are migrated on first load. Deleting a setup does not delete its past outputs.

The launcher uses a cheap Studio identity check, so opening it again reuses the
server. Model/node discovery is cached for two minutes. **Models & folders →
Refresh inventory** also refreshes the node schema after manual model or node changes.
