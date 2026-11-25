# Adoption proposal — P36-B-20261125-1

**Adopt the offline evidence tools first. Activate live Studio admission and Lumenfold import only after the named owners prove the gates below.** This proposal needs an accept/decline comment from the adopting lane; delivery of the prototype does not establish adoption. P35/P36 belong to the Studio’s agents under Lumenfold `docs/ORDERS.md`.

Import-side tracking: [Lumenfold #3175](https://github.com/Chris0Jeky/lumenfold/issues/3175).

## Scope and first character

Start with **existing Sable A2**. Resolve the exact accepted art, retained native source, model/build identity and acceptance evidence before choosing any transformation. Record their locations, byte counts, SHA-256 values, Workspace IDs where present, and the authority linking them to “A2”. None of those native identities is established by this sandbox.

The 14 November cast-image/study hold remains relevant. `pipelines/characters/fighter/ROUTE.md` records narrowly authorized finishing of owner-provided Kiri/Sable inputs on 19 November; the 20 November order identifies accepted Kiri A4/Sable A2 demonstrations. These records do not establish a general generation restart. The supplied `packs/sable/pack.json` is a legacy draft with `default_variant=slender`; that label is not an A2 receipt. Missing inputs leave the pilot blocked. There is no default generation, alternate-character substitution or access to `owner-models/`.

## What exists, and what still needs adoption

The implementation remains under `prototypes/pro/P36/P36-B-20261125-1/`. It provides bounded family receipts, direct accepted-concept comparisons, required-view/feature gates, ancestor invalidation, fresh production media checks, explicit uncertainty resolution and draft pack export. `prove.py` exercises synthetic fixtures and can call the actual Lumenfold validator with file checks. It submits no generation and performs no native import. (`pipeline.py`, `consistency.py`, `pack_export.py`, `prove.py`.)

No live Studio scheduler, Workspace acceptance store, app endpoint or catalogue was changed. The prototype’s `actor="owner"` and evidence references are caller assertions. **Hashes detect changed records; they do not authenticate acceptance, establish current revocation state or prove a job ran.** Live integration must supply that authority.

## Numbers this adoption should move

| Owner | Current P36 evidence | Next target |
| --- | --- | --- |
| Studio agents | 0 exact A2 source/acceptance mappings recorded by this run | 1 verified mapping to exact bytes and current acceptance scope |
| Studio agents | 0/16 synthetic invalid cases admitted; real rate unmeasured | Preserve 0/16; target 0 critical false passes on an explicitly counted, held-out real set |
| Studio agents | 0 live adapter negative tests implemented by this prototype | 7/7 listed authority/media/uncertainty cases reject before queue/export |
| lf-characters-3d | 0/8 real P36 stages with complete receipts | 8/8 when each preceding gate actually passes; no promotion for a failed stage |
| lf-characters-3d | 0 native imports measured here | 1 staged import with zero contract errors and passing interruption/rollback checks |
| lf-anime-look | 0 real P36 playback captures | 1 accepted representative sequence, at least 24 consecutive frames when motion is claimed |

Zeros describe this run's evidence, not absence of existing work in either repository.
The eighth prototype stage (`unreal`) accepts handoff readiness before export; 8/8
receipts is not native import/playback acceptance. The consumer records that separate
downstream gate after import, under issue #3175.

## 1. Studio agents: reproduce the software contract

From the Studio repository root, using a new output directory:

```bash
py -3 prototypes/pro/P36/P36-B-20261125-1/prove.py --output .runtime/pro/P36-B-20261125-1/adoption-proof-001 --lumenfold-root ../lumenfold --check-evidence prototypes/pro/P36/P36-B-20261125-1/EVIDENCE.json
```

This CLI is implemented. The `../lumenfold` path must point to your existing checkout and contain the actual `pipelines/characters/validate_pack.py` and `packs/pack.schema.json`. The command writes synthetic assets, test results, deterministic evidence, hashes and separate environment/timing information. A test-only check is available as `prove.py --tests-only`. Reusing an existing destination is refused; inspect an interrupted run before starting another.

**Gate:** zero test failures/errors; expected outcomes for every labelled synthetic case; all drift/stale-ancestor descendants blocked; actual consumer `check_files` passed. Retain the validator/schema hashes and the environment’s test/skip counts. Synthetic false-pass counts describe the software fixtures only. The timed metadata gate excludes disk I/O and cannot be reported as native workflow latency.

## 2. Studio agents and lf-characters-3d: resolve the authoritative Sable anchor

Once the existing asset and Workspace IDs are known, these read-only Studio commands are implemented:

```bash
py -3 -m studio_workflow.asset_family_client inspect <SABLE_ASSET_ID> --workspace <WORKSPACE_ID> --children --privacy regular
py -3 -m studio_workflow.asset_family_client recall <SABLE_ASSET_ID> --workspace <WORKSPACE_ID> --privacy regular
```

The client returns observation-only lineage/recipe envelopes with `media_bytes_verified=false`; it does not authorize execution. Resolve any reported lineage gaps or truncation through the retained records before proceeding. (`studio_workflow/asset_family_client.py`, `asset_family.py`.)

**Gate:** an evidence-backed mapping from Sable A2 to exact accepted art and retained native bytes; explicit current owner acceptance; complete required ancestry; the original recipe and any known job/prompt IDs; licence facts and intended-use decisions recorded separately. Resolve contradictory or missing records instead of assigning acceptance from a filename, a hash match or a successful command.

## 3. Studio agents: wire live admission and calibrate the rubric

This is **planned implementation**, not an enabled feature. Integrate the prototype with the existing Workspace/job authority before any native submission or export:

- Read current selected parents, acceptance/revocation events and review subjects from the authoritative store. Recheck immediately before submission and publication. A rejected, replaced, missing or stale required ancestor blocks every descendant, including cached outputs.
- Bind stage receipts to real Workspace asset/job IDs, exact media, full recipes and retained prompt IDs. Consult live uncertain-job history even when no output artifact exists yet. Recover the recorded attempt; do not resubmit it to obtain a cleaner receipt.
- Require fresh byte and pixel verification for production admission. Keep metadata-only assessment diagnostic. Preserve separate generation, inspection, acceptance and licence-use states.
- Make revocation, changed media, forged review subjects, wrong Workspace scope, missing views, one failed critical trait and unresolved upstream submissions executable negative tests through the live adapter. Required tests must reject before a job is queued or a handoff is published.

The implemented preflight can inspect a prepared, authoritative family without submitting work:

```bash
py -3 prototypes/pro/P36/P36-B-20261125-1/pipeline.py next --family <FAMILY_JSON> --stage turnaround --asset-root <PUBLIC_ASSET_ROOT>
```

A passing result is only one precondition; it does not override the cast hold or authorize generation.

**Calibration target:** zero observed critical false passes on a held-out set of **owner-labelled real candidates**, with sample counts, per-trait results and false rejections reported. This is a proposed target, not a measured result. Start with retained candidates and reviews. Freeze views, regions, tolerances, invariant features and permitted expression/outfit changes before evaluation; do not tune against held-out labels. Pixel agreement remains a proxy. A critical visual identity failure blocks progression regardless of aggregate score or owner-independent annotations.

## 4. lf-characters-3d: stage and inspect the retained native source

Inspect source format, skeleton, skinning, morphs, textures and dependencies first. Reuse `intake_model.py` for qualifying rigged VRM/GLB/FBX; its joiner requires one armature and skinned geometry. Raw unrigged geometry needs the existing fighter route first. Selecting or changing that route is native follow-up work, not an action taken by this proposal. (`pipelines/characters/README.md`, `blender/model_join.py`, `fighter/ROUTE.md`.)

After the import adapter stages an explicit candidate store, this existing check applies from Lumenfold:

```bash
py -3 pipelines/characters/validate_pack.py <STAGED_PACK_DIRECTORY> --files
```

Set `LUMENFOLD_ASSETS` to that staged store. The directory name must equal the pack ID. Require zero errors, preserved manual/engine-owned metadata, and successful interruption/rollback tests. Pack validation does not establish art acceptance or native engine compatibility. The exported `draft` status must never imply an Unreal asset path, successful import or playable character. (`validate_pack.py`, `packs/pack.schema.json`; issue #3175.)

For retained compatible study views and fit data, the verified diagnostic CLI is:

```bash
py -3 pipelines/characters/castcheck/castcheck.py <VIEWS> <STUDY> <OUTPUT> --fit <FIT_NPZ> --cameras <FROZEN_CAMERAS_JSON>
```

**Gate:** report silhouette, colour, face and deformation evidence against the resolved concept; inspect every blocking finding. `CASTCHECK ok` means scoring completed. Calibrate character-specific thresholds before declaring a pass.

## 5. lf-anime-look: prove the adopted bytes in Unreal

Native capture/import commands must be selected from the live lane’s verified current scripts; none was executed or invented here. Use offscreen proof under the current native lease rules. Compare matched cameras under game exposure, check toon/outline/face-shadow behavior, and inspect required expressions and secondary motion. Where movement is included, retain at least 24 consecutive frames. The lane’s existing axis-mapping check fails above 1 cm. (`docs/lanes/lf-anime-look.md`, `lf-characters-3d.md`.)

**Final gate:** exact imported hashes, native receipt, judged stills/clip, measured compatibility results, current identity acceptance and explicit intended-use decision. Any identity drift blocks descendants and adoption. Record the Studio and Lumenfold adopting commits plus the lane’s acceptance comment; keep native proof pending until those artifacts exist.
