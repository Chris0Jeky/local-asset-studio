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

**Restyle a picture in another picture's look (FLUX.2 Klein 4B)** is the route's second destination (late night, 14
September 2026): the same Klein graph with a two-slot board, image 1 = the picture you keep, image 2 = a picture drawn the
way you want; the wording tells the model to copy how image 2 is drawn, not what it shows, and carries one bracketed fill,
*Image 1's colours: […]*. It is a compromise, measured on the throne witch with a crisp flat-cel fan picture: with no
colour anchor the look transfers strongly and the palette drifts (purple hair, orange throne); with the full source
description the look is lost; a short colour sentence holds the colours with a moderate look shift. Use it when the look
is easier to show than to say; **Restyle a picture (keeps everything)** holds colours better whenever the look can be
said in words.

## From a finished picture: Continue with this → Combine

**Put this character into another picture's pose (FLUX.2 Klein 9B, depth map: strongest pose)** leads the
route since 15 September 2026 (later that night). The graph turns the pose picture into a Depth Anything V2 depth map and
that map is image 1, so only the body position reaches the model: the person, costume, shoes and colours of the pose
picture never do. On the owner's own pair (the SHARK crop-top character, the bent-over maid picture) FLUX.2 Klein 9B held
the deep waist bend and the crossed legs on 3 of 4 seeds with the face, hair, crop top, lettering and pink shorts kept,
bare feet, no tights and no tail, in 90-115 s warm (`examples/style-pose/combine-pose-round2.jpg`; the fourth seed bent
only moderately). Proved through the Studio's own path: job `22ff6394…`, output `Combine/Klein-9B-depth_00001_.png`. Two things the
research settled: both 2D skeleton detectors (OpenPose, DWPose) fail on that pose picture, the depth map does not; and a
blank image 1 plus the pose in words gives perfect identity but never the deep bend, so the structural image, not the
wording, carries the pose. The same three fills as the pose-first recipe. What the silhouette contains is drawn, so a
heel can still shape a foot; audition three seeds. The depth model is CC-BY-NC-4.0, the 9B model non-commercial.

**Put this character into another picture's pose (FLUX.2 Klein 9B, follows the pose)** is second on the route and is the
recipe to reach for when the pose picture's camera, framing and background should be kept as well as the pose (the depth
recipe keeps only the body position). It is the recipe for a strong pose (a deep bend, a crouch, a lean seen from an angle). It works
the other way round from the 4B recipe: the **pose picture is image 1** and is kept (pose, camera, framing, background),
and **your character is image 2** and is swapped into it. Three bracketed fills: who is in image 2, image 1's pose in a
few words, and your character's clothes and colours. The last one is not optional: without it image 1's black shorts and
heels leaked in our test; with it FLUX.2 Klein 9B held a deep waist bend on 4 of 4 seeds on the owner's own pictures
(`examples/style-pose/combine-klein9b-pose-first.jpg`). A shoe or stocking from image 1 can still ghost in, lettering
can garble; audition three seeds. About 100-200 s warm; the 9B model is non-commercial (private experiments only). Why
this order: the Klein models keep image 1's structure, so the 4B recipe below (character first, pose in words) can only
give a mild pose, and putting the pose picture first on 4B just brings the character's own pose back; the research table
in `experiments/curated/style-pose-matrix/2026-09-14-combine/README.md` shows all 22 renders.

**Put this character in another picture's pose (FLUX.2 Klein 4B)** is a new route (late night, 14 September 2026) for
what the owner actually tried that evening: "have the pose of the second image". Image 1 is the picture you keep (the
handoff puts it there), image 2 goes on Picture 1 of the board (*Pull from library* or drop a file); both are scaled to
about one megapixel and chained as reference latents. The prepared wording carries two bracketed fills the page refuses
to run until you replace them: *who is in image 1* (name the subject and costume: "the witch in the black and red robe
with gold trim and the wide-brimmed witch hat") and *the pose in a few words*. That is not ceremony: with abstract
wording ("the character from image 1") the 4B model either left the witch on her throne or kept the *second* picture's
person and added a witch hat (three renders); with the subject named it moved her every time (four renders across two
pose pictures). Do not append the source description: it names the source's pose and the model obeyed it. One pose
picture: a third leaked its shorts and lettering; the second slot exists so you can try, and the hint says so. The pose
picture's clothing can still leak a detail ("SHARK" lettering appeared on the robe once), so say "no lettering" or pick a
plainer picture. About 30–45 s warm. Research table and the exact graphs:
`experiments/curated/style-pose-matrix/2026-09-14-combine/README.md`; sheet `examples/style-pose/combine-klein-research.jpg`;
proving run through the page in `CURRENT_STATE.md` and the catalog's `execution_note`.

The owner's first run through this route (job `aebf406f…`, 22:54 the same night: the "SHARK" crop-top picture on image 1, a
bent-over fan picture as the pose, four seeds; sheet `examples/style-pose/combine-klein-owner-run.jpg`) showed two faults
in the prepared wording, not in the route: the keep sentence had been written for the witch and said "her hat", so
every seed invented a cap, and one seed drew two figures. The sentence is now subject-neutral ("Keep the face, the hair,
the outfit and its colours") and asks for one figure; the same four seeds re-rendered with the owner's own fills gave
four single figures, no hats, tail left out, seen from behind with hands on hips
(`examples/style-pose/combine-klein-owner-fix.jpg`, prompts `a20e6df1`, `39e6ce34`, `f73b9c0b`, `a27ae00d`, 21 s each
warm). The lean stayed mild because the fill said "leaning forwards": the picture guides, the words decide, so say how
far the figure bends and what each hand does; the board hint now says so. A test keeps the sentence free of `her`, `his`,
`hat`, `robe` and `witch` outside the fills. Starting from the *Combine two pictures* card instead of *Continue with this*
now blocks until you choose the picture you keep (the server refuses to queue the authored example picture), and the
board describes itself as a pose picture rather than a style board. Stronger pose words ("bent forward at the waist,
seen from behind, both hands on the hips, looking back over her shoulder") moved the look-back and the hands but not the
deep waist bend (`examples/style-pose/combine-klein-owner-bend.jpg`): say what should move, and expect a mild pose from
the 4B model when the pose picture is extreme.

**Change one thing (FLUX.2 Klein 4B, keeps the rest)** now leads *Continue with this → Edit* (it was the 11-minute Qwen
recipe). The prepared wording is "Change one thing: [say what changes]. Keep everything else exactly as it is: …" plus the
source's description; the bracketed fill blocks Generate until replaced. Measured: "replace her hat with a red Santa hat"
kept pose, face, robe and throne (the whole picture warmed towards red, so name the colours you keep).

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
   no longer blocks: a panel asks what the picture is for — *Use its pose → Combine* (the leading button since the
   Combine route exists: opens the handoff at Combine, prepares, and puts that picture on Picture 1), *Use its look →
   Restyle the source* (the same at Restyle), *Start from this picture instead* (ends the continuation), or *Keep the
   source, drop this picture*.
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
