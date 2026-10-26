# MOSS study results, 26 October 2026

**39 jobs completed, 39 unique prompt IDs and 39 distinct image hashes; no failed,
uncertain or repeated submission.** Every output has an exact exported recipe,
hash-bound receipt and full-image/face/hand inspection. Generated files stay outside
Git in `E:/local-asset-studio-labs/moss-20261026/evidence/`; `gallery.html` there
includes every image and links to its full-size original and recipe.

## What ran

MOSS SFT int8, Qwen3.5 9B int8 and the small FLUX.2 VAE ran on the isolated
ComfyUI v0.42.1 backend, commit `63be2f9b82ad0dac88a7ceaa28a9cf3154125a18`,
port 8198, RX 9070 XT, shared unchanged Torch 2.9.1+rocm7.2.1 environment.
The template's raw SHA-256 is
`92dc6168d5501b90a5c8e1e23fc05512207c7a5b53b76aa31fe6af8ec12fb4e0`.
All pictures use 1024×1536, 30 steps, Euler / sgm_uniform, CFG 3 and empty negative.
Model hashes and the submitted graph travel with the recipes; sampler, resolution
or adapter settings outside these comparisons are not qualified by this run.
Retained recipe JSON uses LF newlines for Git portability: `recipe_sha256` hashes
those retained bytes, while `export_sha256` hashes the original Windows export on E:.
The top-level `plan_sha256` likewise hashes the LF plan in Git and
`plan_export_sha256` retains its local export hash. Per-run Production plan hashes
remain the runtime's own identities. No JSON field or submitted graph was changed
by newline normalization.

| Track | Design | Agent pre-review | Median job time |
| --- | --- | --- | --- |
| Original adults | 2 briefs × 2 seeds × 6 treatments = 24 | 10 keep, 14 fixable | 50.814 s |
| Franchise pilot | 3 characters × 5 independent variants = 15 | 7 keep, 8 fixable | 51.094 s |

These are visible-label judgments, not a blind ranking or owner acceptance. Six
original-character results also received an independent second judgment. The
strict full-body outfit/hand requirements differ from the older 70-image study;
their keep rates cannot be compared. Job timing excludes Production preparation
and repeated model hashing; cache state and a shared PC preclude a speed ranking.
Original-track times range from 48.544 to 86.810 seconds, including model loads.

## Adapter lessons from the original-character comparison

- **mikkoani at 0.9** most clearly shifts these prompts toward graphic ink lines,
  controlled shading and mature fashion illustration. It is a useful starting
  recipe here, not an across-model quality winner.
- **Reverse 1999 at 0.9, with versus without `reversesty`:** the matched outputs
  look similar; this small comparison does not show a consistent quality gain.
  The author trigger belongs in metadata even when its local effect is subtle.
  Raising the triggered strength to 1.2 changes outfit/composition without reliably
  fixing anatomy. The author's er_sde / CFG 5 settings were not tested here.
- **Impasto at 0.25 over mikkoani 0.9** softens contrast and adds hatching/texture.
  It did not clearly improve the strict brief and sometimes moved coverage or
  composition. This low secondary blend is our experiment, not the author's
  recommended standalone strength.
- Full-body free hands show thin/merged fingers on one seed; the second is cleaner.
  The requested short cape repeatedly becomes long. Portrait/gloved hands are
  cleaner in this sample, but multiple scene variables changed, so gloves are not
  established as the cause. Inspect source pixels before choosing a keeper.

## Recognition and adaptation from the existing character roster

The pilot selected adult main-story Tifa, adult Yor, and adult-presenting android
2B from `presets/wildcards/nsfw_character.txt`; it did not expand the mixed roster.
The [plan and primary sources](README.md#franchise-recognition-pilot-requested-during-the-study)
record the adult-version boundary and canonical art anchors. No character LoRA or
reference picture was supplied. Only the style variant uses an adapter (mikkoani 0.9).

| Character | Name-only recall and explicit description | Independent adaptations | Agent verdicts |
| --- | --- | --- | --- |
| Tifa | Name alone recalls white top, suspenders/skirt, arm guards and red boots; description refines the same design | Mikko changes linework. Seated pose crosses knees, not requested ankles. Fuller-bust wording has modest chest effect and clearer hip/leg fullness | 4 keep, 1 fixable |
| Yor | Name alone recalls black/red dress, rose headgear, red eyes, boots and even unrequested needle weapons | Mikko has stronger lines but obscures one boot. Seated pose crosses knees. Fuller-bust variant is somewhat fuller while retaining the main outfit anchors | 3 keep, 2 fixable |
| 2B | Name alone recalls white bob and black embroidered dress/boots but misses eye-cover and beauty mark; explicit description recovers those in the baseline | Mikko partially loses eye-cover. Seated pose crosses knees. Fuller-bust result changes little and duplicates the beauty mark. All five retain a skin-visible chest panel despite the opaque-clothing instruction | 0 keep, 5 fixable |

All 15 remain non-explicit and adult-presenting in inspection. A coverage-instruction
miss is still a defect even when the image is non-explicit. Covered eyes are not
graded for color. No pose/depth/reference input was supplied, so rubric control is
not applicable. The fuller-bust and style variants each branch from the described
baseline; they are not a combined style/body/pose experiment.

Name recall demonstrates learned name-to-design associations. It cannot identify
particular training images or prove training-set membership. One seed per character
does not establish consistency, and different body types remain only partly controlled.

## Reuse and next bounded comparisons

Three executed control sets are available in `presets/recipes.json`: the mikkoani
evening portrait, Tifa name-only recall and Yor fuller-bust pilot. Their evidence
blocks retain actual job/prompt IDs and specific limitations; none is marked accepted.
All 39 exact exports are under [recipes/](recipes/), with
[original receipts](receipts.json), [franchise receipts](characters-receipts.json),
[original judgments](judgements.jsonl), [second judgments](second-judge.jsonl) and
[franchise judgments](characters-judgements.jsonl).

The next queue is deliberately finite; saved plans are not submitted jobs:

1. **Body/style repeatability, 12 jobs:** [followup-plan.json](followup-plan.json),
   Tifa and Yor, two new seeds each, described baseline versus mikkoani 0.9 versus
   fuller-bust wording. Compare same-seed pairs and retain each character's face,
   outfit anchors and proportions separately. This tests whether the pilot repeats.
2. **Kromoss, eight jobs NOT RUN:** [kromoss-plan.json](kromoss-plan.json), gated by
   a complete checksum-verified checkpoint. Three short transfers ended this wave's
   attempt budget; [#1662](https://github.com/Chris0Jeky/local-asset-studio/issues/1662)
   retains the exact dependency. The DMD2 LoRA passed its source checksum but did
   not run. The preset remains unverified.
3. After those comparisons, choose a single demonstrated weakness for a new bounded
   test: 2B opaque coverage/eye-cover wording or an already-supported reference/pose
   route. Neither is installed or queued by this document. New community edit/control
   adapters need their own compatibility/provenance check, not inferred support.

## Engineering qualification and runtime disposition

Missing/empty MOSS text-encoder implementation is now rejected before a backend
switch can stop the healthy environment. Its regression failed before the fix;
48 backend-safety and 175 server tests pass. The browser fixture now supplies the
family observations used by the real UI; its missing-route regression failed first,
then three fixture tests and all 25 browser journeys pass, with zero page errors,
zero server tracebacks and zero generation submissions.

The final full suite passes **6,109 tests, 82 skipped, 1,061.452 seconds**, with
configured FFmpeg/ffprobe on PATH. An earlier run found a Windows catalog encoding
regression; restoring the existing JSON escape policy fixed it (16 focused checks
also pass). After integrating the AV output-verification base, the affected suites
pass 31 AV tests, 41 Studio AV tests (one skip), and three new output tests. Live
MOSS schema validation passes without submitting a graph. Fresh independent review
found no merge blockers in the readiness, fixture, pin and catalog changes.

Four six-stage Production plans remain `awaiting_review` (all allowances consumed
exactly once); all other 15 jobs are complete. Final snapshots show 39 completed
jobs, unique prompt IDs and an empty ComfyUI queue. The owned Studio PID 29932 and
MOSS PID 30520 were then stopped after command/root/create-time checks; ports 8191
and 8198 are free. Original output files remain under the installed ComfyUI
`output/Studio/` and complete copied evidence remains on E:. No paid credits were used.
No installed ComfyUI source or shared packages were modified.

`HUMAN_TODO.md` retains art acceptance and the Make-look choice. This milestone
records execution and agent findings; it makes no licensing-clearance or acceptance claim.
