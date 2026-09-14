# Continue with this → Restyle, first two runs — 14 September 2026

The Restyle route sends a finished picture to a Style + Pose board as its **pose picture**. Both runs below were
driven through the Studio page exactly as the owner would: *Continue with this →* on the throne witch
(Nova output `Nova_00004_.png`, asset `9f2fca4d91ab59bba39f6e3606d10917`, sha256 `36d5a3661e552197…`),
*Restyle*, *Prepare in Create*, one imported picture pulled from the library onto Picture 1
(`140800824_p0_master1200.jpg`, asset `f44ac333401c5a3d8c831bf58e0644a5`, sha256 `0633c6e8b84bf28e…`),
then *Restyle source →*. Nova Anime XL IL v19, primary backend, no LoRA, seed 2026091407, pose strength 0.9,
832×1216, the source's own submitted prompt copied unchanged. Empty board slots 2 and 3 were pruned from the
submitted graph (`workflow.json` of each run has nodes 10 and 11 only, `IPAdapterCombineEmbeds` with `embed1`).

| Run | Studio job | ComfyUI prompt | Style weight | Time | Output | sha256 |
|---|---|---|---|---|---|---|
| Default | `2f34fdc8-743e-4d3b-807f-6ffb2a7a3966` | `486c1c75-0224-4410-b242-6c459a01f585` | 0.7 | 64 s | `Nova_00005_.png` (asset `441d90ca49575c33998ce26402a26d9d`) | `2dfe58c679a0cbc6…` |
| *Style stronger* variant | `f69c524c-eb0d-4ac0-b8f2-6b51ed2f2ac2` | `6b38f2fe-d79f-4718-83a8-e5b59478ae47` | 0.9 | 28 s | `Nova_00006_.png` (asset `2f3ed7ad995b5c8987a3342e48502c97`) | `1cc8eb9b3f4e9f9a…` |

Sheet: [`examples/style-pose/restyle-continue-nova.jpg`](../../../../examples/style-pose/restyle-continue-nova.jpg)
(source, style picture, 0.7, 0.9). Job records: `experiments/runs/<job>/` outside Git.

## What the pictures show (agent reading, not acceptance)

- **Pose held in both**: seated on the throne, one knee raised, one eye closed, hand at the face, from below.
- **The look moved, but not to the style picture's.** Both outputs are a flat, heavier-lined cel rendering with a
  blue-and-gold palette; 0.9 is more saturated with a glowing throne. The style picture is a soft, lightly shaded
  modern illustration with a red throne, and neither output reads as that rendering. One picture on the board at
  linear weighting is a weaker style signal than the owner's verified three-picture boards
  (`../2026-09-14-nova/`); the route works mechanically, the creative question is HUMAN_TODO q-27.
- Not verified: WAI or the other three boards through this route; a three-picture board through this route; any
  LoRA; a warm-versus-cold timing; art acceptance or licence clearance (the style picture is the owner's import).

## Restyle a picture (WAI v17 + light-novel look) — 14 September 2026 (later)

The owner ran the route above on their own style picture (`file.png`, a clean soft illustration on a white
background, sha256 `cc25e72f01542544…`, asset `b8691da84928503fb5ba1a87f026f509`) and said the result was not
good: flat, garish, throne gone, eyes crude. They then supplied a target render of the same throne witch
(1024×1536, soft high-key light-novel finish, black-and-gold costume kept, red-and-gold throne kept; a file
outside this repository, not committed). Twenty-three research renders were submitted straight to the primary
ComfyUI (research prompts, not Studio jobs; graphs and PNGs in the session scratchpad, hashes below), all with the
throne witch as the pose picture (`e0e988933f3c…_Nova_00004_.png.png`), the owner's style picture on a
one-picture board, the source's own prompt, seed 2026091407, pose strength 0.9.

| # | Checkpoint | Board | Latent | CFG | LoRA | Canvas | Prompt terms | Time | sha256 (16) | Reading |
|---|---|---|---|---|---|---|---|---|---|---|
| owner run (job `69d3962b`) | Nova | linear 0.7 | empty | 6 | none | 832×1216 | source only | 28 s | asset `225195d0…` | flat cel, throne gone, garish |
| st-0.7 (`4abb9701`) | Nova | style transfer 0.7 | empty | 6 | none | 832×1216 | source | 60 s | `52c4c551c254c3f0` | throne back, smoother; saturated |
| st-1.0 / stp-1.0 | Nova | style transfer (precise) 1.0 | empty | 6 | none | 832×1216 | source | 26 / 22 s | — | neon stripes: weight 1.0 is out |
| i2i60-lin0.7 (`cb546d5f`) | Nova | linear 0.7 | source, denoise 0.6 | 6 | none | 832×1216 | source | 22 s | — | picture kept, yellow and heavy |
| nova-i2i65-st0.6-c45 (`de875877`) | Nova | style transfer 0.6 | source, 0.65 | 4.5 | none | 832×1216 | source | 30 s | `81a6989685ae30d0` | cleanest lines of the Nova set; still saturated |
| K+mean(V) variants (`fd1cbfeb`, `4a8a2e50`) | Nova / WAI | style transfer 0.6 | source, 0.65 | 4.5 | none | 832×1216 | source | 160 / 84 s | — | glitter and star fields: keep `V only` |
| i2i60-st1.0-face (`254c1b0c`) | Nova | style transfer 1.0 | source, 0.6 | 6 | none | 832×1216 | source | 38 s | — | face pass cleans the eye and lashes (+18 s) |
| soft-wai-d85 (`9101d4bd`) | WAI | style transfer 0.6 | source, 0.85 | 4.5 | none | 1024×1536 | + soft-light terms | 66 s | `f57479f2f5b49815` | first bright, clean render; costume grey |
| soft-wai-d85-mishima (`624ef09d`) | WAI | style transfer 0.6 | source, 0.85 | 4.5 | Mishima Kurone 0.8 | 1024×1536 | + trigger | 82 s | `8bf1fb58fd6ac3ea` | light-novel face and shading; costume grey |
| soft-wai-d85-momoko (`929942b0`) | WAI | style transfer 0.6 | source, 0.85 | 4.5 | Momoko 0.8 | 1024×1536 | + trigger | 111 s | `99e62c21a0a29827` | softest; costume grey |
| soft-wai-mishima-w40 / w30 / w20 (`842b2f2b`, `d917d7ec`, `102fda2b`) | WAI | style transfer 0.4 / 0.3 / 0.2 | source, 0.85 | 4.5 | Mishima 0.8 | 1024×1536 | + trigger | 176 / 178 / 132 s | `00b55a5eecfda769` (0.3) | costume blue-grey at every weight tried |
| **soft-wai-mishima-w0 (`519de277`)** | WAI | **off (0)** | source, 0.85 | 4.5 | Mishima 0.8 | 1024×1536 | + trigger | 130 s | `04f6433965984b99` | **closest to the target: black-and-gold costume, red-and-gold throne, soft finish, clean face** |
| soft-wai-momoko-w0 (`dcb592e2`) | WAI | off | source, 0.85 | 4.5 | Momoko 0.8 | 1024×1536 | + trigger | 132 s | `4e332d9a4b10e9e6` | the alternative look (variant *Momoko look*) |
| soft-cstati-d85 (`bfcba917`, retry) | CSTati | style transfer 0.6 | source, 0.85 | 4.0 karras | none | 1024×1536 | + terms | 215 s | `82f5ffc575580346` | soft but blurrier; costume grey |
| soft-nova-d85-mishima (`cb7c6051`), w40-d90 (`a630c20b`), first WAI (`88b90b43`), first CSTati (`f3f4391d`) | — | — | — | — | — | — | — | — | — | failed before sampling: ComfyUI `free_memory` IndexError on the first checkpoint swap (issue #350); Nova was not retried |

Sheet of the four deciding renders: [`examples/style-pose/restyle-picture-research.jpg`](../../../../examples/style-pose/restyle-picture-research.jpg)
(source, style picture, owner run, WAI 0.85, WAI + Mishima, board 0.3, board off). Times include queue waits behind other
research prompts and model reloads; a warm run of the shipped recipe is the Studio job below.

What decided the recipe: (1) starting from the picture itself (img2img at denoise 0.85) is what keeps the throne and
costume; an empty latent keeps only the skeleton; (2) the palette shift the owner wanted came from the checkpoint
(WAI), the light-novel LoRA and the prompt terms, not from the style picture: the IP-Adapter board tinted the costume
towards the style picture's white-and-grey palette at every weight from 0.2 to 0.6 and over-drove it to neon at 1.0,
so the board ships **off** with *Board touch (0.3)* and *Board strong (0.6)* as variants; (3) CFG 4.5 instead of 6
removed most of the saturation; (4) a FaceDetailer pass with the same styled model fixed the eyes the owner complained
about; (5) `K+mean(V) w/ C penalty` scaling adds glitter and was dropped.

### The shipped recipe through the Studio

`restyle-wai` (*Restyle a picture (WAI v17 + light-novel look)*), driven through the page as the owner would:
*Continue with this →* on the throne witch (job `bb8efa52…`, asset `9f2fca4d…`), *Restyle* (the new recipe is
listed first), *Prepare in Create*, *Pull from library* → the owner's style picture on Picture 1, *Restyle
source →*. Every control at its authored default: Style weight 0 (board off), Denoise 0.85, CFG 4.5, 30 steps,
1024×1536 (first run; the canvas later became aspect-preserving), Mishima Kurone 0.8, Momoko 0, seed 2026091407 for the first run (carried over from the source's form: the handoff keeps width/height/seed, so this was not the recipe default 2026091401), pose strength 0.9, the source description copied
(the finish terms and the LoRA trigger are appended inside the graph by `StringConcatenate`, so the copied prompt
is unchanged on screen). Continuation intent `restyle`, source on `last_reference`, board slots 2 and 3 pruned.

| Studio job | ComfyUI prompt | Time | Output | sha256 (16) | Reading |
|---|---|---|---|---|---|
| `0c13590c-d204-4634-b045-cc03d5a3f2e3` | `5b9c2049-6586-47dd-ae4f-3d590972cb3b` | 86 s (warm WAI, LoRA and face pass included) | `Restyle/WAI_00001_.png`, 1024×1536, asset `2ae826ea22e35d50910c110ea72958c5` | `68d1dd8d15e90172` | pose held (knee up, one eye closed, hand at the cheek, from below), black-and-gold costume and red-and-gold throne kept, soft light-novel finish, clean face; the background is a darker red-to-blue wash than the owner's target, and the hat gained stars. Submitted graph: nodes 9, 30, 31 pruned (Momoko off, empty slots), `IPAdapterCombineEmbeds` with `embed1` only, Style weight 0 |

| `f2361234-53ab-4026-8647-7092a8aa83e1` (re-proof after Codex P2: node 4 became `ImageScaleToTotalPixels` 1.5 MP, no crop, width/height unbound) | `1165fb28-1741-4a90-9d16-7076a6700866` | 93 s | `Restyle/WAI_00002_.png`, 1040×1520 (the source's 2:3 kept), asset `2a3b5e613ee0588cbfd9adeaf680a708` | `3e5ab53c1382846b` | recipe seed 2026091401 this time (page reloaded, so no carried form seed); pose, costume and throne kept, soft finish, clean face, lighter background than the first run |

Sheet: [`examples/style-pose/restyle-picture-proving.jpg`](../../../../examples/style-pose/restyle-picture-proving.jpg) (source, style picture, owner run, first proving run, re-proof). Job records `experiments/runs/<job>/` outside Git. A job in between (`168f0bd4…`) was never submitted: the Studio's 60-second pre-submit wait expired while a research prompt held ComfyUI, and it queued nothing, as designed.

Not verified: Nova through the new shape (its checkpoint swap failed twice in ComfyUI); the other four boards;
a three-picture board on this recipe; any denoise other than 0.75/0.85; whether the owner accepts the look
(HUMAN_TODO q-27); licence clearance for WAI, the LoRAs or the style picture.

### Aside: Z-Image Turbo timing on this card (same session)

Asked whether Z-Image Turbo, FLUX.1 dev or FLUX.2 Klein 9B would serve this task better, two research prompts ran the
shipped `zimage` graph (`z_image_turbo_bf16.safetensors` 11.7 GB + `qwen_3_4b` encoder, 8 steps, `res_multistep`/simple,
CFG 1) at 1024×1536 after `/free` unloaded the SDXL models: cold **306.6 s** (22.8 s/it), warm **178.1 s** (15.3 s/it);
ComfyUI reported the model "loaded completely; 13102.84 MB usable, 11739.54 MB loaded", i.e. about 1.3 GB of headroom on
the 16 GB card, against 1.7-2.1 it/s for SDXL on the same card minutes earlier. The picture itself was clean and followed
a one-sentence natural-language prompt closely (throne, hat, crossed legs). Reading: on this card the bf16 file is
memory-starved; the "few seconds per image" reports use the fp8 (≈6 GB) or GGUF builds with headroom, which are not
installed. No conclusion about quality for restyling: Z-Image has no img2img/edit recipe here and Z-Image-Edit is unreleased.


## Restyle a picture (FLUX.2 Klein 4B, keeps everything) — 14 September 2026 (night)

The owner asked to keep improving the result and lifted the non-commercial constraint for their own experiments. While the
larger downloads ran (Z-Image fp8, Klein 9B, AniEdit; see `research/style-pose/restyle-model-strategy-2026-09-14.md`), eleven
research prompts went straight to the primary ComfyUI on the already-installed `flux-2-klein-4b-fp8` (Qwen3 4B encoder, FLUX.2
VAE, Euler on the Flux2 schedule, CFG 1, seed 2026091407 unless noted), the throne witch as the reference (scaled to 1 MP),
canvas 1024×1536 unless noted. The exact submitted graphs (full prompts, references, sampler settings) are committed in
`klein-4b-graphs/<name>.graph.json`; the PNGs stay in the session scratchpad and are identified by the hashes below.

| # | References | Prompt | Steps | Time | sha256 (16) | Reading |
|---|---|---|---|---|---|---|
| k4-plain-2ref (`ce56ae01`) | source + style picture | "Redraw the first image in the art style of the second image. Keep …" | 4 | 56 s (cold) | `1804aeac93b4222a` | picture kept exactly; style ignored, flat cel, purple wall |
| k4-plain-srconly-text (`42e13e66`) | source | finish in words (soft pastel light-novel, high-key, airy) + keep hat/robe/throne | 6 | 20 s | `57c84a8a34e412e1` | **close to the target**: soft high-key, gold throne, clean face; slightly washed |
| k4-text-s8 (`e8ceee08`) | source | same | 8 | 16 s | `46a30e9690b0c88a` | as above; paper grain |
| **k4-text2-s6 (`ba6054b9`)** | source | richer finish (throne-room curtains, glossy hair, blue eyes, black robe with gold trim) | 6 | 20 s | `b651e982aa79c209` | **closest to the owner's target** (curtains, gold, purple hair, blue eyes) |
| k4-text-2ref-s6 (`e53afd1f`) | source + style picture | finish in words, "in the art style of the second image" | 6 | 26 s | `ba913c2b290cf320` | washed out, pinker: the style picture hurts |
| k4-text-s6-2mp (`306de151`) | source (1.5 MP) | finish in words | 6 | 38 s | `8d026aa3bd5113ea` | 1216×1824: hair turned silver; larger canvas drifts identity |
| k4-generic-s6 (`73386f5d`) | source | generic keep clause, no costume names | 6 | 44 s | `dc1cb4c74bd9b46e` | robe drifted green |
| k4-generic-s4 (`d0826148`) | source | same | 4 | 10 s | `28515e59bb46eb54` | as above, softer |
| k4-generic-s6-seed2 (`142ba6db`) | source | same, seed 2026091402 | 6 | 16 s | `c43f5f3cfcc4eb58` | both eyes open (wink lost), robe green |
| k4-generic-tags (`37b66ed0`) | source | generic keep + "The picture shows: <source tag list>" | 6 | 20 s | `8de8921a870cdf04` | robe red-and-black kept; eyes yellowish |
| **k4-generic-desc (`d995a176`)** | source | generic keep + "The picture shows <natural description>" | 6 | 20 s | `6ff516b4e7097d8f` | **most faithful**: red throne, robe, wink and blue-grey eyes kept, soft finish |

What decided the recipe: (1) Klein keeps the picture through its reference latent alone; no img2img, ControlNet or LoRA is
needed; (2) the look must be *described*, the style picture as a second reference washes the result out (the IP-Adapter
finding again, on a different family); (3) naming what the picture shows holds the colours, so the handoff appends the
source's submitted description; (4) six steps at ~1.5 MP; a 2 MP canvas changed the hair.

### The shipped recipe through the Studio

`restyle-klein` (*Restyle a picture (FLUX.2 Klein 4B, keeps everything)*), driven through the page as the owner would:
*Continue with this →* on the throne witch (job `bb8efa52…`, asset `9f2fca4d…`), *Restyle* (the recipe is listed first, the
dialog shows the prepared wording), *Prepare in Create* (canvas fitted to 1040×1520, nothing missing), *Restyle source →*.
Job `db25b173-e39c-4656-96bf-b377ded6bf80`, prompt `7a205e07-8375-4f41-9f1e-99cba8e788cf`, **65.9 s** in ComfyUI including
the model load (16–20 s warm above), output `Restyle/Klein_00001_.png`, sha256 `6248d7c07a987780…`, asset
`841d3fcb8530533d84c1a8c06f3c617c`: pose, wink, hat, red-and-black robe with gold trim and the throne kept, warm high-key
finish, clean detailed eyes. Sheet: [`examples/style-pose/restyle-klein-proving.jpg`](../../../../examples/style-pose/restyle-klein-proving.jpg)
(source, style-picture-as-reference, finish in words, richer finish, generic keep + description, the shipped run).

Not verified: Klein 9B (Q6_K GGUF), AniEdit 4B/9B and Z-Image Turbo fp8 on this task (downloads in progress at 0.25–0.5 MB/s);
other seeds through the page; landscape sources; whether the owner accepts the look (HUMAN_TODO q-27).
