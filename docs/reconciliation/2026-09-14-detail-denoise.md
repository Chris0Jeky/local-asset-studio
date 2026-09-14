# Preserve the authored hand strength in Anime Detail Fix

Issue [#254](https://github.com/Chris0Jeky/local-asset-studio/issues/254), advancing
[#14](https://github.com/Chris0Jeky/local-asset-studio/issues/14). Inspected base
`20c46dd45044a6f9193b3e562df5bee4e5fc8912`, 14 September 2026. This is independent
of the #253 coordinator correction and active Create/Prompt/repair UI work.

## Historical evidence checked before choosing a fix

The tracked `experiments/curated/anime-fantasy-atelier/anime-detail-fix-noob-hands-recipe.json`
contains empty controls and the actual submitted graph for prompt
`3eeba334-6161-4f84-bd36-de0c888c0d74`, job
`14caa4fb-5999-497f-8b73-0bb2562229df`. Node 12 has denoise 0.40 and node 13 has
0.45. This resolves the issue's uncertainty about whether the recorded successful
trial used a shared UI value. It did not.

Retained SHA-256 identities (none of these files changed):

| File | SHA-256 |
| --- | --- |
| Authored `workflows/api/anime-detail-fix-api.json` | `7b7b7e1d3108661aba9314519af5cb3a0a43ebde96a930015352f016151dc150` |
| Recorded no-control recipe | `f4f15f5add23bb2284cf6bb4c37969b1bdd1676b1512f2ea26fc4f9029878f9c` |
| `anime-detail-fix-gentle-evidence.json` | `87b7314288a3071aafc8ff0a0b26fd09bca6244da1245b34f21a8d0baf922200` |

The 0.30/0.30 Gentle trial and its failed hand correction remain historical
results. They are not evidence for the new 0.30/0.45 variant. This session did not
rerun or independently inspect the historical neural outputs.

## Decision

Use option 3 from the issue: remove only the hand node from
`bindings_extra.denoise`. The face follows the existing Denoise control; hands
retain their authored 0.45. This restores the exact authored pair when the
browser sends its normal face default of 0.40. It avoids inventing a second
control protocol across concurrent UI/SDK/setup owners or changing a previously
executed graph merely to match an accidental fan-out.

The description explicitly calls Denoise **face-only** and the stage labels name
both scopes. Rename the variants to **Lighter face (face 0.30 / hand 0.45)** and
**Stronger face (face 0.55 / hand 0.45)**. Neither claims a measured quality win.
A face value of zero still leaves hand repainting at 0.45: this is not a way to
preserve hands. A different hand value needs an explicitly separate workflow
editing node 13 in ComfyUI; do not silently mutate an old saved recipe.

Seed, steps, CFG, sampler and scheduler still fan out to both passes. Batch seed
expansion stays synchronized. The hand prompt stays authored; source/reference,
model, detector and export bindings are unchanged. No API/visual graph bytes,
model pin, shared server control lists or installed-node behavior changes.

The changed preset is marked `verified: false`. Its historical execution note
is retained with the changed binding date and **not rerun** limitation. Static
Prepare tests do not requalify neural execution or art acceptance.

## Compatibility and current flow

Open the current recipe, review its description/variant and source, then preview
or explicitly generate through the existing Studio flow. The Denoise value now
changes only the face. The current controls with an embedded new graph round-trip
normally. The old shared-value recipe's full embedded graph remains its authority:
`Studio.check_recipe()` refuses to certify it as the current preset because the
hand input differs. Its response directs the user to the original embedded graph
or a deliberately new experiment. No old recipe, setup or output is rewritten.

A settings-only setup lacks an embedded graph to prove old output equivalence;
loading those values is a proposal for the current preset, not an exact replay.
The new variant names and description disclose this change. Preserving a historical
0.30/0.30 or 0.55/0.55 run requires its original graph, not the new preset mapping.
A general fan-out-default validator and independent hand-control UI are outside
this scoped fix; neither is needed to silently unify these intentionally different
strengths. Do not promote the broader #14 character pack from binding tests.

## Proof and runbook

```console
python -m unittest discover -s tests -p test_detail_denoise_binding.py -v
python scripts/validate-repo.py
python -m unittest discover -s tests
```

Six methods use the real shipped catalog, graph, `Studio.catalog`, `prepare`,
`check_recipe` and batch seed expansion. They verify the default pair, face-only
numeric/string values, all named variants, the original submitted graph, exact
old-recipe refusal and the remaining synchronized controls. Preparation/inspection
create no job, queue item or Comfy request. The captured original graph and
historical evidence files remain byte-identical.

The final baseline fixture run completed six methods with nine failing
assertions/subtests; all six pass after the catalog correction. An earlier fixture
passed the authored example filename as though it were an uploaded file, correctly
hitting the upload-name guard. The corrected fixture omits that unstaged file
control, as required; no upload policy was relaxed. Full-suite and hosted results
are recorded separately with exact branch heads. No new browser interaction,
installed Impact-Pack schema check or neural quality result is claimed.

The oldest #2/#3/#9/#10 workstreams were reconciled before this slice: switching,
intake, schema and recovery infrastructure were retained, while their actual
native/creative acceptance stays open. #253 is this pass's first execution fix;
#254 is the next scoped older atelier defect. HUMAN_TODO is untouched: the
already-supplied q5/q6 decisions belong to #277/#278. Rollback is a scoped catalog
and copy revert, never deletion or rewriting of historical recipes.
