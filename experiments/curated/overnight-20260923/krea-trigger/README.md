# Why the Krea atelier stack paints "@NJSW33T" into the picture — 23 September 2026 (overnight lab)

**Question.** Both GGUF runs with Niji Sweet Spot in #880 painted the trigger word as visible text: the target-stack run `976da1a8`
and the `krea-anime-atelier-gguf` Studio proof `29e468ca`. Is it the trigger token, its position, or the TextFusion LoRA?

**Method.** `krea_trigger.py render`, 06:54-07:08 local: 8 direct prompts. The graph is the `krea-anime-atelier-gguf` graph at its
authored defaults: 768x1152, 15 steps euler_ancestral, TextFusion 1.0 + Niji Sweet Spot 1.0, its witch prompt, text encoder on
the CPU. There were two seeds (the authored 281715418 and 2026092391) and four configurations:
- `start`: the authored prompt, "@NJSW33T, …";
- `end`: the same prompt with the trigger moved to the end;
- `none`: no trigger;
- `start-noTF`: the trigger at the start, TextFusion pruned.

Judged **blind** per seed (`judgements.jsonl`): all eight records were written before the key was read. Each picture was searched
for text at full resolution in two halves.

## Results (unblinded)

| configuration | painted trigger text (2 seeds) | where |
| --- | --- | --- |
| `start` (authored) | **2 / 2** | on the cloak; beside the face |
| `end` | **2 / 2** | on the cloak; beside the face under the brim |
| `start-noTF` (no TextFusion) | **1 / 2** | the bottom-left corner |
| **`none` (no trigger)** | **0 / 2** | – |

**The trigger word is painted wherever it sits.** Moving it to the end does not help, and dropping TextFusion made it rarer but
did not stop it (1/2). With no trigger, neither seed has text. The Niji Sweet Spot look (lavender hair, soft painterly cel shading,
the gold-trimmed witch) is still present without the trigger, as far as the pictures show; the LoRA acts through its weights. So
the untested hypothesis in #880 is half right: the trigger is rendered as text. It was rarer without TextFusion here (1/2 against
2/2 over two seeds), which is too few to say TextFusion makes it more likely; it is at most not the only cause.

Every clean picture is `keep`, and every picture with text is `fixable` (crop or inpaint). Speed: 57-131 s per prompt, most of it
the CPU text encode.

## Follow-up: three more seeds and the look A/B (23 September 2026, coordinator's request)

`trigger2.py` (records in `followup/`): the same GGUF graph at its authored defaults, three new seeds 2026092396-98 and four
configurations: `start-1.0` (the trigger at the start, Niji Sweet Spot 1.0, the reference), `none-1.0` (no trigger, Niji 1.0),
`start-0.7` (the trigger, Niji 0.7) and `none-0.0` (no trigger, Niji pruned, TextFusion only). All 12 prompts completed
(prompt IDs in `followup/results.json`). Judged **blind** per seed (`followup/judgements.jsonl`): the four letters of each seed
were shuffled, all 12 records were written before the key was read, and each picture was searched for text at full resolution
in two halves. Style was scored against the triggered look.

| configuration | painted trigger text (3 seeds) | look (blind style score) |
| --- | --- | --- |
| `start-1.0` (authored) | **1 / 3** (beside the face under the brim) | 5, 5, 5 |
| `start-0.7` | **1 / 3** (on the cloak below the collar) | 5, 5, 5 |
| **`none-1.0`** | **0 / 3** | **5, 5, 5** |
| `none-0.0` (Niji off) | 0 / 3 | 3, 3, 3: plainer cel shading and fewer ornaments |

- **With no trigger, no picture has text: 0/5 over both runs** (0/2 + 0/3), against 3/5 for the authored start position
  (2/2 + 1/3). Niji 0.7 did not stop it (1/3).
- **Dropping the trigger kept the look.** Blind, the `none-1.0` pictures scored the same style as the triggered ones on every
  seed. The judge could not tell them apart. The Niji-off control was the plainer picture on all three seeds, and the blind
  notes guessed it as the LoRA-off control each time. So the look comes from the LoRA weights, not from the trigger word.
- Every clean picture with the Niji look is `keep`. The two with text are `fixable` (inpaint or crop). The three Niji-off
  pictures are `fixable` on style: a weaker version of the look, not a broken picture.
- Speed: 39-139 s per prompt (spread in `followup/results.json`). The first seed of each configuration pays for the CPU text
  encode. The 133 s of `none-0.0` seed 98 was not examined.

## Recommendation (not applied here)

For Niji Sweet Spot on Krea 2, leave the `@NJSW33T` trigger out of the prompt. Over five seeds, no untriggered picture had
text, against 3/5 with the trigger at the start, and the look held without it (a blind tie on three seeds). The LoRA card asks
for the trigger at the start, so changing the authored prompt of the atelier presets is the owner's call. It is a small change:
remove `@NJSW33T` from the authored prompts that carry it (`workflows/api/krea-anime-atelier-api.json`,
`krea-anime-atelier-gguf-api.json`, `krea-refine-api.json`; `presets/recipes.json` and `presets/settings-kb.json` mention it
too), then run one Studio proof per preset.

## Not verified

- Five seeds in all, and three for the look A/B, with one judge (the lab). A second judge has not looked.
- The look A/B compares the triggered and untriggered pictures on the same seed; it does not test prompts other than the
  atelier witch.
- Only the GGUF build was tested; the fp8 renders of the same recipe were not re-checked.
- The recommendation is not applied: the atelier presets still carry the trigger, and no Studio proof without it exists.
- No art acceptance.
