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

- `python -m unittest discover -s tests -p 'test_procgen*.py'`: **54 tests,
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
gate evidence; the actual Blender qualification is recorded below.

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

The hosted native gate has now passed and its exported geometry and normals
were inspected, as recorded below. No local native run or visual acceptance is
claimed. The qualified change merged as #2034 and issue #1948 is closed; broader
configured Studio/Windows/Godot qualification remains in #2026. Existing owner
decisions in `HUMAN_TODO.md` remain separate and were not changed by this slice.

## First native run and socket correction

Hosted run [42105583129](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42105583129)
verified the official archive checksum and Blender 5.4 alpha build `6f4fc760c138`,
including bundled NumPy and the glTF exporter. The first production export then
failed before creating a GLB: the builder addressed the Set Shade Smooth input
as `Geometry`, but its displayed socket name is `Mesh`. The builder resolves
displayed names, not the socket's internal identifier. The official
[node reference](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/mesh/write/set_shade_smooth.html)
also names the input and output `Mesh`.

The correction uses `Mesh` and makes the recording fixture match that real
interface on both sides. With the corrected fixture and the old production
code, the sphere, cylinder and cone regressions all fail with the same
`IndexError` observed in Blender. The corrected production code passes those
tests. The original failed receipt, stdout/stderr and verified runtime identity
remain in artifact `13452770402`. The later passing native run is recorded
separately below; this failed attempt is not replaced by a skipped or mock-only
result.

The [second native run](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42106126054)
completed both lantern Blender invocations and reached the per-case receipt
write. It then exposed a probe error: `engine_validation.write_json` deliberately
creates immutable files, while the probe tried to reuse the aggregate receipt
path after each case and again at finalization. Artifact `13451882092` retains
the original partial receipt and six lantern GLBs; it is a failed qualification.

Each completed case now gets its own immutable `shading.json`; the final
aggregate `receipt.json` is created once. A regression executes the real evidence
writes with synthetic geometry for both a six-case success and an export failure
after two completed cases. Both scenarios reproduced the native `FileExistsError`
before correction. After correction, all case receipts remain readable, the
final state and case count are correct, and a later failure preserves its reason.
This tests receipt handling only; it does not replace native normal validation.


## Passing native qualification

[Native run 42106959396, job 127524187967](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42106959396/job/127524187967)
passed with a direct, clean checkout of reviewed candidate
`195cf046269e08165a2ddfca0f36c02005ecb259`, tree
`5121753668bed0ccf15e71773f1ee2990a24a31f`. It executed all six production
builds: prop variants 0, 1 and 2, each with flat and smooth shading, exporting
three LODs per build for **18 GLBs**. The receipt passed the normal, hard-cap,
side-interpolation and paired-geometry invariance gates described above.

[Artifact 13451428157](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42106959396/artifacts/13451428157)
was downloaded and its ZIP SHA-256 checked against
`4a1ce5286c0b6d3b0cb37cd633e7a0a4f6589d633f45a5ecd5ab432a176e876d`.
All 18 GLB hashes and normal measurements were independently rechecked after
download. This is exported-mesh evidence from the production generator, in
addition to the offline graph and probe regressions.

The retained runtime is Blender **5.4 alpha**, build `6f4fc760c138`, with bundled
Python **3.13.13** and NumPy **2.3.4**. Its official archive SHA-256 is
`d1bc2e2d0b5bb8ff0b74ab805f5aa5c514668636ea7e70fd4dda4eb0583dd4c0`;
the executable SHA-256 is
`4e1feb831f57332f89a8b33c4cf9b0a505c1bc2d79fc46b7734a046304d9a1d9`.
The archive verification and runtime identity are part of the retained receipt.

This gate qualifies the sampled prop primitives, their realized geometry and
exported LOD normals. It does not qualify all eight generators through the
configured Studio on the owner's Windows installation, a Godot import, a render,
Khronos validation or artistic acceptance. Those wider native-path requirements
remain open in #2026. The two failed attempts above remain failed evidence.


## Merge and full-suite qualification

[#2034](https://github.com/Chris0Jeky/local-asset-studio/pull/2034) merged as
`3bfb7da4adb775ff83e6b371c8bf1650dc944408`. Its reviewed head and native checkout
above, actual merge and full-suite synthetic checkout
`0473eccac4d6d3d9b8104e69ac31b01cc272515a` all resolve to tree
`5121753668bed0ccf15e71773f1ee2990a24a31f`. The synthetic checkout's parent
`235a180cff327d42b8d7e9f65c96a3623dc47b04` has the same tree as the actual merged
parent `daebc630b2fa5b770faa3c8f7a909ae03fa96d19`.

[Full run 42106959107, job 127524419082](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/42106959107/job/127524419082)
finished at **2026-11-05T21:07:15.309Z**: **7,298 tests, 7,179 passed, 119 explicitly
skipped, zero failures/errors, 1,013.837 seconds**. The validator at
21:07:15.489Z passed 98 graphs, 194 pinned assets, 4,925 tracked paths and
167 LoRA names. All applicable required workflows passed; independent and
connected Codex reviews were clear. The original Archive infrastructure attempt
hit its setup budget; its retry in run `42106959456` passed the unchanged head.
Native repeat run `42108415535` also passed. The body-opt-out job in run
`42108777479` skipped and supplies no native evidence.

Issue #1948 is closed following this merge. The wider configured
Studio/Windows/Godot qualification in #2026 remains open, and the two failed
native attempts above remain retained.
