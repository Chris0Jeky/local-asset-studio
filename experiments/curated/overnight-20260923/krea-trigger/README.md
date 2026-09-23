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

## Recommendation (not applied here)

For Niji Sweet Spot on Krea 2, try leaving the `@NJSW33T` trigger out of the prompt. The LoRA card asks for it at the start, so
changing the presets' authored prompt is the owner's call. Two seeds make this a strong hint, not a rule. A 3-seed confirmation,
plus a comparison of the look with and without the trigger, should come first.

## Not verified

- Two seeds per configuration.
- The look difference with and without the trigger was not A/B-judged; only the text artefact was.
- Only the GGUF build was tested; the fp8 renders of the same recipe were not re-checked.
- No art acceptance.
