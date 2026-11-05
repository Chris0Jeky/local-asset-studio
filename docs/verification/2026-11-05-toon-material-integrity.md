# Toon material integrity: sampler identity and imported-material retention

Date: 5 November 2026. Issues: [#1993](https://github.com/Chris0Jeky/local-asset-studio/issues/1993) and
[#1994](https://github.com/Chris0Jeky/local-asset-studio/issues/1994).
Base: local `3c67895a1ab930f5aeeda22343de46bb29b79c63`, tree
`04f099c1a3b9ff21795c3827a7c8cd2ccba20cd8`, matching GitHub main `26036b05e22b6adfd486b6e511b4fc0cae05593d`.

## Reproduced failures

Before the change, two Image Texture nodes referencing one image produced one sampler uniform and one texture
sample, even when one requested Closest/Repeat and the other Linear/Extend. The shared image's last exported
setting won. Linked Transmission Light was reported as `partial` with a shader file, but the Godot runner applied
any record with a file. A nonblack unlinked Transmission Light default was incorrectly reported as `ok`.

The initial offline regression run executed 31 test methods and reported nine failing assertions/subcases: two
direct/group sampler-sharing cases, six unimplemented or invalid sampler modes, and constant transmission. This
was a Python/compiler reproduction; no Blender or Godot execution took place locally.

## Changes and acceptance coverage

- Image settings stay on their Blender nodes. Uniform identity now includes image, interpolation and extension;
  the sample memo also uses that sampler identity, UV expression and shader stage. The report retains its
  `uniform -> image` mapping, and legacy IR falls back to image settings or Linear/Repeat defaults.
- Generated-shader tests observe sampler names as well as evaluated colors. They cover changes to filtering
  alone, wrapping alone, or both; direct nodes and groups; identical-setting reuse; different UVs; Color/Alpha
  reuse; serialization; and explicit refusal of Cubic, Smart, Clip, Mirror and invalid sampler values.
- Both linked and nonblack constant Transmission Light produce `partial` artifacts for inspection. An unlinked
  black RGB value remains `ok`, independent of its alpha default.
- The Godot runner's production guard requires exactly `status == "ok"`, a usable file field, and a material from
  the factory before setting a surface override. Missing/unreadable/blank shader source returns no material.
  Rejected records preserve the current imported material and expose a reason, including unsupported features.

## Local verification

Commands used for this slice:

```text
python -m unittest discover -s tests -p 'test_toon_compile*.py' -v
python scripts/validate-repo.py
git diff --cached --check
```

Final targeted result: **32 tests in 0.046 seconds: 31 passed, 1 skipped**. The skip is the explicit missing-Godot
native policy test. Repository validation passed: **98 preset graphs/bindings, 194 pinned assets, 4,883 tracked
paths**, 743 local-media manifest entries / 102 references, and 167 LoRA names. `git diff --cached --check` passed.
The workflow YAML also parsed successfully, with both PR/main-push toon path filters and the required toon test
step present.

## Native evidence gate

`tests/test_toon_compile_native.py` uses only an explicit `STUDIO_TEST_GODOT`; it does not discover or install a
local runtime. The existing Linux/Windows Native engine evidence workflow runs the toon test glob with its
checksum-pinned Godot **4.5** setup. Missing executable configuration fails that required hosted lane.

The headless probe imports the repository's original CPU-authored GLB fixture and checks its `FixturePaint`
material. It invokes the actual production guard and shader-file loader against that imported mesh for 15 cases:
ok, partial, unsupported, unknown/missing status, missing record/file field, empty/invalid file field, preexisting
overrides, unavailable factory material, and absent/empty/whitespace shader files. Partial and unsupported fixture
records deliberately refer to existing shader files, so their retained material cannot be explained by an absent
artifact. The positive case uses a nonempty shader and must replace the material; rejected cases must leave the
same active material and original mesh material intact. Factory-call counts also prove rejected statuses are not
loaded.

With `STUDIO_ENGINE_EVIDENCE`, `toon-material-policy/` retains the project and GLB, the literal command and source
hashes in `plan.json`, `execution.json`, stdout/stderr, and `result.json` containing Godot's version, imported material
metadata, all 15 decisions and any failures. The native launch has a 60-second timeout and preserves timeout logs.

Native execution is **pending hosted CI**. This local environment has no configured Godot or Blender runtime;
the native test is explicitly skipped. No native export, GPU rendering, shader compilation coverage, or visual
parity is claimed from the offline checks. The Godot **4.5** policy probe does not establish Godot **4.7.2** visual
parity or repeat the historical 2 November measurements in `docs/TOON-COMPILER.md`. A nonempty malformed shader is
outside this file-availability guard's scope.

Art direction/replacement of the paused asset wave (#1923), parallax usability (#1219), and the island default
switch remain owner decisions. This change records no art or licensing acceptance.
