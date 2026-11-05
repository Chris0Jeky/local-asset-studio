# R&D programme "Harbour Night", 2 November 2026

The owner gave the machine to an agent R&D programme overnight and through the next day, to move LAS from tooling towards
experiments with bleeding-edge models and tools. This file records what ran, what it proved, what failed, the lessons,
and where to pick each thread up again. The visual brief is the private artifact
<https://claude.ai/artifact/3bjxaiBCPtc5ub3vEh2Q2o>. Lab media stays outside Git, under
`E:/local-asset-studio-labs/rnd-20261102/`, and so do MIRA art and adult-adjacent lab images.

## How it ran

- A coordinator session ran about ten Claude lanes, each in its own worktree with a `TRACKER.md` in the lab folder:
  "Resume here", findings and UE5 assets. The programme log, with every decision and incident in time order, is
  `E:/local-asset-studio-labs/rnd-20261102/PROGRAMME.md`.
- Routing: Opus 5.5 implemented, Codex GPT-6.1 Terra xhigh was the review gate, Sol took hard calls, Haiku did mechanical
  work and ran inside the experiments, and a Muse swarm (`rnd-las`) did retroactive review.
- A GPU and heavy-work lease (`gpu_lease.py`) serialised heavy jobs. It has a fair FIFO queue, a 45-minute cap and a
  RAM guard (at least 6 GB free, at most 60% commit). `ramlog.ps1` logs memory every 30 s.
- 63 LAS PRs (48 from the lanes, 15 from the parallel Codex task) and 4 mira-companion PRs merged by 15:42 on 2 November,
  through the T2 gate. Three more (#1990, #1991, #1992) were in the merge queue. A sequential merge queue landed a 15-deep stack.

## Results worth keeping (PRs are LAS unless named)

| Thread | Result | Where |
| --- | --- | --- |
| Blender runtime probe and manifest | Capability probe and typed scene/rig manifest with a semantic checksum, on 4.5 and the 5.4 alpha | #1912, #1914, `docs/BLENDER-LAB.md` |
| Export parity sentinel | 7/7 seeded defects caught on both builds, 4 of them invisible in renders | #1916 |
| Persistent Blender worker | 26× (4.5) and 19× (5.4) faster than fresh processes, no state leaks | #1924 |
| Typed MCP façade | 9 tools, no arbitrary Python; driven live by Haiku and Sol | #1936 |
| Render-space active testing | Searches camera, frame, shape-key weight and culling; finds all 5 fixed-view-blind defects | #1960 |
| Delta localisation | The sentinel names objects and materials ("material A → B on Badge") | #1962 |
| Confined repair loop | Toy corpus: 3/4 exact repairs, 8/8 declines, 0 collateral. Real assets (57 cases): Sol 22/28 exact, 0 collateral; Haiku 18/28, 1 collateral | #1966, #1982 |
| "Check this export" in the Studio | The sentinel as a native job card | #1971 |
| Render critic | Reference (parity) mode: 96/96 seeded defects, 0/12 false alarms; no-reference VLM labels unusable | #1956, #1974, #1981 |
| Local splats | Brush on Vulkan, RX 9070 XT: 30k steps in about 2.5 min; held-out 35.4 dB on a near+far orbit (far only 26.4, defaults 19.0); Blender 5.4 imports splat PLY/SPZ | #1967, #1973 |
| GPU benchmark | HIP vs HIP RT and OpenGL vs Vulkan on 4.5 and the 5.4 alpha | #1942, `docs/research/BLENDER-BENCHMARK-2026-11-02.md` |
| Procedural asset factory | Geometry Nodes generators (room kit, lighthouse room, pier, coastal path, tide pools, market street) with 15 gates; a Haiku agent hit 10/10 briefs at 1.6 attempts; 210-view labelled dataset validated; level assembler for Godot | #1933, #1946, #1958, #1959, #1961, #1968, #1972, #1980 |
| Anime toon kit and Suzu | Original character Suzu: bible → Anima concepts → Klein turnaround → VRM in Blender 5.4 (Material Lighting toon, SDF face shadow) → Godot (spring bones, Kokoro voice, Rhubarb lip sync, mocap gait with foot IK); 50 s short "A day at the harbour" | #1927, #1935, #1947, #1963, #1969, #1975 |
| Suzu v2 | Design-faithful hair and outfit by script and from a VRoid base; silhouette IoU against the turnaround; the working route is the VRoid hybrid with the scripted v2 outfit | #1978, `waifu-lab/TRACKER.md` |
| New cast | Kiri and Hana redesigned in the owner's WuWa/ZZZ-like direction (curvy and slender), 3D v2 VRMs, a duo scene with Suzu | #1976, `waifu-cast/TRACKER.md` |
| Talk to Suzu | A fully local companion: llama.cpp + Kokoro + Rhubarb + VRM in Godot, about 1 s from Enter to the first word; Gemma 4 12B is the default over Qwen3.5-9B; memory with a no-invention guard | #1979, #1989, `docs/COMPANION-LOOP.md` |
| Studio UX from the owner's tour | Review keys visible, Full editor step strip, Workflow lab stages, guide coach, review grid journey; Kromoss + DMD2 + Mikko is a one-press Make look | #1926, #1929, #1930, #1934, #1940, #1944, #1965 |
| Characterful art direction | Three directions for the Studio's own illustrations, Suzu guide poses, harbour-short posters; the choice is the owner's (Versus, inbox `las-art-direction-1923`) | #1955, #1964, #1923 |
| MIRA (private repo) | 4.5 vs 5.4 regression (only Bevel edges differ), paint → UV bake, proxy normals (25° → 3°), Material-Lighting toon, rig/morph gauntlet, hair colliders | mira-companion #55, #56, #57 |

### Factory triangle reports — 5 November follow-up

New factory reports make the LOD0 triangle count explicit in the `triangle_budget` gate. `triangles` is the render-mesh
count checked against `budget`; `collision_triangles` counts the collision proxies; `glb_triangles` is their sum for
`asset_LOD0.glb`. Each disconnected piece with collision enabled gets a 12-triangle box, so one collision object may
contain several boxes. A brief that caps the whole exported GLB should use `glb_triangles`; passing the render budget alone does not
meet that stricter cap. Older reports may not have these additional fields. This reporting change does not alter the
generated geometry, collision policy or budget threshold (#1949).

## What failed or stays open

- No local critic can judge without a reference. The no-reference VLM flags clean renders, and the pairwise likeness test
  scored 57% (VLM) and 43% (CCIP) against the owner's presses, which is chance level with a position bias.
- Unreal 5.8 imported Suzu, but no capture route produced a toon frame within the 2 h cap.
- See-through LayerDiff3D is parked: 5.5 GB host RAM, 34 min at 1280 with no output, and it was running during the second freeze.
- No permissively licensed coastal splat exists for agents to fetch. The anime-sets-from-one-illustration experiment
  (Qwen-Edit multi-angle → COLMAP → Brush) is mid-way: see `frontier-lab/TRACKER.md`.
- Every image-to-3D route checked needs CUDA or Linux, so characters are built from VRM bases.

## Incidents and lessons

- **Secret exposure.** A plain `codex exec` review printed the environment, and the owner's GitHub token reached the
  model context. Codex inherits every variable (`inherit = 'all'`). Fix: `codex_terra.sh` strips token, PAT, secret and
  key variables and passes `shell_environment_policy.exclude`; verified 0 secret characters against 144 with plain
  `codex exec`. Tracked as claude-config#1229. The owner still has to revoke the token.
- **Two hard freezes** (Kernel-Power 41, at 11:32 and about 12:18). Several heavy jobs had stacked: See-through, unleased
  COLMAP GPU-SIFT, ComfyUI-cached models and local full test suites. The second freeze zero-filled a worktree's git
  index and 448 files written just before it; all other trees were clean. Rule since then: one heavy job machine-wide
  through the lease, a RAM guard, no local full suites while lanes run.
- **Network dropouts** (DNS) twice cut every lane mid-turn. Proton VPN also throttles downloads, so use resumable
  fetchers with completeness checks.
- **Shared %TEMP%.** Never glob-move there: one lane briefly swept 330 other sessions' files.
- **Unconfined headless agents.** `claude -p` and `codex exec` children inherit bypass mode, every tool and the
  environment. Confine them with `--restricted --tools ""`, an isolated `CODEX_HOME`, and a canary run first.

## Picking it up again

- Each lane's `TRACKER.md` under `E:/local-asset-studio-labs/rnd-20261102/<lane>/` starts with "Resume here".
- Unreal demo: `E:/UnrealProjects/Lanternfall/docs/LAS-RND-ASSETS.md` lists the characters, sets, animation, voices
  and splats ready for Lanternfall, with formats, licences and import notes.
- Owner choices waiting: the Versus contests (art direction #1923, harbour-short posters, Suzu concepts, sheets and v2
  builds, Kiri and Hana v2 concepts, palettes, guide poses, the companion model A/B), the tour repeats for #1920 and
  #1921, MIRA q-5, and revoking the leaked token.
