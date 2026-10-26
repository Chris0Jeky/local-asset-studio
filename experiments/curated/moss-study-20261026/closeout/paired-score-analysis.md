# Matched score summary, 26 October 2026

Four existing scene/seed pairs per row. Entries are **wins / ties / losses** for the right-hand treatment against the left. These are ordinal, visible-label agent ratings, not blind preferences or population estimates. No new images or scores were produced.

| Baseline -> treatment | Adherence | Anatomy | Style | Technical | Composition |
| --- | --- | --- | --- | --- | --- |
| base -> reverse-no-trigger | 0 / 3 / 1 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 |
| base -> reverse-trigger | 0 / 3 / 1 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 |
| base -> reverse-1.2 | 0 / 2 / 2 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 |
| base -> mikko | 0 / 4 / 0 | 0 / 4 / 0 | 4 / 0 / 0 | 0 / 4 / 0 | 0 / 4 / 0 |
| base -> mikko-impasto | 0 / 3 / 1 | 0 / 4 / 0 | 1 / 3 / 0 | 0 / 4 / 0 | 0 / 4 / 0 |
| reverse-no-trigger -> reverse-trigger | 1 / 2 / 1 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 |
| reverse-trigger -> reverse-1.2 | 0 / 3 / 1 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 | 0 / 4 / 0 |
| mikko -> mikko-impasto | 0 / 3 / 1 | 0 / 4 / 0 | 0 / 1 / 3 | 0 / 4 / 0 | 0 / 4 / 0 |

Each comparison keeps seed, scene, resolution, step count, CFG, sampler, scheduler and negative fixed. Prompt-trigger and adapter-strength changes are the deliberately tested variables. The original receipts preserve the actual controls/graphs.

- Scores are ordinal and subjective; no averages, significance tests or population generalization.
- Same reviewer within a plan; reviewers differ between plans. Labels are visible, allowing expectation bias.
- No owner art acceptance; no character consistency/training-set membership inference.
- Style adherence score is not a whole-image quality or keeper rate.
- A tie is the same ordinal bucket, not identical images, hands or anatomy.

The full calculation and per-pair scores are in `paired-score-analysis.json`; source hashes bind the exact retained review and receipt files.
