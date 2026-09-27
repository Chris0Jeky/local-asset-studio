# FLUX.2 Klein LoRAs matched to the installed stack — 27 September 2026 (08:10-08:26 local)

Issue #764: shortlist Klein LoRAs whose declared base matches this PC's FLUX.2 Klein stack, then either smoke-test them or park them.
The stack is Klein 4B `flux-2-klein-4b-fp8` and Klein 9B `flux-2-klein-9b-Q6_K.gguf` (the distilled models).
Everything here was generated and agent-judged only. It is not art acceptance and not licence clearance.

## Candidates (Hugging Face, licence first)

Hugging Face was searched by `base_model:adapter:black-forest-labs/FLUX.2-klein-{4B,9B,base-4B,base-9B}`, sorted by downloads.
NSFW-tagged or explicitly adult repositories were skipped. Three SFW, game-relevant adapters were downloaded. All three are
Apache-2.0 per their cards, read on 27 September 2026. Each was fetched with resumable `curl` at a pinned revision, its
SHA-256 was compared with the LFS object ID before install, and it is pinned in `models/library.json`.

| Pin id | Repo @ revision | Base | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `klein4b-pixel-art-sprite-limbicnation` | `Limbicnation/pixel-art-lora` @ `0ac8e5c3` (the `.comfyui` file) | Klein 4B | 325,276,656 | `24e938f5…` |
| `klein9b-isometric-redmond` | `artificialguybr/ISOMETRIC-REDMOND-FLUXKLEIN9B` @ `63ce35f9` | Klein 9B | 165,704,496 | `633467a5…` |
| `flux2-klein-9b-consistency-v2` | `dx8152/Flux2-Klein-9B-Consistency` @ `8df0c733` (V2) | Klein 9B (edits) | 331,379,608 | `61db2017…` |

Also shortlisted but not downloaded (Apache-2.0, Klein 4B): `xocialize/background-remove-FLUX.2-klein-4B-lora` and
`xocialize/spritesheet-FLUX.2-klein-4B-lora` (both 76 MB). Klein 9B's own weights carry the FLUX non-commercial licence,
whatever the licence of a LoRA on top of them.

## Method

All graphs were submitted straight to the primary ComfyUI (0.35.0, port 8188) with `comfy_run.py`: one submission per cell,
serial, no retries. `graphs/` holds the exact graphs and `runs.json` the prompt IDs, `exec_s` and host commit.
Each pair differs only by a `LoraLoaderModelOnly` at 1.0 against no LoRA, with the same seed and the same words (triggers included).
Pairs were shuffled into A/B panels, and every judgement (`judgements-*.jsonl`) was written before its `key-*.sealed.json` was read.

- **Pixel art** (Klein 4B, 4 steps, 512²): the card's trigger wording on a knight and a potion flask, 2 seeds each.
- **Isometric** (Klein 9B, 6 steps, 1024²): `Isometric. IsometricRedm.` wording on a tavern tile and a forge room, 2 seeds each.
- **Consistency V2** (Klein 9B single-reference edit, 6 steps, 832x1216): the fantasy pack's original traveller portrait as the
  reference. Two instructions ("change only the background to a sunny forest clearing …", "change only her expression to a
  warm open smile …"), 2 seeds each. Judged against the source for "closer to the source outside the asked change". Pixel
  drift was also measured (mean absolute difference inside and outside the face box).

## Results (blind, one agent judge)

| LoRA | Preferred with LoRA | Preferred without | Notes |
| --- | --- | --- | --- |
| Pixel art 4B | 1 of 4 | 3 of 4 | The trigger words alone already give pixel art on Klein 4B, with a crisper grid. The LoRA softened it. ComfyUI logged **6 LoRA keys not loaded** (the `*_modulation` layers) on every LoRA run. Both arms paint a fake checkerboard for "transparent background": there is no real alpha. |
| Isometric 9B | 1 of 4 | 3 of 4 | Klein 9B draws clean isometric dioramas from the words alone. Both pseudo-lettered signs came from the LoRA side. |
| Consistency V2 9B | 2 of 4 | 1 of 4 (1 tie) | Every edit did what was asked and kept the face. On the background change the LoRA cut face drift (face-box MAD 35.1 / 33.6 against 40.1 / 42.1) but raised saturation (+33 / +30 against +6 / +17), the opposite of the card's V2 claim. On the smile edit it drifted slightly more (23.0 / 18.3 against 18.5 / 17.2) and warmed the grade. |

Timing: pixel art took 3-6 s per warm job at 512² (27.6 s for the first, cold job). Isometric took 34-53 s and consistency edits 44-78 s.
Adding a LoRA made no consistent timing difference. Host commit peaked at 68-83 %.

## Verdict

**Park all three. Promote no recipe.** None beats the base model's own response to the same words on this sample. The consistency
LoRA is the only one with a plausible upside (lower face drift on large background changes). It is worth a larger test only if
identity drift on Klein 9B edits becomes a named problem. The pins stay so that the files are accounted for; nothing in
the catalog loads them.

## Not verified

Not tested: more than two seeds per cell, strengths other than 1.0, the 4B pixel LoRA at the card's bf16 base (only the fp8
distilled base is installed), a second judge, the owner's eye. Local full-size PNGs are in the primary ComfyUI
`output/Research/lab2-20260927/klein/`.
