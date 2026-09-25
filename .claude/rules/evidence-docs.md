---
paths:
  - "CURRENT_STATE.md"
  - "HUMAN_TODO.md"
  - "docs/**"
  - "experiments/curated/**"
---

# State, evidence and human-choice docs

- `CURRENT_STATE.md` records what was executed, with prompt IDs, timings and inspected outputs, and
  keeps plans visibly separate. Never upgrade a plan to a result without the run that proves it, and
  never delete or relabel a historical result; add the correction next to it.
- Three states stay distinct in every sentence: generated (the job completed), inspected/accepted
  (a human judged the art), licensed (the model terms allow the use). One never implies another.
- `experiments/curated/` is the only experiments folder in Git. A curated entry carries the exact
  recipe JSON, the prompt ID, the backend and the reviewer's own words; contact sheets stay small
  (the validator caps tracked files at 10 MiB).
- `HUMAN_TODO.md` items are owner decisions and actions. Surface open items in every summary. Tick one
  only on directly verified completion, or a recorded owner answer to every part the item asks with its stated conditions met; record the date and how (their words, or the evidence). Never infer a decision.
- `docs/` is beginner-facing: keep commands runnable as written, keep model claims tied to the recorded
  run, and route ComfyUI-level detail to `workflows/comfyui/` rather than restating node graphs in prose.
- Clock times come from receipts or Git, never from the session's sense of time: `created_at` in
  `experiments/runs/<job>/state.json` (the receipts root), `git log --format=%ci`, or `python -c "import datetime;
  print(datetime.datetime.now())"` run right before writing. Twice on 16 September 2026 section headers were
  written more than an hour late; Git Bash's `date` labels the zone `GMTST` but is local time.
