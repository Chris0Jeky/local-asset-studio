# Character-consistency workstation status — 13 September 2026

This note reconciles the current pilot state with the three completed baseline jobs recorded in the original source checkout. It is a factual execution boundary, not a quality or licensing approval.

## Pilot accounting

The external pilot summary records **12 attempts used, 11 completed, 0 selected, 0 human-accepted and 0 remaining**. The portrait-scope status records an uncertain first attempt after the backend exited without an output; its prompt and job evidence remain in the private pilot workspace. It is not retried here.

The scoped boot edit remains staged only. An approval review rejected the explicit Start command before process creation, so no start intent or generation was recorded and no retry is authorized by that evidence. The supplied standard costume, including its shown back view, remains the recorded private pilot canon; it does not accept a generated result.

The latest implementation is the repository's offline character-study and media scripts. The restored `character-consistency-kit.zip` is the baseline input for that implementation; it is retained outside Git with the original sources and operational receipts.

## Completed baseline jobs

The small companion curation in [`experiments/curated/goal-baselines-20260913/`](../../experiments/curated/goal-baselines-20260913/) records the recipes and provenance for three completed jobs from the configured original experiments root. Each job used a single 832×1216 image output, seed `2026091301` and 30 steps. CSTati v3 and YumeFlux ILv1 used the same full-body station brief; JANIMA v1 used its matching prose version. The source recipe, workflow and state records remain in the external run directories.

The coordinator visually inspected all three existing output images. They are useful generated baselines, but hand detail and leg/foot overlap remain unresolved across the set. All three remain experiment-only: **0 selected and 0 human-accepted**. No art-quality, character-identity, model-rights or production-use approval is inferred.

| Baseline | Job | Model route | Output | Execution |
| --- | --- | --- | --- | --- |
| CSTati v3 | `0b245661-1de8-4574-9f57-a51bb4bbdc6c` | `cstatiANIMEV30XL_v30.safetensors` | `CSTati-v3-Baseline_00001_.png` | completed |
| YumeFlux ILv1 | `4403908b-bedb-489d-a9ce-9f19e6136bab` | `yumefluxXLIllustrious_ilV10.safetensors` | `YumeFlux-ILv1-Baseline_00001_.png` | completed |
| JANIMA v1 | `78b5e0a3-5890-413a-ae64-ec0b59235879` | `JANIMAAnima_v10_2847103.safetensors` | `JANIMA-v1-Baseline_00001_.png` | completed |

The three output files, raw job receipts, full workflow snapshots and private character sources are not copied into this repository. The curation publishes recipe controls, source-run identifiers and hashes only; it does not publish an image or a machine snapshot.

## Current visibility observation

The live GitHub repository visibility was observed as **PUBLIC** on 13 September 2026. This is a read-only observation of the current state. It records no owner approval and makes no visibility change.

## Evidence sources and limits

- Baseline source: `C:/Users/jekyt/source/local-asset-studio/experiments/runs/<job-id>/{recipe,state,workflow}.json`.
- Character state: the private pilot `summary-latest.json`, portrait `STATUS-20260912.md` and staged-boot `STATUS-20260912.md` files, retained outside Git.
- The curation's recipe SHA-256 values bind the reviewed metadata to the source files at reconciliation time; they do not prove a future rerender will be byte-identical.
- The source pilot records are local attestations. They preserve uncertainty and review boundaries but do not authenticate a human reviewer, model terms or finished-art acceptance.
