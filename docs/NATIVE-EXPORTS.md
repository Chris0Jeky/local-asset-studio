# Native exports

In Studio, select originals in **Workspace → Create native export**. Arrange the
source order, frame durations or layer names, choose the format, and prepare the
plan. Start it explicitly from **Experiments**. The resulting source pack includes
the originals, full recipes, interchange files and execution reports.

**Layered artwork · ORA / Krita** offers **Save and reopen in local Krita**.
Studio pins the configured executable before Start, exports the flat layer stack
to KRA, then reopens it to PNG. The result provides a native KRA download and
preview. Clear that option to produce ORA only. See [the Krita adapter](KRITA-ROUNDTRIP.md)
for its limits. Godot's separate verification option performs actual local import
and timing inspection, rather than only packaging a project.

The Studio coordinator adds these optional application steps around the format
helper described below. No generation is submitted for a native export.

`NativeExports` turns trusted Studio asset records into one exclusive local
export directory. It accepts no commands, code, workflow graphs, or output paths
inside `options`; it never submits generation and does not start Godot.

```python
from native_exports import NativeExports

exports = NativeExports(repo_root, media_root, godot_path=r"C:\Tools\Godot.exe")
result = exports.execute(
    output_root=r"C:\exports\hero-idle",
    kind="godot",
    assets=[
        {"id": "idle-0", "path": "jobs/idle-0.webp", "filename": "idle-0.webp",
         "media_type": "image/webp", "sha256": "<64 lowercase hex characters>"},
        {"id": "hero-mesh", "path": "jobs/hero.glb", "filename": "hero.glb",
         "media_type": "model/gltf-binary", "sha256": "<64 lowercase hex characters>"},
    ],
    options={"clip": "hero-idle", "duration_ms": 100, "anchor": [256, 512],
             "loop": True, "filter": "nearest", "columns": 4},
)
```

`repo_root` and `media_root` must be existing directories. `output_root` must be
an absolute path that does not yet exist. Each asset `path` is a portable relative
path beneath `media_root`; the exporter resolves it, rejects symlink escapes, and
matches its bytes to the supplied SHA-256 before any output directory is created.
Records can additionally carry JSON `recipe` and `metadata`, which are preserved
in `metadata.json` beside the source snapshots.

Image records must be PNG, JPEG, or WebP and are ordered exactly as supplied.
There must be 1–32 images with one shared canvas, no more than 16 million total
source pixels, and at most one GLB for `godot`. The exporter saves original bytes
under `sources/`, converts each still image to RGBA sRGB PNG under `interchange/`,
and never resizes or trims an individual image. `duration_ms` is either one
integer or one integer per image. The default anchor is bottom-centre; durations,
anchor, loop, and filter are shared by atlas and Godot packaging.

Kinds are `atlas`, `ora`, and `godot`. Atlas output includes the existing bounded
sprite-atlas manifest. ORA output has supplied `layer_names` in topmost-first
order and supports only normal flat RGBA layers. Godot creates the existing fixed
template project with an optional GLB, but does not execute the configured local
Godot executable. Every result contains relative artifact paths, source
provenance, measurements, limitations, and `native-sources.zip`; the ZIP excludes
any `.godot` cache.
