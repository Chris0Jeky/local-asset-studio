"""Re-run the 23 September 2026 calibration analysis from the committed records.

    python experiments/curated/quality-calibration-20260923/analyse.py [records.jsonl] [--corrected]

Reads docs/quality/CALIBRATION-2026-09-23.judgements.jsonl (both blind judges), maps each picture to the owner tier
that was pre-registered before judging (below), and prints verdict agreement, Spearman rank correlation, pair
concordance and the two forced look choices' mean-score order. To calibrate a later judge, append its records (same
shape, a new judge_instance) and add any newly owner-judged pictures to TIERS with the owner's words as the source.
"""
import itertools, json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RECORDS = os.path.join(ROOT, "docs", "quality", "CALIBRATION-2026-09-23.judgements.jsonl")

# Owner tiers by output filename (5 great/very good, 4 good, 3 okay/potential/experiment, 1 mess/not good).
TIERS = {
    "krea-anime-atelier_00001_.png": 5, "witch-target-ersde-4step_00001_.png": 5, "witch-target-stack_00001_.png": 5,
    "witch-target-stack-4step_00001_.png": 5, "witch-nijisis-4step_00001_.png": 5,
    "witch-target-plus-baroque-oil-4step_00001_.png": 4, "witch-airy-watercolor-short-4step_00001_.png": 4,
    "WAI-Illustration_00012_.png": 3, "noob_00004_.png": 3, "krea-style-lab_00001_.png": 3,
    "witch-nijisis-baseline_00001_.png": 3, "WAI-Illustration_00013_.png": 3, "anima-artist-stack_00004_.png": 3,
    "pony_00002_.png": 1, "Nova_00007_.png": 1,
}
# Owner's pairwise choices: (preferred, other).
CHOICES = [("Anima-v1-Baseline_00002_.png", "Anima-v1-Baseline_00001_.png"),
           ("seed-2026091103-large.png", "seed-2026091104-large.png")]
OK = {5: {"keep", "fixable"}, 4: {"keep", "fixable"}, 3: {"fixable"}, 1: {"reject"}}

# --corrected: the POST-HOC check. Re-apply rubric notes R1-R5 to each judge's OWN named defects (no new looking) and
# recompute. Written from these same pictures, so it shows consistency with the owner, not generalisation.
# (judge prefix, filename) -> (score changes, rule and the judge's own words it rests on)
ADJ = {
    ("blind-1", "krea-anime-atelier_00001_.png"): ({"technical": 4}, "R4: the only named defect is a corner glyph"),
    ("blind-2", "krea-anime-atelier_00001_.png"): ({"anatomy": 3}, "R1: 'glove is elongated and mitten-like'"),
    ("blind-1", "witch-target-stack-4step_00001_.png"): ({"technical": 4}, "R4: corner glyph only"),
    ("blind-2", "witch-target-stack-4step_00001_.png"): ({"technical": 4}, "R4: corner glyph only"),
    ("blind-1", "witch-target-ersde-4step_00001_.png"): ({"technical": 3}, "R1: 'knees are flat lavender blocks'"),
    ("blind-2", "witch-target-ersde-4step_00001_.png"): ({"technical": 3}, "R1: 'white paint blotch on the lower hand, smears on both knees'"),
    ("blind-2", "witch-airy-watercolor-short-4step_00001_.png"): ({"anatomy": 3}, "R1: 'her right hand is lost'"),
    ("blind-1", "WAI-Illustration_00012_.png"): ({"anatomy": 3}, "R1: 'the upper hand shows a thumb and two fingers, the rest lost'"),
    ("blind-2", "WAI-Illustration_00012_.png"): ({"anatomy": 3}, "R1: 'over-long thumb with the other fingers merged'"),
    ("blind-1", "witch-nijisis-baseline_00001_.png"): ({"technical": 3, "composition": 3}, "R1: 'blotchy paint patches', 'boots cut off by the left edge'"),
    ("blind-2", "witch-nijisis-baseline_00001_.png"): ({"technical": 3, "composition": 3}, "R1: 'mottled paint blotches', 'boots cut by the left edge'"),
    ("blind-2", "anima-artist-stack_00004_.png"): ({"adherence": 3}, "R2: 'two lanterns instead of one lantern plus compass'"),
    ("blind-1", "noob_00004_.png"): ({"anatomy": 3}, "R3: one extra digit on a readable hand"),
    ("blind-1", "pony_00002_.png"): ({"anatomy": 2, "adherence": 3, "composition": 3}, "R5: 'face is a featureless shadowed profile'; back view where a cowboy shot was asked"),
    ("blind-1", "Anima-v1-Baseline_00002_.png"): ({"anatomy": 3}, "R1: 'fingerless pink sliver'"),
    ("blind-2", "Anima-v1-Baseline_00002_.png"): ({"anatomy": 3}, "R1: 'reading as a hidden or missing hand'"),
}

def verdict(s):
    v = [x for x in s.values() if x is not None]
    return "keep" if all(x >= 4 for x in v) else "fixable" if all(x >= 3 for x in v) else "reject"

def mean(s):
    v = [x for x in s.values() if x is not None]
    return sum(v) / len(v)

def rank(xs):
    s = sorted((x, i) for i, x in enumerate(xs)); r = [0.0] * len(xs); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1][0] == s[i][0]: j += 1
        for k in range(i, j + 1): r[s[k][1]] = (i + j) / 2 + 1
        i = j + 1
    return r

def spearman(a, b):
    ra, rb = rank(a), rank(b); ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / ((sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** .5)

CORRECTED = "--corrected" in sys.argv[1:]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if args:
    RECORDS = args[0]
judges = defaultdict(dict)
for line in open(RECORDS, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        name = r.get("judge_instance", r["judge"]); fn = os.path.basename(r["image"])
        if CORRECTED:
            chg = ADJ.get((name.split(" ")[0], fn))
            if chg:
                r = dict(r, scores=dict(r["scores"], **chg[0]))
                r["verdict"] = verdict(r["scores"])
        judges[name][fn] = r
if CORRECTED:
    print("POST-HOC: rubric notes R1-R5 applied to the judges' own named defects (see ADJ); not a validation.")

for name, recs in sorted(judges.items()):
    items = [k for k in TIERS if k in recs]
    agree = sum(recs[k]["verdict"] in OK[TIERS[k]] for k in items)
    rho = spearman([mean(recs[k]["scores"]) for k in items], [TIERS[k] for k in items])
    conc = disc = tied = 0
    for a, b in itertools.combinations(items, 2):
        if TIERS[a] == TIERS[b]: continue
        d = (mean(recs[a]["scores"]) - mean(recs[b]["scores"])) * (TIERS[a] - TIERS[b])
        conc += d > 0; disc += d < 0; tied += d == 0
    print(f"{name}: verdict agreement {agree}/{len(items)} (an always-'fixable' judge would get "
          f"{sum('fixable' in OK[TIERS[k]] for k in items)}/{len(items)}); Spearman {rho:.2f}; pairs {conc} right, {disc} wrong, {tied} tied")
    for good, other in CHOICES:
        if good in recs and other in recs:
            print(f"   owner preferred {good}: judge's mean {mean(recs[good]['scores']):.2f} vs {mean(recs[other]['scores']):.2f}")
