# Creative production workspace

The 11 September implementation connects the research in merged PRs #20 and #8
to the local Studio. Open the desktop shortcut or `http://127.0.0.1:8191`.
The configured installation has 54 recipes, 55 API graphs and 54 visual workflows.

## Good places to start

| Intent | Route | Useful controls |
|---|---|---|
| Anime illustration | Anima Aesthetic; free Krea Retro Anime | Prompt, seed, steps, size; compare one change at a time |
| Separate identity, pose and style | Qwen Atelier | One to three reference roles, contribution/avoid notes, resolved graph preview |
| Native 2K concepts or restyles | Switch to HiDream O1 | Eight-step audition, then optional higher-step variants |
| Animate a still | Wan 2.2 Animate Image | Short audition, motion prompt, seed, frame count |
| Organize useful results | Workspace | Collections, favorites, tags, notes, search, recoverable Trash |
| Compare variations | Plan comparison | One numeric axis, at most four candidates, shared branch allowance |
| Edit layers in Krita | Workspace → Create native export | ORA/Krita format, top-first layer order and names |
| Test a sprite in Godot | Workspace → Create native export | Order, individual frame timings, common anchor, filtering, loop |
| Build a hinged blockout | Experiments → Build an articulated prop | Body/lid dimensions; editable BLEND, animated GLB and inspection views |

Changing an environment preserves known jobs and refuses active work. It does
not download packages or start generation. It can stop an idle ComfyUI process
that matches the configured interpreter, entry point and loopback port, including
one started by the normal local launcher. Finish direct ComfyUI jobs before switching.

Image imports and native exports do not need the GPU. Source packs retain the
original files, generation recipes, names/hashes and application reports. Selected
whole images become flat layers; the Krita route does not automatically segment
an illustration into body parts or infer masks.

## Actual execution evidence

Operational outputs live under the configured `experiments_root`, outside Git.

| Run | Recorded result |
|---|---|
| Qwen three references — `386230de-61a7-4d63-9778-0bc76025b7ae` | 512×768 PNG, four steps, 1,334.646 seconds; role-conditioned result needs creative review |
| HiDream concept — `5ef80a63-9861-43fc-8687-c8229512c43a` | 2048×2048 PNG, eight steps, 184.697 seconds |
| HiDream restyle — `cb098ca3-0fbc-4d08-8109-3f0e864964e0` | 2048×2048 PNG, eight steps, 76.260 seconds with different loading/cache conditions |
| Anima comparison — project `fbb384c70a5e48b39a9eba6c227374eb` | Two seeds completed; candidate choice remains open |
| Anime 2× finish — `1754de82-4114-4227-963a-c2a9c0534c16` | Saved setup restored and generated an upscaled PNG with source lineage |
| Timed Godot export — project `d62777fdd019462b99d28357e61393b8` | Actual 64×64 import/playback, 120/80/120/160 ms, anchor [32,32], 480.000003 ms cycle |
| Krita export — project `e563585717324f54aa57e6fc9bd9f773` | UI selected two originals; KRA retained both supplied layer names, reopened to 64×64 PNG and packaged source/receipts |
| Hinged prop — project `44cfa4a0b29a43098d6c7c7609ca6831` | CPU BLEND/GLB build; four visible parts, named hinge clip, four inspection renders; browser preview inspected |

These timings describe different tasks and cache conditions; they are not model
rankings. Successful execution does not establish pose fidelity, art acceptance,
commercial rights or a finished game asset.

## Backlog reconciliation

| Issues | Implemented here | Remaining research or acceptance |
|---|---|---|
| #1 | Cheap startup identity, cached discovery, decoded input validation, removed-reference feedback | Closed by the demonstrated behavior once this branch lands |
| #2 | Explicit isolated switching, visual/API HiDream recipes, concept and reference runs | Controlled higher-step comparison; upstream warning remains documented |
| #9 / #26 | Existing pinned bundle library; model paths and scoped execution evidence retained | Further provenance/terms intake, Hunyuan-specific applicability; H3 confirmation does not cover another provider |
| #10 / #22 | Trusted catalog execution, one-axis comparisons, root budgets, durable attempts, branching, source packs | Full accepted character-pack vertical slice; generic arbitrary-stage execution is not enabled |
| #21 | One/two/three role-reference graphs and UI, reference hashes and preview | Actual one/two-reference renders, controlled pose/identity acceptance |
| #11 / #18 | Isolated H3 loader and bounded construction probes; exact known prompts retained | Successful video baseline before cache/seed-hunt claims |
| #12 / #13 | Existing working short Wan image-to-video route and typed controls | Shot continuation/reshoots, LTX/VACE comparisons and measured temporal refinement |
| #14 / #23 | Matched anime adapters, reference atelier, native KRA save/reopen | Interactive Krita diffusion, layered puppets and in-between studies |
| #15 / #24 / #25 | Godot sprite/GLB adapter, timed playback, authored articulated Blender baseline | Khronos validation, gameplay collision/rig stress tests, automatic part/rig experiments and cleanup-effort comparisons |
| #16 / #17 | Workspace, Experiments, environment and native-export controls | Remaining roadmap items above; no blanket completion claim |

The exact Seed Hunter v1.6 graph remains preserved. Its inspected dependency
report identifies 24 unresolved node classes, the int8 video VAE, latent upscaler,
TAE and RIFE weights. Installing those packs would not establish that H3 runs on
this PC. The current Wan recipe is an available short-motion alternative; it does
not implement Seed Hunter continuation, native audio or latent upscaling.

Independent review found and fixed native restart recovery and a Krita snapshot
provenance race. One lower-priority limitation remains: failed Krita logs are
retained on disk but are not exposed as downloadable project artifacts. Native
source directories are never erased automatically. The finished worker checkout
was removed after its commits were integrated and pushed; all its ignored runtime
receipts were copied into `.runtime/worker-survivors/krita-roundtrip-20260911/`.

[HUMAN_TODO.md](../HUMAN_TODO.md) contains the optional creative choices. None were
inferred or checked off. No Buzz was spent; the current installation needs no
additional disk space for the completed work.
