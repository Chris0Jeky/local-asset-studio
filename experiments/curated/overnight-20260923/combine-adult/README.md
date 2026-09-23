# Combine routes re-proved on an adult original pair — 23 September 2026 (overnight lab)

**Why.** Every earlier proof of the four lead Combine routes used imported fan pictures of a student-canon character, which are
now excluded as inputs; the q-27/q-28 pre-reviews (PR #862) could not judge the routes. This run re-proves them through the
Studio (`POST /api/jobs`, the page's own path) on original adult characters only.

**Inputs** (no fan pictures; everything Git-safe):
- **Character picture:** the fantasy pack's three-quarter portrait, `Studio/Anima-v1-Baseline_00004_.png`: an adult traveller in a
  navy double-breasted coat with brass buttons, a teal scarf, long dark hair and gold earrings. It was staged through
  `POST /api/upload` as `906acc81…_adult-traveller-portrait.png`.
- **Pose picture:** a new WAI v17 render of an adult woman in plain black clothes on white, in a wide stance with one arm raised
  and the other reaching out (`pose-source-v2-2026092346`, prompt in `combine_adult.py`).
  - The first pose render (v1, a "side-view fencing lunge" prompt, prompt `cb972cab`) came out as a bent-over rear view with the
    hips as the focus. It was rejected and never used (`judgements.jsonl`).
  - Three v2 seeds were rendered; seed 2026092346 had the clearest silhouette.
- **Skeleton:** 17 joints read by eye from that pose picture (`keypoints-v2-2026092346.json`). It was drawn by the pose editor's
  own endpoint (`POST /api/pose/render`, renderer `studio.coco18-lines/v1`) into `46eee08a…_drawn-pose.png`.

**Method.** `combine_adult.py run`, 04:47-05:04 local. Four routes × three seeds (2026092341-43). Each route takes its
`continuation_prompt` with the three bracketed fills replaced: who, the clothes, and the pose in words (all in the script). The
character goes on *Picture to keep* (`last_reference`); the pose picture, or the skeleton for that route, goes in the pose slot.
- `combine-klein-9b-depth` at the default cut (100);
- `combine-klein-9b-depth` with `depth_cut` 88 (the review asked for 86-92);
- `combine-klein-9b-copypose` (Copy Pose LoRA; character as image 1);
- `combine-klein-9b-skeleton`.

Judged open, since the route is visible from the output file, with full-resolution face and hand crops (`judgements.jsonl`,
rubric R1-R7). Job IDs, prompt IDs and exact recipes are in `results.json` and `graphs/*.recipe.json`. Sheet:
`examples/overnight-20260923/combine-adult-sheet.jpg`.

## Results

| route | s per job (warm) | pose held | face and identity kept | verdicts |
| --- | --- | --- | --- | --- |
| depth (cut 100) | 80.6-94.8 | 3/3 | **1/3** | reject, keep, reject |
| depth, cut 88 | 82.6-82.7 | 3/3 | **1/3** | reject, keep, reject |
| Copy Pose | 104.6-108.7 | 2/3 (seed 43 dropped the reaching arm) | 3/3 | keep, keep, fixable |
| drawn skeleton | 66.4-70.5 | 3/3 | 3/3 | keep, keep, keep |

- **The depth route loses the face at full-body scale on 2 of 3 seeds.** The failure follows the seed, with or without the cut:
  - seed 41 drew a blank skin oval with no eyes, nose or mouth, and grey, glove-like hands;
  - seed 43 turned the skin dark brown and left the face nearly featureless;
  - seed 42 kept the face.

  This repeats the fantasy pack's slice B (16 September: "the depth Combine carried the pose and the costume but lost the face"),
  now on 4 of 6 renders. Its pose-holding is perfect, but it is not safe for identity when the character picture is a portrait
  and the target is a full body.
- **The ankle cut at 88 changed nothing visible.** Each cut render is near-identical to the uncut render of its seed. The boots
  were already clean without the cut on this pair, so the cut's original purpose (a stocking-foot artefact on the old pair) is
  not exercised here.
- **The drawn skeleton is the best of the four here.** It held the pose 3/3 with the face, earrings, scarf, coat and boots kept,
  and both hands five-fingered at full resolution. It is also the fastest, at 66-71 s. Its finish is flatter than the
  portrait's painterly shading.
- **Copy Pose keeps the character picture's own world**: its light floor, and on seed 42 the station platform itself. The
  painterly shading comes with it, and faces were kept 3/3. On seed 43 the second arm hangs at the hip instead of reaching out.

## Verdict

For putting an adult original from a portrait into a full-body pose, the drawn-skeleton route is the reliable choice on this
evidence (3/3 keep). Copy Pose is next (2/3 keep plus 1 fixable), and it is the one that keeps the character's own setting and
finish. The depth route should carry a warning that it can drop the face (2/3 here, 4/6 with the pack's earlier run), or be
paired with a face pass. These are agent verdicts on three seeds per route, not art acceptance. The route choice between
skeleton and Copy Pose is partly a look choice (flat vs painterly, plain vs the character's setting), and that is left to the
owner (R6).

## Not verified

- A single character and a single pose. The depth route's face loss may depend on the scale gap between the portrait and the
  full-body frame, which is not isolated here.
- Clicking through the page. The runs used the page's API shape, not the UI.
- The `depth_cut` control's original stocking-foot case was not reproduced on this pair.
- None of this is art acceptance or licence clearance. FLUX.2 Klein 9B is non-commercial per its card.
