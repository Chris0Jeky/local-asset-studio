# Native exports

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
