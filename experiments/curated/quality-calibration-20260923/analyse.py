"""Re-run the 23 September 2026 calibration analysis from the committed records.

    python experiments/curated/quality-calibration-20260923/analyse.py [records.jsonl]

Reads docs/quality/CALIBRATION-2026-09-23.judgements.jsonl (both blind judges), maps each picture to the owner tier
that was pre-registered before judging (below), and prints verdict agreement, Spearman rank correlation, pair
concordance and the two forced look choices' mean-score order. To calibrate a later judge, append its records (same
shape, a new judge_instance) and add any newly owner-judged pictures to TIERS with the owner's words as the source.
"""
import itertools, json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RECORDS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "quality", "CALIBRATION-2026-09-23.judgements.jsonl")

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

judges = defaultdict(dict)
for line in open(RECORDS, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        judges[r.get("judge_instance", r["judge"])][os.path.basename(r["image"])] = r

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
