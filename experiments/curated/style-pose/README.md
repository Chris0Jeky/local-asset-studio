# Style + Pose proving run — 14 September 2026

One Studio job of the new **Style + Pose (WAI v17)** recipe with its authored defaults: IP-Adapter Plus (ViT-H) in
`style transfer` mode reading `examples/references/style-reference-example.png` (a Krea 2 retro-anime street scene) and
an OpenPose skeleton extracted from `examples/references/pose-reference-example.png` (the WAI lantern keeper) driving the
Xinsir OpenPose ControlNet. Both LoRA slots were at 0 and pruned. Exact IDs, hashes and the submitted graph are in
[`execution-evidence.json`](execution-evidence.json), [`studio-job-88026ea3-workflow.json`](studio-job-88026ea3-workflow.json)
and [`studio-job-88026ea3-recipe.json`](studio-job-88026ea3-recipe.json); a JPEG copy (quality 88) is
[`examples/style-pose/wai-proving-run.jpg`](../../../examples/style-pose/wai-proving-run.jpg).

| Job | Prompt ID | Wall time | Seen |
|---|---|---|---|
| `88026ea3-c950-48bd-9529-3d02e81bf1e4` | `82d46bb9-f46f-4a70-b9e3-f72dfbb7c0d8` | 283 s, all cold loads (host commit 57 % → 74 % while loading) | Pose followed the pose picture (standing, left arm out with the lantern, feet planted). Style followed the style picture (cel shading, hard outlines, neon cyan/magenta palette); none of its subject leaked in. Colours of the pose picture's costume were not kept, as intended. |

Read it honestly: one run, one seed, defaults only. The Animagine XL 4 sibling was not run. No warm-run timing exists yet;
the 283 s is dominated by first loads of five model files and the annotators. This is neither art acceptance nor licence
clearance: WAI v17's creator is not authenticated by its hashes, and the two example pictures are Studio outputs reused as
references.
