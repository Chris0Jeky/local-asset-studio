# Anima recipe execution evidence — maintenance pass 2

## Scope and reconciliation

Fixes issue #148. Inspected main: `61a8c4e16b8e64b8bdea5a121bec71f2b0758cb8`,
Git tree `c7e1c8e0857661ce614ba7dd635a4de2beb90062`. The supplied older ZIP was
not used as the implementation base. An exported tracked snapshot reproduced
that exact tree before edits. Existing PRs #197/#198/#200/#202/#203/#205/#206
were left to their owners; this is a separate metadata correction.

## Root cause and correction

`describeRecipe` reads `evidence.prompt_id` and `evidence.seconds`. The two
modular Anima entries instead supplied prose strings. Their executed status was
already correct, but the picker could not display the retained prompt identity
and elapsed time.

Only those two `evidence` fields change. Each becomes the established object
shape, with exact job ID, prompt ID and seconds copied from
`experiments/curated/anima-modular-baseline-20260913/execution-evidence.json`.
`record` and `case` identify the source. `note` retains the original prose and
output hash verbatim. No recipe controls, workflow bytes, source receipts,
execution statuses, licensing or artistic acceptance are altered.

| Recipe | Retained case | Seconds |
| --- | --- | --- |
| `anima-v1-base` | `anima-base` | 28.098373651504517 |
| `anima-v1-first-adapter-comparison` | `anima-style` | 20.146408081054688 |

These are historical measured executions, not evidence that the current
workstation has just rerun either recipe. Displaying execution evidence must
not imply review, rights clearance, engine acceptance or current-template
identity after a user changes settings.

## Regression proof

The new tests read the actual catalogue and retained receipts, verify the
archived recipe-byte hashes, and execute the shipped `describeRecipe` function
inside a Node VM. They verify displayed prompt IDs/timings, the explicit
inspection caveat, no mutation and no extra requests. They do not freeze
unrelated recipe statuses.

On unchanged main: three methods ran, with three failing assertions/subtests
(the two evidence types and the rendered descriptions). The archived byte-pin
check passed. After the correction all three pass.

```sh
python -m unittest discover -s tests -p test_recipe_execution_evidence.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
git diff --check
```

Linux, Python 3.13.5, Node 22.16.0: full suite **1,492 tests, 15 skipped,
no failures/errors**, 96.462 seconds. Untouched main: 1,489 tests, 15 skipped,
no failures/errors. Existing Pillow deprecation and exit-time socket warnings
remain visible. Optional/live skips are not claimed as executed.

## Rollback and limits

Reverting the two catalogue fields restores the old display behavior. No
migration, native application, model download, generation or owner decision is
involved. The archived receipts and media stay unchanged. Hosted CI and
independent review are separate gates; check the PR's final verification comment.
