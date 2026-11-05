# Hosted native shading qualification

The **Native procedural shading (opt-in)** Actions workflow runs actual Blender
exports from the PR's exact head commit. Request it by adding this exact text to
the PR body:

```text
Native Blender shading qualification: requested
```

Opening, updating, reopening or editing the body of a PR touching the workflow's
scoped paths reevaluates that request. Unmarked PRs skip the native job. A future
Actions UI **Run workflow** (`workflow_dispatch`) invocation also requests it.
This uses `pull_request`, never `pull_request_target`, with `contents: read`, no
secrets, no persisted checkout credentials and an Ubuntu 24.04 hosted runner.

## Selected runtime and bounds

`research/procgen/blender-shading-runtime.json` explicitly selects the official
Linux x86_64 **Blender 5.4.0 Alpha, build `6f4fc760c138`**, listed on 5 November
2026. The loader validates the official HTTPS hostname, exact archive/checksum
paths and redirect destinations; it never discovers or substitutes another
runtime. It retains the original official checksum and verifies the archive
SHA-256 before extracting or executing it. The constrained tar extraction rejects
entries outside the expected runtime directory, escaping links and special files.

Downloads have a shared 180-second deadline, a 20-second socket timeout and an
800 MiB archive limit within a four-minute step. Extraction is limited to 4 GiB
and 100,000 members. Blender identity has a 90-second process limit. Each of the
six production exports has the existing probe's 180-second process limit; the
required test has a 1,110-second outer limit. The entire job has 25 minutes.

Before qualification, a separate Blender process must report major/minor **5.4**
and the exact selected build hash. Its receipt records Blender build/platform,
Python/sys paths, bundled NumPy version/path, bundled glTF exporter Python source
hashes and the production exporter's normals default. Actions' host Python does
not install packages into Blender's separate Python environment.

The workflow sets `PROCGEN_LIVE_BLENDER`, `PROCGEN_REQUIRE_SHADING_NATIVE=1` and
`PROCGEN_SHADING_EVIDENCE`, then runs `test_procgen_shading_native.py`. Missing
runtime configuration fails the required gate. The gate performs six production
exports: lantern, crate and plant, each at smooth 0/1 and all three LODs. It
inspects actual GLB normals, hard edges/caps and unchanged triangle geometry.
It does not render or invoke Godot or Khronos validation.

## Evidence and expiration

The artifact contains source commit/tree, runtime descriptor, original official
checksum, verified archive/binary digests, observed runtime identity, logs,
requests, mesh gates, all 18 GLBs, BLEND outputs and the final shading receipt.
It is uploaded with `if: always()` after failure too. Inspect the receipt's state,
all six cases and exact source/build identities before treating a run as evidence.
Bootstrap failures do not establish native qualification.

Artifacts request **30 days** retention, subject to repository policy. The large
downloaded runtime archive is **not uploaded**. A checksum and build hash identify
bytes; they do not preserve the runtime for replay once its source disappears.
A durable copy of the verified runtime would be a separate future action.

Blender's official archived daily builds are purged after at most **90 days**.
When this selection expires, a requested run must fail visibly. Update and
requalify the explicit selection if another run is needed; routine unmarked PRs
remain independent of the daily download. This lane is targeted Linux alpha
evidence, not qualification of the configured Windows workstation or all eight
generators through the Studio/Godot workflow.

Official references:

- [Current daily build listing](https://builder.blender.org/download/daily/)
- [Build listing API, naming and archive retention](https://developer.blender.org/docs/handbook/tooling/buildbot/)
- [Linux archive installation](https://docs.blender.org/manual/en/5.4/getting_started/installing/linux.html)
- [Bundled Python](https://docs.blender.org/api/main/info_tips_and_tricks.html#bundled-python-extensions)
- [Bundled glTF exporter and normals](https://docs.blender.org/manual/en/5.4/addons/scene_gltf2.html)
- [5.4 command line options](https://docs.blender.org/manual/en/5.4/advanced/command_line/arguments.html)

Offline loader faults are checked with:

```sh
python -m unittest discover -s tests -p test_ci_blender_runtime.py -v
```

These tests use in-memory responses and tiny synthetic archives. They neither
download Blender nor establish native shading behavior.
