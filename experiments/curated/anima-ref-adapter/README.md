# Anima Reference Adapter, first proof (1 November 2026)

Preset `anima-ref-adapter`: one reference picture, a scene-only prompt, Anima base v1.0 with the v2 r64 adapter
LoRA through the `ComfyUI-Anima-Ref-Adapter` custom node. Graph: `workflows/api/anima-ref-adapter-api.json`.

## Setup (what was run)

| item | value |
| --- | --- |
| ComfyUI | primary, 0.35.0, AMD RX 9070 XT, `--reserve-vram 0.6`, shared with other sessions |
| Custom node | `ArcAnima/ComfyUI-Anima-Ref-Adapter` at commit `99c222e1c2da472f4b514583b2dbd1b5afb4bdd9` (Apache-2.0) |
| Base model | `anima-base-v1.0.safetensors`, sha256 `bd43b7cf…a006e` (matches Hugging Face `circlestone-labs/Anima` at `f973fc41`) |
| Adapter | `anima_ref_adapter_v2_r64.safetensors`, sha256 `71dda607…cb81b` (HF `ElectronGirl/anima-ref-adapter` at `b729afd0`); licence CircleStone Non-Commercial v1.2 |
| Reference | `docs/showcase/pilot_girl.jpg` from the node repo (sha256 `62d1190f…a963a2`), the author's showcase sheet, used for local tests only |
| Settings | 832×1216, 30 steps, er_sde, simple, cfg 4.5, APG correction, seed 20261029, one image |

## Receipts

| run | route | ref_guidance | prompt ID | time | output sha256 |
| --- | --- | --- | --- | --- | --- |
| A | direct ComfyUI graph (probe script) | 4.5 | `7cab5525-a761-45a2-9f6b-447dfbd76c38` | 45.1 s | `ee7a4ca4…ffda5` |
| B | direct ComfyUI graph (probe script) | 1.0 | `0efcb7c1-0dcf-49e6-a218-1d486a93b648` | 40.1 s | `b7d947b6…216a52` |

Earlier attempt (no output, not a run): the first submission returned HTTP 400 because the base checkpoint was not yet
installed; the first Studio submission returned HTTP 400 `Unsupported sampler` because the preset had no `choices`
block. Both fixed before the runs recorded here.

## What was inspected

- Run A keeps the reference's long blonde hair, the red hair clip, the pink eyes and the black-and-white maid-style
  outfit. The cafe window, a cup in hand and a seated pose match the prompt.
- Run B keeps the hair and outfit in broad strokes, but the eyes are purple rather than pink, the clip is thinner,
  and the pose drifts. So `ref_guidance` changes the output in the direction of the reference.
- This is a visual judgement by one agent. It is not a measured identity score, and no second seed was run.
- Run B used `ref_guidance` 1.0 through the direct graph. The preset does not bind `ref_guidance`, so the Studio cannot
  reproduce run B; only the direct graph can. A follow-up would expose it as a control.
  Correction, 1 November 2026: PR #1888 binds `ref_guidance` as the *Reference strength* control, so the Studio can now
  reproduce run B. The runs above stay as recorded.

## Not verified

- Identity similarity measured numerically, across seeds, or against other references.
- Speed and quality while another process (Blender, a peer's ComfyUI jobs) shares the GPU. Timings above were taken on
  the shared machine but not under contention measurement.
- Compatibility with ComfyUI versions other than 0.35.0 and Torch ROCm as installed here.
- Two-reference (`two characters`) and asymmetric (`arch: asym`) adapters, which the preset does not expose.

## Licence and terms

The adapter weights are under CircleStone Labs Non-Commercial License v1.2, read 1 November 2026 at commit `b729afd0`.
LoRA weights are Derivatives; outputs are not, and section 2(e) lets outputs be used for any purpose. Whether a
commercial project's pipeline counts as a Non-Commercial Purpose (section 1(c)) is an open owner question, recorded in
HUMAN_TODO as `anima-ref-terms-1101`. This is advisory, not legal advice.
The existing `anima-base-v1-0` pin has an empty licence field and civitai terms for the same file. A separate PR should
fill it from the CircleStone licence; this PR does not change it.

## Status

Runs A and B were generated through a direct ComfyUI graph and inspected by eye. They are not a Studio job receipt.

## Studio receipt (preset proof)

| item | value |
| --- | --- |
| Studio job | `953363be-06cc-49a2-84fb-9c7cbe3171ac`, preset `anima-ref-adapter`, status `completed`, message `Complete` |
| Prompt ID | `03573334-76e7-48e0-97f0-4698fbc4ebc0` |
| Asset | `d27bf566929e5df2bb04d14788ff6681` (output `anima_ref_adapter/image_00001_.png`) |
| Time | 40.0 s |
| Output sha256 | `466e578a…bb3c1d` (PNG metadata differs from run A; pixels are identical) |
| Pixel check | identical to run A (`probe_cafe_00001_.png`): difference bounding box empty |
| Controls | same reference (`anima-ref-probe.jpg` upload, original sha256 `62d1190f…a963a2`), seed 20261029, 832×1216, 30 steps, cfg 4.5, er_sde, simple |

The preset is `verified: true` on this receipt. That means one Studio job completed and an agent inspected it. It is
not art acceptance and not a licence clearance; the catalog's `verified` flag means the same across presets.

Tests: `python -m unittest discover -s tests -p test_server.py` ran 176 tests, all OK. `validate-repo.py` passes
(95 preset graphs, 190 pinned assets). `validate-live.py --preset anima-ref-adapter` passed against the live schema.

## Seed stability (Studio batch, 1 November 2026)

Same reference, prompt, settings and `ref_guidance` 4.5, submitted as one Studio job with `batch_count` 3.

| item | value |
| --- | --- |
| Studio job | `dc95441f-c219-4e38-8e77-afdb6e526d9f`, status `completed`, 125.1 s for three images |
| Seeds and prompt IDs | 20261029 `e43f8c49-8e5f-48ba-8f1f-e47611bbf625`; 20261030 `59784e4d-f2b0-4f19-8430-1ade0e0400a3`; 20261031 `780a8a67-3b15-4046-9e31-5943f8f20213` |
| Output files | `anima_ref_adapter/image_00002_.png`, `image_00003_.png`, `image_00004_.png` |
| Studio note | GPU memory overflowed about 1.7 GB into system RAM during the run, which slows the steps it touches |

Inspected by an agent: all three keep the reference's pink eyes, red hair clip, long blonde hair, the black-and-white
maid-style outfit, and the cafe setting. Cup, pose and background vary across seeds. Seed 20261029 is the same seed as the
earlier Studio job `953363be`, so the first picture is expected to repeat it.

Not verified: a numeric identity score, other references, and whether the overflow changes the output beyond timing.
