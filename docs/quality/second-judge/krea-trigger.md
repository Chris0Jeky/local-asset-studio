# Second judge: the painted `@NJSW33T` trigger (23 September 2026)

This is an independent second judgement of the lab's `krea-trigger` test (#893). The test ran eight direct prompts on
`krea-anime-atelier-gguf`, with the same witch-portrait prompt and two seeds (2026092391 and 281715418). Four placements
of the trigger were tried:

- at the start of the prompt;
- at the end;
- at the start, without the TextFusion LoRA;
- no trigger at all.

The prompt describes a clothed witch portrait.

**How it was judged.** The review agent (Claude Opus 5.5) judged the eight pictures blind:

- under its own shuffle, with metadata stripped;
- every frame read at 1× for painted text, with each suspect region then read at 4×;
- the top and bottom 72 px strips checked separately on the frames with no text;
- before reading the key or any lab record.

The records are in [krea-trigger.judgements.jsonl](krea-trigger.judgements.jsonl).

## Result: the painted text is confirmed

| Trigger | Seed …91 | Seed …418 |
| --- | --- | --- |
| at the start | garbled handle on the hat brim | faint `@NJSW33T` on the cloak |
| at the end | `@NJSW33T` on the hat brim beside the face | `@NJSW33T` across the cloak by the lantern |
| at the start, no TextFusion | `@NJSW33T` in the bottom-left corner | none |
| no trigger | none | none |

That is 5 of 6 renders with the trigger, and 0 of 2 without it. The trigger word is painted as a signature wherever it
sits in the prompt, most often on the subject itself, where a crop cannot remove it.

## Agreement with the lab's judge

| Measure | Result |
| --- | --- |
| Where text was found | **8 of 8** agree, at the same places |
| Picture verdicts | 7 of 8 agree |

The one verdict difference is the corner signature (no TextFusion, seed …91). The lab calls it fixable. This judge applied
rule R4: a small glyph in the outer edge that a crop removes is `technical` 4, so the picture is a keep.

**Answer to the lab's claim.** Confirmed: `@NJSW33T` is painted as text wherever it sits, and never without it. The
lab's next step is still open: dropping the trigger, and checking whether the Niji Sweet Spot look survives without it.

## Not verified

- Two seeds per placement.
- Whether the look holds without the trigger. The lab's three-seed follow-up was still running at the time of writing.
- Nothing here is art acceptance.
