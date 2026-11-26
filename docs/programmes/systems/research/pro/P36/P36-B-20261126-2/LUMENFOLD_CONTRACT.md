# P36-B-20261126-2: Lumenfold contract notes

## Scope and source identity

All Lumenfold source was read through the GitHub connector. The authoritative repository is `Chris0Jeky/lumenfold`, not `lumenfold-showcase` or `lumenfold-open`. The pinned main revision is **`19d86763944e842cbce6a3b6ae13f7abc1464b37`**, authored 26 November 2026 at 22:52:36 UTC. The twenty retrieved source blobs were checked locally; [LUMENFOLD_SOURCES.json](LUMENFOLD_SOURCES.json) records their immutable URLs, Git blob identities, byte counts and SHA-256 hashes. These external source files are not copied into this branch. Every local source copy was checked against its Git blob identity.

Studio guidance read from its current `0270760a3d4fd9e005a1788bba59d8242b77c2f4` snapshot: `AGENTS.md`, `CLAUDE.md`, current-state head, open `HUMAN_TODO.md` headings/items, operating model, Codex readme/active pointer and tier declaration. No app, catalog, native runtime or existing production files were edited.

The prior P36 lab is **open, unmerged Studio PR #2046**, branch `pro/P36-B-20261125-1`, head **`80b274e8dde6b0333c4d39a9473f6e15e41f38e1`**, with the same Studio base. It already contains the eight-stage receipt graph, synthetic sheet scorer, draft exporter, fixed schema and 84-test proof. It is an explicit unmerged source dependency, not current Studio main. GitHub code search on Studio main found no P36 prototype; PR/branch search found that prior run and this new run, plus an unrelated documentation PR mentioning P36.

Lumenfold **issue #3175 is open**, created 25 November, last updated at `2026-11-25T02:32:12Z`, with zero comments at capture. It already owns exact-concept/ancestry admission and native acceptance. Use an addendum there; do not create a duplicate import issue or imply adoption.

## Controlling orders and lane ownership

- The current ORDERS head is **26 November 2026, 21:24**, proportionate review/CI. P35/P36 triage explicitly belongs to Studio agents. Pro adoption remains a proposal accepted or declined by the named lane in a PR comment; Pro contributions do not edit shared cores.
- The 14 November cast-study stop remains: no new cast images, sheets, turnarounds or study. The Characters topic still stops general hero 3D generation. No new generation is part of this run.
- The 20 November entry identifies accepted cast demos as **Kiri A4 and Sable A2**, with a separate Sable portrait for the near-eye read and a paired wide for the exchange. It gives no exact A2 input bytes or current Workspace acceptance record.
- `packs/sable/pack.json` remains a legacy **draft**, `default_variant: slender`, variants `slender`/`curvy`, with two **posted**, not judged, Versus rows. `packs/kiri/pack.json` is also draft/slender with no Versus result. These files do not establish the A2/A4 anchor mapping.
- `lf-characters-3d` owns asset/rig/intake work; `lf-anime-look` owns the Unreal look/face/outline/secondary-motion evidence. Character 3D lane notes say the old hero-model work is parked. No original/private owner-model path was opened or listed.
- Studio's unaddressed owner items, including paused illustration work, parallax judgment, character-sheet/native review and art direction, remain unchanged. This software prototype supplies none of those acceptances.

## Exact pack-v1 contract

Canonical schema: [`packs/pack.schema.json`](https://github.com/Chris0Jeky/lumenfold/blob/19d86763944e842cbce6a3b6ae13f7abc1464b37/packs/pack.schema.json). Git blob: `fd00e2fb6de69b80b3b0756ab89fcbfb32945b37`. SHA-256: `9892f716abfff35a85088c5b5c798a8ae38ddbff50f1e67845f799c7af16a28a`. This is byte-identical to the prior P36 schema.

| Field | Exact requirement |
| --- | --- |
| `schema` | Literal `lumenfold.pack/1`; JSON Schema Draft 2020-12 |
| Required roots | `schema`, `id`, `display_name`, `status`, `profile`, `style`, `files`, `models`, `expressions`, `portraits`, `voice`, `animations`, `versus` |
| Extensions | Root properties beginning `x-` are allowed. Most defined blocks also allow them; arbitrary non-extension root keys are refused. |
| `id` | Regex `^[a-z][a-z0-9-]{1,31}$`; validator also matches the directory name. |
| `status` | `concept`, `draft`, `playable`, `retired`. Draft may lack store bytes; playable requires real files unless explicitly metadata-only. A schema pass is not engine or art acceptance. |
| `profile` | Required `full_name`, integer `age >= 18`, `pronouns`, `role`, nonempty `personality` array, `bio`. Optional `height_m` 0.5–3 and repo-relative `bible`. |
| `style` | Required nonempty `tags`; optional `figure`, named `#RRGGBB` palette, notes. |
| `files` keys | Regex `^[a-z0-9][a-z0-9_.-]*$`. |
| Every file record | Required relative `path`, lowercase 64-hex `sha256`, integer nonnegative `bytes`, `source`, `licence`, `commercial` = `yes`/`no`/`unknown`. Optional `made_by` and `restrictions`; no arbitrary other fields. |
| File paths | Forward slashes; no absolute slash, backslash, colon or `..` segments. Store is `$LUMENFOLD_ASSETS/packs/<id>/` (default asset root `E:/Lumenfold-assets`). The Studio prototype adds stricter portable path guards. |
| File references | Every recursively encountered object member named **`file`** is a key in `files`, even inside `x-` extensions. Use `family_sidecar`/`handoff_sidecar`, not unregistered `file` keys, for metadata sidecars. |
| 3D model references | `vrm: {file, version?}` where version is `0.x`/`1.0`; `glb: {file, joined?}`; `fbx: {file, unit_scale?}`. `joined=true` means one skinned mesh, not merely valid GLB bytes. |
| Skeleton declaration | `vrm-humanoid`, `ue-mannequin`, `mixamo`, `custom`, `none`. Declaration alone proves none of the decoded rig. |
| Engine settings | `models.ue` and `.godot` are consumer-owned open objects; `from`, when set, is `vrm`/`glb`/`fbx`. |
| Toon | `models.toon: {file}` points at a material-name-to-look JSON: base/shade, band parameters, rim, outline, emission and alpha facts; textures stay in GLB. |
| Expressions | Expression names map to arrays of `{morph: string, weight: number 0..1}`. |
| Portraits | Mood names map to `{file: file_key}`. |
| Voice / animations | Voice requires `engine`, `voice_id`; animations requires `set`. Preserve the owning lanes' data. |
| Versus | Owner-only recorded judgments. Empty until judged; entries require `contest`, `question`, state `posted`/`judged`. No agent taste or synthetic acceptance goes here. |
| Variants | A selected variant replaces each named block wholesale, except `style` deep-merges. `validate_pack.load` applies it; all merged variants are schema-validated. |

The validator also checks all reference keys, unique recorded paths, default-variant existence, model presence for every non-concept effective pack and resolved path containment. `--files` checks byte counts and SHA-256. `--metadata-only` deliberately bypasses bytes, including playable status, for public unlinked source paths. It does **not** establish identity, current Workspace review state, acceptance authority, native rig compatibility, whole-chain licence clearance or playability.

## Existing producer and consumer behavior

`pipelines/characters/intake_model.py` is an **already rigged model** route. It accepts VRM/GLB/FBX; loose `.gltf` side files are refused. Blender produces one skinned mesh in metres facing -Y, reports skeleton/morphs, validates expression names, renders portraits, and extracts VRM 1.0 MToon. VRM 0.x expression mapping exists, but its MToon extractor returns an empty map for VRM 0.x. The route preserves profile/style/voice/combat/animations/Versus and merges consumer-owned engine settings. A custom skeleton only prints a note, so completion is not proof the game can retarget it.

Its publication is not a verified rollback transaction: it builds `.staging`, checks the document, renames the old folder, renames staging to final, deletes the old folder, writes `pack.json`, then performs full-file validation. A manifest-write or final-validation failure can occur after old bytes are removed. For an existing playable pack, pre-swap `validate_doc` also tries to validate the new hashes against the old store. The README's general promise that a failed rerun leaves the old pack untouched is broader than this code proves.

The current Unreal entry point is [`games/world3d/tools/import_packs.py`](https://github.com/Chris0Jeky/lumenfold/blob/19d86763944e842cbce6a3b6ae13f7abc1464b37/games/world3d/tools/import_packs.py), Git blob `8fccf011d915e41733edacef1dec023946c99a38`, SHA-256 `381f704c73445ba7733cee46619814fcfbe117d1b5eae29c2fe52067b27fb44a`. Source inspection shows:

1. It reads raw JSON without invoking the pack validator or checking Studio sidecars. It skips `concept` only; draft is not an admission barrier, and retired also passes that status filter.
2. It reads top-level model data directly, without `default_variant` application. It prefers GLB then VRM; it does not follow `models.ue.from`, and an FBX-only manifest does not supply its `glb` field.
3. A GLB without proven `joined:true` is replaced by an external `<JOINED>/<id>.glb`. A VRM also takes that joined route. The base P36 exporter correctly does not invent `joined:true`, so its output is not directly import-ready.
4. It only retargets `vrm-humanoid`, then constructs fixed `J_Bip_*` chains. The schema's mannequin/mixamo/custom options are not all supported by this importer.
5. It deletes an existing `/Game/Packs/<Id>` directory before importing the new mesh. The game's pack list and retarget map are written later. AnimeLook failure may raise only after those writes.
6. Its AnimeLook path uses face SDFs and original VRM information; it does not consume the generic `models.toon` JSON as a guaranteed look contract. Kawaii missing chains/plugin or build failure can print and continue. Missing SDF falls back to the old toon path. Therefore successful pack/file checks do not prove requested AnimeLook or garment motion.

The anime lane requires matched game-frame evidence: SceneCapture does not reproduce eye adaptation. It records a prior wrong assumed axis conversion and calls for fitting signed axes against the actual imported reference pose, failing over 1 cm. Character lane evidence calls for 24 consecutive move frames. These remain proposed native acceptance requirements, not results of this run.

## Narrow new implementation

The new `export_guard.py` wraps the retained unmerged exporter with `build_guarded_manifest(family, asset_root, metadata, *, release=False, intended_use=None)`.

- Before exporter deduplication, repeated active path/hash/size declarations must have equal effective `source` and the **complete** `licence` object. The guard refuses either ordering of conflicting commercial facts, changed licence name, terms source, restrictions or other recorded licence facts. It does not infer a conservative licence merge or an owner decision.
- Omitted artifact source is compared using the upstream's actual Workspace/asset fallback locator. Identical path spelling/case and content identity are also required. Selected family, concept and stage hashes remain unchanged; metadata receives its own digest in the declaration.
- The manifest remains a `draft` under unchanged pack v1. `x-studio-character-pipeline.consumer_admission` is `las.lumenfold-consumer-admission/1`, sets `current_direct_import_allowed: false`, requires staged validation and calls joined topology and rig compatibility unverified. It records the inspected consumer revision.
- This is **a declaration the proposed consumer must enforce**, not a change to Lumenfold. Dropping the file into a root scanned by the existing importer would still bypass it. The main run adds separate Studio authority preflight; this helper alone does not authenticate owner assertions or implement a live dispatch boundary.

Focused verification: 12 synthetic tests passed, no skips/errors, 15.254 seconds. They reproduce the prior exporter emitting `commercial: yes` when a reused artifact later says `no`, then show the new wrapper refuses before calling that exporter. Exact-schema validation passes. The supplied current `validate_pack.validate_doc(..., check_files=True)` accepts the guarded synthetic manifest and rejects changed fixture bytes. No Blender, Unreal, real model/character generation, owner acceptance or licence clearance was executed.

## Adoption recommendation

Keep #3175 as the importer owner. Admit only through a new staged adapter that rechecks live Studio authority, all selected ancestry and exact bytes; resolves the selected variant and true consumer model path; normalizes an already rigged model without inventing a rig; validates native morphs/materials/axes; and retains the previous accepted pack until promotion succeeds. Treat receipts and engine artifacts as separate staged outputs. A subsequent native receipt must bind the admitted handoff hash, source model/texture hashes, engine/build identity, actual import settings, captures and owner acceptance. Synthetic families are software-test inputs only.

The next real character action remains resolving exact Sable A2 source and acceptance mapping. The legacy slender pack and a matching filename are not a substitute. Keep generated, inspected, accepted, intended-use licence-cleared and native-playable states separate.
