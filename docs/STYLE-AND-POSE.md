# Style of one picture, pose of another — without Qwen

Five recipes in the Create view do this in one SDXL run: **Style + Pose (WAI v17)**, **(Nova Anime XL v19)**,
**(YumeFlux ILv1)**, **(Animagine XL 4)** and **(CSTati v3)**. WAI is the calm default; Nova (installed 14 September
2026) is the punchier, higher-contrast alternative; see the matrices below for the rest. Pony V6 and
NoobAI XL were tried and removed: with this adapter they lose the figure entirely. All four use weights and
custom nodes that were already installed on this PC:

| Part | What it does | File / node |
|---|---|---|
| IP-Adapter Plus SDXL (ViT-H), linear weighting, **style board of 1–3 pictures** | Each picture is encoded separately (`IPAdapterEncoder`), the embeddings are averaged (`IPAdapterCombineEmbeds`) and applied once (`IPAdapterEmbeds`); empty board slots are pruned before submission. Copies linework, shading, medium and palette; ignores the subject as far as the adapter can. (`style transfer` weighting looked the same but took 260 s per run on this ROCm build against 80 s for linear.) | `ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors`, `clip_vision/clip-vision_vit-h.safetensors`, `IPAdapterEncoder` / `IPAdapterCombineEmbeds` / `IPAdapterEmbeds` (ComfyUI_IPAdapter_plus) |
| OpenPose preprocessor | Extracts a body/hand/face skeleton from the **pose picture**, so an ordinary illustration or photo works as input | `OpenposePreprocessor` (comfyui_controlnet_aux, annotator weights under its `ckpts/`) |
| Xinsir OpenPose ControlNet | Holds the render to that skeleton | `controlnet/xinsir-openpose-sdxl.safetensors`, `ControlNetApplyAdvanced` |
| Checkpoint + two optional LoRA slots | Who the character is, plus any style adapter you want to stack | WAI v17 or Animagine XL 4 |

The Qwen Atelier recipes remain the route when you also need an **identity** picture; these two
recipes take the character from the prompt, not from a picture.

## Step by step

1. Open the Create view and choose **Style + Pose (WAI v17)** (or the Animagine one if you prefer
   its tag order). Readiness should list every file as present.
2. **Style board** — attach one to three pictures whose look you want on the *Picture 1–3* cards (drop a
   file, choose one, or *Pull from library* and pick the slot; the picker stays open until you close it).
   One picture is enough; two or three blend their looks. Slots you leave empty are simply skipped.
   The recipe's example (a retro-anime street scene) sits in Picture 1 until you replace it.
3. **Pose picture** — attach a normal picture of a person in the pose you want (its own control below
   the board, also offered as a slot in *Pull from library*). The graph extracts the skeleton itself. Do **not** feed it a coloured skeleton image; for those use the older
   *Animagine — pose guide* / *WAI — pose guide* recipes, which take the skeleton directly.
4. Write the prompt: subject, costume, setting, and the base model's quality tail. The prompt is the
   only thing that says who the character is. The negative prompt is prefilled.
5. Two knobs: **Style weight** (IP-Adapter, default 0.7) and **Pose strength** (ControlNet, default
   0.9), both 0–2. The variants give quick starting points: *Style lighter, pose looser*, *Style
   stronger*, *Pose exact*, *3-seed audition*.
6. Width and Height set the canvas (default 832×1216); neither picture sets the output size.
7. Generate. The first run in a ComfyUI session loads four model files (checkpoint, CLIP vision, IP-Adapter, ControlNet) and the OpenPose annotators; the proving run
   took 283 s that way. A warm run has not been timed yet.
8. Review in the library. If the pose was misread, check what the preprocessor could see: an
   occluded, cropped or back-facing figure gives a partial skeleton. If the style is too literal
   (the reference's subject leaks in), lower Style weight or shorten its window in the graph.

## Measured

Proving run of the WAI recipe, 14 September 2026: Studio job `88026ea3-c950-48bd-9529-3d02e81bf1e4`, prompt
`82d46bb9-f46f-4a70-b9e3-f72dfbb7c0d8`, 283 s including every cold load. The pose followed the pose picture and the
style picture's cel-shaded neon look transferred without its subject; details and hashes in
`experiments/curated/style-pose/README.md`, JPEG copy in `examples/style-pose/wai-proving-run.jpg`. The Animagine
recipe has not been run yet. A completed render is neither art acceptance nor
licence clearance for the checkpoint, the adapters or either reference picture.

## Matrix of 14 September 2026

Six checkpoints × three LoRA settings × two poses with the owner's own pictures, one seed, 30 Studio jobs:
[`experiments/curated/style-pose-matrix/2026-09-14/`](../experiments/curated/style-pose-matrix/2026-09-14/README.md),
assessment sheet in [`examples/style-pose/matrix/`](../examples/style-pose/matrix/assessment-sheet.jpg). WAI v17 and
YumeFlux carried both the palette and the poses; Animagine was darker; CSTati soft; Pony V6 and NoobAI produced no figure
at all, so their recipes were dropped. Cells took 62–372 s each; the spread is ComfyUI reloading models from paged RAM,
not the graph (see the README). Seven Illustrious LoRAs for this look were installed afterwards
([`research/style-pose/`](../research/style-pose/adapters-and-loras-2026-09-14.md)); the recipes' two LoRA slots take any
of them by filename.

A completed render is neither art acceptance nor licence clearance for the checkpoint, the adapters, the LoRAs or the
reference pictures; the flags civitai declares for each LoRA are recorded in `models/library.json`.

Nova Anime XL IL v19 was added afterwards and compared on the same board (`experiments/curated/style-pose-matrix/2026-09-14-nova/`,
sheet `examples/style-pose/matrix/nova-vs-wai.jpg`): pose held, stronger colour and contrast than WAI; a second choice, not a replacement.
