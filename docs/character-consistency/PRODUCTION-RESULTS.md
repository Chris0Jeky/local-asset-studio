# Collect saved study results

Use this after primary character-study cases have been imported into Production.
It collects their saved outcomes into the existing study summary, so actual prompt
IDs and outputs no longer need to be transcribed into attempt records by hand.
ComfyUI and Studio do not need to be running. The command reads saved files and
SQLite databases; it does not start, resume, recover or submit anything.

From the repository root, replace the example study paths with your existing
approved plan and canon workspace. The workspace must contain the original
reference paths and bytes named by the plan. Choose a new output directory inside
that workspace, outside the source `experiments` directory; its parent must exist.

```console
python scripts/character_study_results.py --plan C:/AI/character-lab/my-study/plan.json --workspace C:/AI/character-lab/my-study --experiments experiments --out C:/AI/character-lab/my-study/production-results-v1
```

If your canon workspace currently lives under `experiments`, retain that original
and copy the whole workspace to a separate location without changing its relative
paths. The collector rechecks the approved plan and every reference digest there.
Point `--experiments` at the directory used for the original Production imports,
including when running the command from a different checkout.

The new directory contains:

- `collection.json`: case dispositions, unchanged Production allowance and
  reservations, unimported case IDs, file hashes and collection limits.
- `production.json`: the saved project plans, states and shared budget snapshot.
- `records.json` and `summary.json`: inputs and output of the existing
  `character_study.py summarize` contract.
- Each observed job's evidence JSON, including the exact saved graph, submission
  receipts, pending markers and project identity. Never-submitted jobs retain
  evidence without becoming image-producing attempt records.
- Completed candidate copies verified against their Workspace asset hashes and
  job ownership. The source images and asset metadata are unchanged.

Read `collection.json` alongside the summary. **The summary's `attempts_remaining`
counts records; it is not permission to generate or the remaining Production
allowance.** Reservations remain spent for unstarted work too. This command cannot
return, replenish or grant an allowance. Failed attempts keep their prompt IDs;
unknown, active or abandoned observations remain `submission_uncertain`. Collection
does not reconcile them or permit another submission.

Each imported primary case must retain one bound Production stage. The collector
checks its plan, case seed, prompt/reference bindings, deterministic job and asset
ownership, saved submission graph and output bytes. Generic branches sharing the
budget, missing job evidence, incomplete project creation and mismatches stop
collection instead of disappearing from the accounting. This command does not
collect character-edit campaigns, repairs, warmups or manually run legacy jobs.

Every candidate review starts as `null`. A generic Production choice or Workspace
keeper label does not cover the canon's required checks or establish human art
acceptance. To assess candidates, retain `records.json`, create a new assessment
copy, and add actual reviews using [the review contract](RUNBOOK.md#6-record-attempts-and-reviews).
Run the ordinary summarizer against that copy and the same canon workspace:

```console
python scripts/character_study.py summarize --plan C:/AI/character-lab/my-study/plan.json --records C:/AI/character-lab/my-study/assessment-v1.json --workspace C:/AI/character-lab/my-study --out C:/AI/character-lab/my-study/assessment-summary-v1.json
```

Existing output directories are never overwritten. If collection fails after
writing begins, `.incomplete` and any copied evidence remain. Do not use that
directory as a completed collection. Inspect the reported cause and preserve the
partial snapshot; use a new directory for a later collection. A source change
during collection stops publication, with no automatic retry. SQLite snapshots
and the second file check do not form a transaction across all stores.

Limits are 256 projects, 16 MiB per saved JSON document, 20 MiB per candidate image
and 256 MiB of collected evidence/images. Elapsed values come from saved job
measurements; missing or unresolved measurements remain null. These are local
attestations, not authenticated execution, current model/runtime identity,
cold/warm performance, verified resource receipts, art quality or licensing proof.
The broader performance work remains under #302. Keep collected plans, prompts,
images and source paths outside Git; they may contain private study material.
