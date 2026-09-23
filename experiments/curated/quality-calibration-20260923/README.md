# Agent-judge calibration, 23 September 2026

The method and the result are in [docs/quality/CALIBRATION-2026-09-23.md](../../../docs/quality/CALIBRATION-2026-09-23.md).
This folder keeps what is needed to repeat it:

- `build_pack.py` builds the blind pack: 19 SFW pictures the owner judged in their own words. Each is copied with its
  metadata stripped, under a shuffled label (seed `20260923`), with a brief file and a sealed key. Everything lands
  under the gitignored `.runtime/quality-calibration/`. No picture enters Git.
- `analyse.py` re-runs the agreement analysis from the committed records
  (`docs/quality/CALIBRATION-2026-09-23.judgements.jsonl`) against the owner tiers that were written down before
  judging.

To calibrate a new judge:

1. Build the pack.
2. Give a fresh agent only the pack folder and the rubric ([docs/quality/JUDGING-RUBRIC.md](../../../docs/quality/JUDGING-RUBRIC.md)).
   Tell it not to read anything else.
3. Append its records with a new `judge_instance` and run `analyse.py`.

When the owner judges more pictures in their own words, add them to `TIERS` in `analyse.py` and to the pack. That is how
the corrections in the rubric get tested on pictures they were not written from.

No GPU was used, and nothing here is art acceptance or licence clearance.
