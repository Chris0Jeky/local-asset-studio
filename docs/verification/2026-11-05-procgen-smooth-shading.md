# Procedural round-surface shading (#1948)

## Contract and implementation

All eight generators expose `smooth`, an integer switch bounded to `0..1`.
The default is `0` to preserve the existing faceted style and old recipes.
`describe` and the Studio catalog read the same schema; no duplicate frontend
control or app-specific generator behavior is added.

`B.sphere` and `B.cyl` opt their primitive mesh into Geometry Nodes **Set Shade
Smooth**, with the group `smooth` socket driving **Shade Smooth** on the face
domain. Cylinders and cones exclude the primitive's Top and Bottom selections,
so the side normals interpolate while caps stay flat. The operation precedes
UV/part tagging, materials, placement, instance realization and part splitting.
Boxes, grids, terrain and collision boxes receive no smoothing operation.

This changes normals, not vertex positions, topology, collision geometry, LOD
selection or the render triangle budget. Increasing `detail` still controls the
polygon silhouette. Existing plans remain pinned by the adapter's schema and
script hashes; a plan prepared against an earlier schema must be prepared again
under the existing stale-plan rules.

## Offline evidence

Tests were written before functional changes and initially failed because the
schema lacked `smooth` and the Blender entry point executed at import. The
entry point now uses a normal `__main__` guard, allowing the production builder
to be imported with inert Blender sockets for graph tests.

- `python -m unittest discover -s tests -p 'test_procgen*.py'`: **53 tests,
  4 skipped**. The skips are explicit optional native/engine tests, including
  the new shading qualification; no Blender was available locally.
- `python -m unittest discover -s tests -p 'test_procedural*.py'`: **30 tests
  passed**. Schema-driven catalog, validation and explicit preparation remain covered by the existing
  Studio/SQLite/HTTP/frontend tests plus the new smoothing-control regression.
- `python scripts/validate-repo.py`: passed (98 preset graphs/bindings,
  194 pinned assets). The validator's tracked-path count depends on staging.

Graph regressions execute actual `B.place`, `B.cyl`, `B.sphere`, `B.box`,
`B.grid` and `build_tree` code against a recording socket fixture. They check
interface bounds/default/help, live control links, cap exclusion, geometry
flow through shading before UV storage, and unaffected boxes/grids. They do
not establish Blender runtime compatibility or exported normals.

The GLB probe's offline tests decode authored POSITION/NORMAL/index buffers,
reject missing/invalid normals and truncated accessors, distinguish flat from
interpolated corner normals, compare geometry independent of glTF vertex
splits/order, and retain failure receipts when a native export fails.

## Required native gate

Run with an explicit **Blender 5.4** executable (the existing production
modifier-input API requires it), bundled NumPy and the standard glTF exporter:

```console
python scripts/procgen_shading_probe.py --blender /absolute/path/to/blender --output /new/evidence/directory
```

The probe invokes the production `procgen_blender.py` entry point six times:
lantern, crate and potted plant, each with `smooth=0` and `smooth=1`, fixed seed,
`detail=12`, three LODs (`12,6,4`). Each process has a 180-second default bound.
It evaluates existing factory mesh gates and reads the exported GLB binary
POSITION, NORMAL and index accessors. It requires:

1. Flat exports retain constant corner normals within each triangle.
2. Every foliage and lantern-body triangle has interpolated corner normals
   when smoothing is enabled, including realized foliage instances and every
   exported LOD.
3. Lantern caps and the plant pot have smooth sides and flat, axial cap normals;
   every non-cap triangle must interpolate, with positive cap and side counts.
   The pot covers both the cylinder rim and cone body; a smooth rim cannot mask
   a flat cone.
4. Both crate exports have identical positions and normals; all other paired
   exports have identical names and triangle-position geometry, including
   collision meshes and every LOD. Vertex splitting in glTF may change.
5. Every exported normal is finite and unit length.

The cap/side predicate has a causal offline regression: a three-triangle fixture
with a flat cone side, smooth cylindrical rim and hard cap produces exactly
`triangles=3, varying_triangles=1, hard_cap_triangles=1`. The original predicate
incorrectly passed it; the strengthened gate rejects it for pot and lantern-cap
names, including lower LOD names. Smoothing the cone side makes the same geometry
pass. Empty meshes, missing caps and missing sides also fail. This is offline
gate evidence; actual Blender execution remains required below.

The new output directory retains the initial plan; exact source revision/tree,
dirty status and implementation hashes; each request/command and bounded
native stdout/stderr/exit logs; Blender version/build hash; GLB hashes; mesh
measurements; per-LOD normal counts; and a final `receipt.json`. A failure keeps
its receipt and any completed native evidence. A passing receipt is a shading
qualification, not a render, Godot-import, Khronos-validation or art judgment.

For unittest/CI, set `PROCGEN_LIVE_BLENDER` to the executable and optionally
`PROCGEN_SHADING_EVIDENCE` to a new retained output directory, then run:

```console
python -m unittest discover -s tests -p test_procgen_shading_native.py
```

Set `PROCGEN_REQUIRE_SHADING_NATIVE=1` in a required native lane to turn missing
runtime configuration into a hard failure instead of a skip. Ordinary offline
runs explicitly skip the native gate.

**Remaining acceptance:** execute the native gate and inspect its retained
receipt on the actual candidate revision. No local native success or visual
acceptance is claimed. Issue #1948 remains open until real exported-normal
qualification succeeds. Existing owner decisions in `HUMAN_TODO.md` remain
separate and were not changed by this slice.
