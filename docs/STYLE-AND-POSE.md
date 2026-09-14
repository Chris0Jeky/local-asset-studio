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

## From a finished picture: Continue with this → Restyle

**Restyle a picture (FLUX.2 Klein 4B, keeps everything)** is the route's first destination since the night of 14 September
2026. It keeps everything: FLUX.2 Klein 4B reads the picture as its own reference latent (no style board, no ControlNet, no
LoRA) and redraws it as the wording says. The handoff prepares that wording for you: a finish sentence (the light-novel
look by default; edit it for another look), a keep sentence (character, pose, face, hair colour, clothing and its
colours, props, background layout), and *The picture shows: …* with the source's submitted description, which is what
held the colours in research (without a description the robe drifted green on one seed). Six Euler steps at CFG 1 on a
canvas fitted to the source's aspect ratio at about 1.5 megapixels (832×1216 becomes 1040×1520); 16–20 s warm, about a
minute with the model load. Measured against the owner's target render on the throne witch: pose, wink, hat, red-and-black
robe and throne kept with the soft high-key finish; adding the style picture as a second reference washed the result out,
and a 2-megapixel canvas changed the hair, so the recipe takes one picture. Proving run through the page: job
`db25b173-e39c-4656-96bf-b377ded6bf80`, 65.9 s including the load; sheet `examples/style-pose/restyle-klein-proving.jpg`;
the eleven research renders are tabled in `experiments/curated/style-pose-matrix/2026-09-14-restyle/README.md`.

**Restyle a picture (WAI v17 + light-novel look)** was the route's first destination from the evening of 14 September
2026, after the owner's first Restyle result (a Style + Pose board with a single style picture) came out flat, garish and
without the throne, and they supplied a target render. It keeps the picture instead of only its skeleton: the picture to
restyle is scaled to about 1.5 megapixels at its own aspect ratio (832×1216 becomes 1024×1504) and VAE-encoded as the starting latent (Denoise 0.85; *Keep more* 0.75, *Repaint
almost everything* 0.95) and its OpenPose skeleton drives the ControlNet; WAI v17 with the Mishima Kurone light-novel LoRA
at 0.8 (Momoko in slot 2 as a variant) and finish terms appended inside the graph (soft lighting, pastel colours, light
background, delicate lineart; negative: dark, high contrast, oversaturated, neon) give the look at CFG 4.5; a FaceDetailer
pass with the same styled model repaints eyes and lashes at 0.4. **The style board ships off (Style weight 0)**: measured
against the owner's own target, the IP-Adapter board tinted the costume towards the style picture's palette at every weight
from 0.2 to 0.6 and over-drove it to neon at 1.0, whichever weighting; *Board touch (0.3)* and *Board strong (0.6)* are
variants for when you do want that palette. One board picture is still required by the graph (issue #351). Proving run
through the page: job `0c13590c-d204-4634-b045-cc03d5a3f2e3`, 86 s; sheets `examples/style-pose/restyle-picture-proving.jpg`
and `restyle-picture-research.jpg`; the twenty-three research renders behind the defaults are tabled in
`experiments/curated/style-pose-matrix/2026-09-14-restyle/README.md`. The five Style + Pose boards remain listed after it
for the original behaviour (skeleton only, look from the board). Since the Klein recipe took the lead it is listed second.

Added 14 September 2026 after the owner tried to give a liked output a different look, chose *Refine → SDXL •
stronger variation* (the closest thing on offer), attached the style picture into its single slot and got two
blockers nobody could act on. The Continue handoff now has a fifth route, **Restyle**, and the one-slot case asks
instead of blocking.

1. On a recent run or in the Asset library, press **Continue with this →** and choose **Restyle**. *Restyle a picture
   (FLUX.2 Klein 4B, keeps everything)* is listed first, then *Restyle a picture (WAI v17 + light-novel look)*, then the
   five Style + Pose boards (the source's own family first among those).
   The dialog says what will happen: the Klein recipe keeps the picture and redraws it in the look the wording describes
   (the prepared wording is shown under *Wording prepared for this pass*); the WAI recipe keeps the picture and repaints
   it in its finish (the board adds palette only by Style weight); a Style + Pose board keeps the pose and takes the look
   from the board. On the WAI recipe and the boards the source's submitted description is copied into the prompt; on the
   Klein recipe it is appended to the prepared wording.
2. **Prepare in Create** attaches the source as the **Picture to restyle** (*Pose picture* on a Style + Pose board; not on
   the board either way). On the Klein recipe nothing is missing: the canvas is fitted to the source, the wording is in
   the prompt, and Generate reads **Restyle source →**. On the WAI recipe and the boards the cursor goes to *Picture 1*
   and the one remaining condition reads *Add at least 1 picture whose look you want to the style board (Picture 1)*
   with a *Show the empty slot* button.
3. Board recipes only: drop the style picture on Picture 1 or use **Pull from library** (it opens on Picture 1 and closes
   itself once the board holds one picture). Generate reads **Restyle source →**.
4. If you were already continuing on a one-slot recipe and add a second picture (file or library pull), Create
   no longer blocks: a panel asks what the picture is for — *Use its look → Restyle the source* (opens the
   handoff at Restyle, prepares, and puts that picture on Picture 1), *Start from this picture instead*
   (ends the continuation), or *Keep the source, drop this picture*.
5. If the pose picture ever goes missing, the condition says *Pose picture no longer holds the picture you chose
   to continue* and its button **Put the source back** re-attaches the same asset (verified by hash) without
   reopening anything.

The server checks the same things: the claim's source must sit on the pose input, empty board slots must be
pruned (no recipe example can stand in), and at least the board minimum must be attached; the Studio job stores
the `restyle` intent with the source hash. Measured run below under *Restyle from a finished picture*.

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
