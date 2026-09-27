# Z-Image Turbo fp8: the four installed anime LoRAs, blind — 27 September 2026

Refs #357 (restyle follow-ups: "Z-Image Turbo fp8 + anime LoRAs"). This is the text-to-image half only. The img2img restyle graph is still open.

## Method

I used the shipped `zimage-fast` graph (fp8 KJ build, Qwen3 4B encoder on the CPU, 8 steps res_multistep, CFG 1) and inserted one `LoraLoaderModelOnly` node at 0.8. I submitted straight to ComfyUI on the primary (06:00-06:25 local) with `.runtime/lab-0927/comfy_run.py`. There were five configurations:

- no LoRA
- `z-image-anime-v1` ("zanime")
- `anime_style_v1_zimage` ("animestyle")
- `elusarca_anime_style_zimage`, with its trigger `elusarca anime style` appended
- `aimaginedworlds_turbo_zimage` ("aimagined")

Each ran against three original SFW prompts with one fixed seed each: an adult woman cartographer, an adult bearded blacksmith, and a shrine courtyard (no people). All four LoRAs were pinned by owner decision q-32(b) and no recipe used them before this study.

I judged the fifteen pictures blind with `docs/quality/JUDGING-RUBRIC.md`: shuffled per prompt, every judgement written before reading `key.sealed.json`. I cropped hands, faces and props. See `judgements.jsonl` for the records and `sheet.jpg` for the configurations side by side (columns in the order above).

## Results (revealed after judging)

| Config | Mean score | Verdicts (p1 / p2 / p3) |
| --- | ---: | --- |
| zanime | 4.32 | keep / keep / keep |
| none | 4.03 | keep / fixable (blade floats beside an empty fist) / keep |
| elusarca | 4.00 | keep (unrequested headband) / fixable (double hammer head) / keep |
| aimagined | 3.87 | fixable (compass reduced to a lid) / keep / keep |
| animestyle | 3.72 | keep / fixable (cluttered, ambiguous tongs hand) / fixable (flat poster look) |

The rubric's rule treats means within 0.3 as a tie. On that rule, **zanime, none and elusarca tie**. Only zanime vs animestyle (0.6) clears the bar, and that is still one seed per prompt. The base model already draws cel-shaded anime from this wording, so none of the LoRAs is needed to get an anime look. What the adapters change is the flavour:

- zanime: glossier, semi-real
- animestyle: older flat TV cel look
- aimagined: more painterly
- elusarca: sharper, heavier linework

## Timing

`exec_s` per cell is in `runs.jsonl`. Whenever a cell reused the previous cell's prompt text, the encode was cached and the cell took 13-18 s. That happened for the first LoRA after the base (zanime) on all three prompts. Every later LoRA swap took 94-185 s, even with the text unchanged, and host commit peaked at 75-84 %. I did not isolate the cause (LoRA re-patching versus paging). Budget minutes, not seconds, when switching Z-Image LoRAs on this PC.

## Recommendation

No recipe change. If the owner wants a Z-Image anime recipe, `z-image-anime-v1` at 0.8 is the one to try first: 3/3 keep here, but a tie with no LoRA by the rubric. Promotion should wait for a three-seed rerun and the owner's eye.

## Status

These results are generated and agent-judged only; none of it is art acceptance. Licences are not cleared. The civitai flags recorded in `models/library.json` (`allowCommercialUse` Image/Rent for zanime and animestyle, and additionally Sell for elusarca and aimagined) are site flags, not clearance. The Z-Image Turbo base weights are Apache-2.0. The pictures stay local under ComfyUI `output/Research/lab-20260927/zimage-lora/`.
