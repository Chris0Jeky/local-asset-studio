# P36 character pipeline design and implementation plan

## Kill criteria first

Any failed, missing, uncertain, stale or incompatible required identity observation
against the exact accepted concept blocks the dependent stage. A good average cannot
cancel one failed critical trait or a missing view. No completed command, generated
file, agent opinion or model licence implies owner acceptance. An uncertain job is
retained, never submitted again by this tool.

**Goal:** connect concept, turnaround, expressions, outfit variants, mesh, rig, toon
materials and Unreal handoff through immutable Studio-side receipts, and export a
Lumenfold-compatible draft manifest only when its ancestry passes.

**Architecture:** a bounded offline sidecar over existing Workspace asset/job IDs,
not a second media store or generation runner. Every receipt binds media checksums,
the full recipe, references, parent receipt digests, concept digest, frozen policy,
independent evidence states and a reproducible consistency report. Re-evaluation
walks current ancestry rather than trusting a cached green badge.

**Tech stack:** Python 3.12+, standard library; Pillow only for explicit raster
measurements (already a Studio dependency). jsonschema validates every export
against the supplied Lumenfold schema; running Lumenfold's actual consumer validator
is an optional additional integration check. No third-party implementation is vendored.

**Spec:** the owner's P36-B-20261125-1 brief; this document fixes implementation
choices under the authority to take the lead. No additional approval is needed for
the offline implementation. New real asset execution and acceptance stay owner-run.

## Approaches considered and chosen

1. A neural embedding threshold alone is attractive but uncalibrated for this cast,
   costly to qualify on this workstation and blind to small asymmetric identity cues.
2. A free-form checklist alone is cheap but cannot remeasure pixels or detect stale
   references and permits aggregate scores to hide critical failures.
3. **Chosen by this run:** measured pixel-region differences plus explicit,
   provenance-labelled annotation checks, hard view/feature gates and independent
   owner acceptance. This is an auditable drift triage system, not a claimed visual
   identity recognizer. Future learned metrics can add evidence, never bypass gates.

## Existing contracts and integration boundaries

- `studio_workflow/asset_family.py` already projects Workspace lineage, multiple
  parents and gaps. `asset_family_client.py` is a bounded, read-only loopback client.
  Receipt references use those asset/workspace identities; no HTTP endpoint, SQLite
  table, browser event, installed runtime or catalogue is modified in this prototype.
- Character canon/study architecture already distinguishes identity, pose, costume,
  style, anatomy, not-visible and uncertain observations. Keep these distinctions.
- Lumenfold `packs/pack.schema.json` is pack v1 with `x-` extensions. Export real file
  sizes/hashes and actual licence facts; keep structured lineage under
  `x-studio-character-pipeline`. `models.ue` is an engine-owned request, not execution.
- `pipelines/characters/validate_pack.py` proves structure and optional bytes, not
  identity or legal clearance. Existing cast/fighter metrics are evidence inputs,
  not acceptance decisions. The import-side change belongs in a Lumenfold issue.

## Records and gates

Each family has a Workspace ID, character ID, frozen policy, immutable receipt map
and active stage heads. Each stage has exact parent heads. Replacing an ancestor
does not rewrite history; its descendants become stale and block until replaced.
The root concept is independently accepted and every descendant compares directly
to it, not merely to the previous stage (which would compound gradual drift).

Generation (`planned`, `completed`, `uncertain`, `failed`), inspection, acceptance and
licence are distinct fields. Evidence from fixtures is always explicitly synthetic.
The real first-character plan contains no completed generation or accepted artifact.
The tool never upgrades these states from a score. Licence records retain terms,
sources, intended use and owner decision separately; draft export preserves unknowns
while release export requires explicit clearance for the requested use.

The fixed stage graph is concept -> turnaround -> expressions/outfits -> mesh -> rig
-> toon -> Unreal handoff, with direct concept references throughout. Expressions and
outfits may be independent children of turnaround, but mesh requires both. A bad
unselected alternative does not poison a selected branch; replacing a selected head
does invalidate dependent receipts. The prototype has one active receipt per stage;
an outfit receipt can contain a bounded set of named variants.

Frozen policy owns mandatory views, pixel regions, tolerances, traits and allowed
variation. Candidate data cannot remove eyes from a frontal check, change a threshold,
select easier crops or authorize occlusion. Side/back views have their own declared
coverage. Missing required evidence blocks; a view with no comparable identity cues
cannot pass. Expression and outfit variation does not waive invariant identity cues.

Pixel means are measured from decoded RGB/RGBA images, with alpha/coverage checks.
Annotated ratios and categorical traits record `human_annotated` or `fixture_truth`;
binding an annotation to a media hash detects stale claims, not dishonest annotation.
The report states `perceptual_identity_verified: false`. Owner acceptance is an
independent required gate, never generated by the scorer.

## Global constraints

- User-specified base `0270760a`, branch `pro/P36-B-20261125-1`; no main push or merge.
- All committed implementation in this run directory; reports in the matching
  `docs/programmes/systems/research/pro/P36/P36-B-20261125-1/` directory.
- UTF-8/LF; each file <300 KB; aggregate <3 MB; zero generated character images.
- Runtime fixtures and regenerated evidence under `.runtime/pro/P36-B-20261125-1/`.
- GitHub writes through connector, <=10 files per commit; RUN_STATE checkpoints.
- No installed ComfyUI edits, dependency upgrades, GPU generations or automatic retry.

## Review focus

1. One bad view, hidden critical feature or NaN must fail despite high aggregate score.
2. Replaced concept, changed recipe/media or forged cached result must fail downstream.
3. Generation, inspection, acceptance and licence must never promote each other.
4. Export must refuse path traversal, symlinks, duplicate paths and changed file bytes.
5. Fixture success must never become a real accepted character or playable-engine claim.

## Implementation tasks

### 1. Receipt graph and state separation

Files: `pipeline.py`, `test_pipeline.py`, `fixtures.py`.
Interfaces: canonical JSON/digest; create family; prepare/record receipt; assess stage;
plan next stage; replace head without changing immutable history.

- [ ] Write and run failing tests for missing identity evidence, independent states,
  stale parents/concept and uncertain submission barriers.
- [ ] Implement deterministic bounded records; retain recipe/reference/asset identity.
- [ ] Re-run all prototype tests; checkpoint source and RUN_STATE via connector.

### 2. Sheet consistency scorer

Files: `consistency.py`, `test_consistency.py`, `fixtures.py`.
Interface: score frozen concept policy against SHA-bound per-view observations;
measure raster regions from files beneath an explicit root; return blockers and
per-feature/per-view metrics, never an acceptance decision.

- [ ] Write tests for identity drift, missing/duplicate views, invalid numbers,
  candidate threshold changes, insufficient alpha coverage and allowed variation.
- [ ] Implement hard gates, deterministic measurements and provenance disclosure.
- [ ] Compare against a deliberately weak mean-score baseline on synthetic cases.

### 3. Manifest export and evidence command

Files: `pack_export.py`, `test_export.py`, `prove.py`, compact evidence and hashes.
Interface: validate all active ancestry; bind files to receipts; export pack v1
draft JSON + handoff receipt under `.runtime/`; no native import or network call.

- [ ] Test tampering, traversal, symlink boundaries, licence state and fixture labels.
- [ ] Validate output against the supplied Lumenfold schema and actual validator.
- [ ] One command runs tests, reproduces deterministic fixtures/metrics and hashes.
- [ ] Retain software environment/timing separately from deterministic outputs.

### 4. Adoption and closeout

Files: `README.md`, `ADOPTION.md`, `first_character.plan.json`, report and sources.

- [ ] Publish routes/models/licences and exact owner acceptance gates for one character.
- [ ] File Lumenfold import issue with contract gaps and numeric acceptance criteria.
- [ ] Run fresh-context review, fix substantive findings, re-run decisive checks.
- [ ] Verify every README-named deliverable exists on branch, finish RUN_STATE header,
  update PR with exact scope/commands/limits, then mark ready without merging.

## Verification scope ruling

The sandbox contains connector-read source slices, not a cloned Studio repository.
Run prototype tests and the real attached Lumenfold pack validator locally. The
unchanged Studio app/catalog are additionally covered by the existing hosted
`Check studio` workflow; retain exact CI identity and result, including failures.
Do not call a partial local test discovery a full Studio-suite pass.
