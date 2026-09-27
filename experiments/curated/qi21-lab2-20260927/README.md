# Qwen-Image 2.1: multi-reference identity, text-heavy prompts, Pruna 8-step LoRA — 27 September 2026

Second GPU lab session of the day, on the isolated `qwen21` backend (ComfyUI v0.37.0, port 8196; the Studio switched to it at
07:10 local). Refs #739 (multi-reference identity and a text-heavy prompt) and #934 (Pruna few-step LoRA). Everything
here was generated and agent-inspected only. None of it is art acceptance, and none of it is licence clearance: Qwen-Image 2.1
and the Pruna adapter are both under the Qwen Research License, which is non-commercial.

Scripts: `comfy_run.py` submits one API graph straight to ComfyUI, once, and records the prompt ID, `exec_s` from `/history`
and host-commit samples. `run_job.py` submits one Studio job through `POST /api/jobs`. The model cache was released
(`POST /free`, about 15 s, asynchronous) before each cold run so that the host-commit gate could pass. Two script defects were fixed after the
runs, on review: `comfy_run.py` treated a `/history` entry with `completed: false` as finished (now it waits for `completed: true` or a
`success`/`error` status), and `run_job.py` dropped a positional reference whose slot was pre-filled in the controls JSON while
logging it as used (now references fill the free slots and the log maps slot to file). Neither touched a committed receipt:
all 16 `comfy_run.py` receipts (`identity/`, `pruna/`) have status `success`, an `exec_s` and one output, and both `run_job.py`
jobs (`text/`) passed no reference files. Full-size PNGs stay local
in the qwen21 checkout's `output/lab2/` and `output/Studio/`.

## 1. Identity edit from 1, 3 and 5 reference pictures (#739)

Graph: the shipped `qwen21-edit` API graph, with extra `LoadImage` nodes wired to `TextEncodeQwenImage21`'s
`images.image_2 … image_5` sockets. All three runs used seed 2026092710 and 25 steps. The output follows picture 1 at about 1 MP
(832 x 1248). The references are the fantasy pack's original adult traveller (`experiments/curated/fantasy-pack-20260916/`):
the portrait (`Studio/Anima-v1-Baseline_00004_`), the full body (`_00005_`), the smile edit (`Verified/FLUX-Edit_00010_`), and the
depth-route full body with a blank face (`Combine/Klein-9B-depth_00005_`, used as the costume picture). For ref5, the fifth
picture is the teal-and-orange `studio-lantern-cutout.png` prop. The prompts are not held constant. All three describe her in
words, then place her "sitting on a wooden bench in a snowy mountain village at night, reading a small book by … lantern", but
ref1 opens "Image 1 shows", ref3 and ref5 "Images 1, 2 and 3 show", and ref5 alone adds "Image 4 shows her full costume from head
to boots" and asks for "the teal and orange lantern from image 5" where ref1 and ref3 ask for "a brass lantern".
`identity/graph-*.json` holds the exact graphs.

| Refs | Prompt ID | `exec_s` | Host commit peak | What came out (agent reading) |
| --- | --- | --- | --- | --- |
| 1 (portrait) | `be316486` | 126.2 | 78.5 % | Face kept: bangs with a side lock, brown eyes, and the gold drop earrings, which the prompt never names. The costume is invented: a long skirt, and a briefcase instead of the satchel. |
| 3 (portrait, full body, smile) | `bb5ecbfc` | 286.1 | 79.6 % | Face closer to the portrait. The costume follows the full-body picture: trousers, lace-up brown boots, the satchel on its strap, the coat's epaulettes. |
| 5 (+ costume, + prop) | `31e15e37` | 470.1 | 81.7 % | As with 3 refs, plus the costume picture's belt and cuffed trousers. The lantern is **image 5's teal-and-orange lantern**, with its ring handle and teal base. |

In all three, hands holding the book are readable (crops checked; the ref5 hands are slightly mitten-like). The references carry
identity beyond the words (the earrings), and ref3 (same wording as ref1 apart from the image count) carried more of the costume.
Ref5's belt and teal lantern come with prompt words that name the costume picture and the lantern, so they are a qualitative
example of what five references can carry, not an effect of the extra references alone. Cost grows with the number
of references: 126 s, 286 s and 470 s. Almost all of the added time is in the text encoder, which reads every picture at about
1 MP (`resolution` 1024). Five references is a patience route on this PC. Pruna's card says its adapter was trained with at most 3.
Sheet: `identity/sheet.jpg` (the four references, then ref1, ref3 and ref5).

## 2. Text-heavy prompts (#739)

Two Studio `qwen21-t2i` jobs at 1024², 25 steps (receipts in `text/`):

| Prompt | Job / prompt ID | Time | Result |
| --- | --- | --- | --- |
| Tavern chalkboard menu: a title and five priced lines | `4b938317` / `1be9bcd8` | 81.8 s | All six strings are spelled exactly, prices included, in a chalk display face. Style drifted toward a semi-photographic render, although "anime illustration style" was asked. |
| Infographic poster: a title, four numbered captions and a footer | `af4fef50` / `df6b89d9` | 75.8 s | All six strings are spelled exactly, in a clean 2x2 layout. The icon semantics are weaker: "silver pestle" is drawn as a fork-like tool, and panel 4 shows no starlight. |

Lettering is a strength of this model here: 12 of 12 requested strings (6 per prompt) came out verbatim at 1 MP. Sheet: `text/sheet.jpg`.

## 3. Pruna 8-step LoRA v0.1 (#934)

Download: `PrunaAI/Pruna-Qwen-Image-2.1`, revision `113e63bb`, `p_qwen_image_2.1_8step_v0.1.safetensors`, 335,606,104 bytes,
SHA-256 `f0865d68b02511a3a0ed232d9d1aa99cac3a94166f574b38bcbab1a7a297bb15` (matches the Hugging Face LFS object). It sits in the
qwen21 checkout's `models/loras/`. Licence: Qwen Research License (the card; a derivative of Qwen-Image 2.1). It is not pinned in
`models/library.json`, because the Studio has no qwen21 recipe that loads it.

The LoRA loads on the int8 ConvRot model through core `LoraLoaderModelOnly` with no "lora key not loaded" warning.
There were four conditions on the step ladder's three prompts and seeds (`qi21-steps-20260927`), all at 1024²:

- **base25**: the ladder's own 25-step renders;
- **p1**: the card's recipe. LoRA 1.0, `SamplerCustom` with `ManualSigmas`
  `1, 14/15, 6/7, 10/13, 2/3, 6/11, 0.4, 2/9, 0`, euler, CFG 1;
- **p2**: the Reddit tip. LoRA 2.0, `KSampler` 8 steps, euler/simple;
- **c0**: no LoRA, p1's 8 sigmas (control).

I judged them blind: shuffled per prompt, with every judgement written before `key.sealed.json` was read
(`pruna/judgements.jsonl`; panels `pruna/blind-*.jpg`).

| Prompt | base25 | p1 (1.0, exact sigmas) | p2 (2.0, simple) | c0 (no LoRA) |
| --- | --- | --- | --- | --- |
| char | keep | fixable: the lantern drawn as two stacked bodies | keep | reject: murky, face and hand smeared |
| prop | fixable: grey smear behind the rim | keep | fixable: pseudo-lettering ring despite "no text" | fixable: molten rim |
| scene | reject | reject | reject | reject |

All four scene pictures are photographic, as in the ladder. That is the prompt's style wording, not the sampler. The ladder's
judge had rated prop-s25 keep; this judge rated it fixable (inter-judge noise on one picture). A second seed (+100, not blind)
of char and prop at base25 and p1: **p1 again doubled the lantern** (one in each hand), and both compasses are usable. So p1
duplicated the lantern on 2 of 2 character seeds.

**Timing.** The sampler takes 4.7-5.0 s for 8 steps (1.6-1.7 it/s) against 15-16 s for 25. The first run after the LoRA is
applied sampled at 2.2 s/it (17 s). The whole job did not get faster: Pruna jobs took 45-74 s cold and 55-56 s warm, against 31-61 s
for the 25-step base. Every new prompt makes the 8.9 GB text encoder evict the diffusion model, and that swap costs about 30-40 s,
more than the 11 s the sampler saves. **Host commit** peaked at 80.1-89.5 % with the LoRA loaded, against 76.3-78.0 % without it
(`pruna/runs.json`). Against the same prompt without the LoRA, the first-seed peaks were p1 +3.8 / +7.7 / +7.9 points and
p2 +9.3 / +7.5 / +2.5 points (char / scene / prop, against c0); on the second seed p1 was +12.8 (char) and +3.4 (prop) against
base25, but those runs started from different commit levels (73.3 % and 65.9 % against 53.4 % and 54.0 %), so the LoRA's own cost was
not isolated. The 89.5 % came on a warm run that skipped the cache release, so it is closer to the 97 % failure point than any
other run here.

**Reading.** In ComfyUI on this RX 9070 XT, Pruna v0.1 8-step works on the int8 model and is level with the 25-step base on the
judged sample: each has one keep and one fixable across char and prop. It does not buy wall-clock time per job, because the text-encoder swap dominates. Its runs peaked 2.5-12.8
points of host commit above the matching no-LoRA run (not isolated from the starting level), and it shows a recurring prop-duplication defect on the character prompt. Park as a try-queue item, and
do not promote a recipe. It becomes worth another look when the text encoder can stay resident (a smaller encoder, or
batches that reuse one prompt), and at v0.2. Strength 2.0 with the plain simple schedule was not worse than the card's recipe
on this sample.

## Not verified

The following were not tested: VRAM peaks (only host commit was sampled); more than one or two seeds per cell; the 5-step
adapter (not downloaded); Pruna on edits; the owner's eye on any picture. The judgements come from one agent judge.
