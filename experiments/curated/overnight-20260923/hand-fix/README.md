# Automatic hand repair (detector route) at a stronger setting — 23 September 2026 (overnight lab)

**Question.** `../hand-inpaint/` showed that a manual masked repaint at denoise 0.6 fixes a six-digit hand where 0.4 does not.
Does the automatic detector route, `anime-hand` (Impact Pack FaceDetailer on `bbox/hand_yolov8n.pt`, WAI v17, which needs no
hand-drawn mask), fix hands if it is simply turned up?

**Method.** `hand_fix.py run`, 06:21-06:23 local: 12 direct prompts. They used the shipped `anime-hand` graph with its FaceDetailer
inputs changed only, a generic hand prompt, seed 2026092395, and three settings:
- `authored`: denoise 0.4, guide_size 512, crop factor 2.5;
- `d06`: denoise 0.6;
- `d06-g768`: denoise 0.6, guide_size 768, crop factor 3.0.

The four sources are pictures the lab judged `fixable` for hands tonight (original characters):
- `noob4`: the six-digit raised hand;
- `noob5`: the witch's smeared left hand;
- `cstati`: two mitten hands;
- `yume`: a mitten right hand.

Judged blind per source, with the original shuffled in (`judgements.jsonl`), under R8: `adherence` = the named hand defect
fixed, `control` = everything else kept. The detector's own masks (`mask-*.png` in the output folder) show what was repainted.

## Results (unblinded)

| source | detector found | authored 0.4 | 0.6 | 0.6 + guide 768 |
| --- | --- | --- | --- | --- |
| noob4 (six digits) | the right hand | still six digits | still six digits | still six digits |
| noob5 (smeared left hand) | **only the right fist**, not the defective hand | unchanged defect | unchanged defect | unchanged defect |
| cstati (two mittens) | **nothing** | nothing repainted | nothing repainted | nothing repainted |
| yume (mitten right hand) | both hands (one box) | still a mitten | fingers now, but veiny, semi-real hands (off-style) | the same |

**The detector route fixed no defect cleanly on any of the four sources.** Every record is `fixable`, and none is `keep`.
- **The detector misses bad hands.** It found nothing on the CSTati mittens and boxed the wrong hand on noob5. An undetected hand
  cannot be repaired.
- **Where it finds the hand, a crop-and-repaint keeps the digit count.** On noob4 all three settings redrew the six-digit hand
  as six digits. The detailer re-renders the hand at a larger size from the same structure, and the redraw follows it.
- **A higher denoise changes style before anatomy.** On yume, 0.6 finally gave the mitten fingers, but it rendered both hands
  veiny and semi-real, unlike the flat anime picture.

Compared with `../hand-inpaint/`, the manual feathered masked repaint at 0.6 fixed the same six-digit hand on 3 of 3 seeds.
The difference is that it repaints the whole region at the picture's own scale with a soft edge, instead of a detected,
upscaled crop.

## Verdict

For hand defects, reach for `anime-masked-repair` (now at 0.6 with a feathered mask) with a hand-drawn mask. `anime-hand` and
the hand pass of `anime-detail-fix` should not be sold as hand fixes: tonight they fixed 0 of 4 defects at any setting. No
preset change is proposed here.

## Not verified

- One seed per setting and four sources.
- Other detector models or a lower detection threshold might find the missed hands (the authored bbox threshold was kept).
- No art acceptance. q-2 stays the owner's.
