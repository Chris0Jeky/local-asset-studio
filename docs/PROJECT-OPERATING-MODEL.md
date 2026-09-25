# Repository operating model

This guide keeps Local Asset Studio's active queue legible while preserving the detailed evidence that makes the project reliable. It implements the first operating slice of issue #315. It does not replace GitHub, `STATUS.md`, `CURRENT_STATE.md`, `HUMAN_TODO.md` or the domain-specific runbooks.

## Four different records

| Record | Owner | What belongs there |
| --- | --- | --- |
| `STATUS.md` | authored current truth | Goal status, product judgement, current gaps and recommended next slice |
| `CURRENT_STATE.md` | chronological evidence ledger | Executed work, exact receipts, retained failures and dated handoffs |
| `HUMAN_TODO.md` | owner decisions | Creative, licensing and owner-run acceptance choices; agents tick an item only on verified completion, or a recorded owner answer to every part with its conditions met |
| `docs/generated/REPOSITORY-STATE.md` | generated factual projection | Captured active PRs, selected issue readiness, WIP arithmetic and SHA-bound receipts |

A generated snapshot cannot decide artistic acceptance, product percentages, priority or licensing. A passing check cannot close a broad issue.

## Work taxonomy

Every active item should have one primary type. Historical issues do not need a bulk relabel.

| Type | Meaning | Ready when |
| --- | --- | --- |
| **Epic** | Long-lived outcome or programme spanning several slices | The next bounded child is identified |
| **Slice** | Implementation-ready, reviewable change with one owner | Scope, acceptance and proving checks are explicit |
| **Defect** | Reproduced failure with a causal regression | The failure mechanism and owner seam are known |
| **Experiment** | Finite execution or evidence budget | Inputs, budget, stop conditions and review criteria are frozen |
| **Decision** | Owner choice or approval | The alternatives and consequences are visible |
| **Research** | Evidence gathering, architecture or feasibility study | The question, sources and promotion test are bounded |

Readiness is independent of type:

| Readiness | Meaning |
| --- | --- |
| `blocked` | A named dependency or owner decision prevents useful work |
| `ready` | Unblocked and sufficiently specified to start |
| `active` | Implementation or investigation is in progress |
| `review` | Delivery is complete enough for review; no further widening |
| `owner-run` | Needs the configured workstation, native tool or creative judgement |
| `parked` | Intentionally deferred; not silently abandoned |

The structured issue form records these fields in the issue body. Labels may mirror them later, but labels are not another source of truth.

## Work-in-progress limit

<!-- repository-snapshot-wip: independent=3 stacks=1 owner-run=1 -->

The default limit is:

- at most **three independent implementation lines**;
- plus **one explicit stacked chain** with its merge order stated;
- plus **one** separately identified `owner-run` neural or native acceptance lane.

A stack child does not consume another independent line. Research in review does consume a line when it has an open PR. A new line starts only after another merges, closes, or is deliberately parked. The owner may override this explicitly. A maintenance defect may bypass the limit only when it blocks an active line, and the reason belongs in the PR.

In `active-work.json`, `stack_parent` names the **root PR of the whole chain**, while `base` retains the immediate branch dependency. Every descendant of `#333 → #336 → #346 → #349`, for example, records `stack_parent: 333`. A non-root parent is rejected rather than counted as a second stack. An owner-run PR cannot simultaneously be a stack child, and the generated verdict fails when more than one owner-run lane is active.

The limit controls integration cost, not personal activity. It does not prohibit reading, issue triage or preparing an owner decision.

## Integration rules

1. Reconcile live `main`, open PRs and issue ownership before editing.
2. Declare a stack before opening its child; do not discover the stack accidentally after both branches drift.
3. Qualify the actual merge candidate after `main` or the stack parent moves.
4. Keep a PR's first screen concise. Put full hashes, causal logs and fault matrices in a reconciliation document or CI artifact.
5. Stop widening after the acceptance is met. Open a separate ready slice for genuinely independent follow-up.
6. Preserve causal commits when they are useful. There is no blanket squash requirement.
7. Emergency corrections may bypass the queue, but must state why and retain the narrow regression.

## Pull-request communication contract

The template asks for:

1. **Outcome** — what is now possible or corrected.
2. **User impact** — why it matters in the real workflow.
3. **Changed files** — the bounded implementation surface.
4. **Risk** — the material compatibility or data risk.
5. **Verification** — fresh commands and exact outcomes.
6. **Issue disposition** — closing keywords only for complete acceptance.
7. **Remaining gap / not verified** — what the PR does not establish.
8. **Evidence link** — detailed receipts without repeating them in three places.

The PR body is a decision surface, not the archive.

## Generated repository state

`scripts/repository_snapshot.py` reads only local, explicit evidence:

- a bounded capture of open PRs and selected active issues;
- optional test and validator receipts.

It never calls GitHub, closes work, changes labels or infers acceptance. The captured GitHub projection under `research/repository-state/` is evidence at one time, not a project-management database.

The snapshot keeps two provenance lines deliberately separate:

- `repository.head_sha` is the revision whose GitHub work queue was captured;
- `repository.facts_sha` is the revision whose measurements the capture asserts; a receipt is current only when its own `source_sha` matches it.

Test and validator receipts are current only when their `source_sha` matches `facts_sha`; otherwise they remain visibly stale.

### Why the committed projection carries no checkout-derived facts

The first design read `presets/catalog.json` and `HUMAN_TODO.md` into the committed projection and bound them to exact Git blob IDs, so generation refused when the checkout bytes moved. That made the drift gate unsatisfiable rather than strict: `HUMAN_TODO.md` is the one file every agent is asked to keep current, and `presets/catalog.json` changes with every preset slice, so the gate went red on edits unrelated to the capture, and the only repair was "regenerate", which republished a days-old PR landscape as current state. That was #461.

The rule now:

- the committed projection is a **pure function of the committed capture, the receipts and the generator**. Nothing else can turn the drift gate red, so `--check` asserts exactly one thing - the checked-in Markdown is what those committed inputs render;
- `presets/catalog.json` and `HUMAN_TODO.md` are read **only** with `--local-facts`, which appends a clearly separated section, prints to stdout only, and is refused with `--check` or `--output` so those facts can never be written into the committed projection;
- that section records the blob it actually observed and whether it still matches the identity the capture recorded. A difference is reported, never raised;
- the capture keeps `catalog_blob_sha` and `human_todo_blob_sha` as the observation it was authored against, not as a pin the checkout must satisfy.

Catalog counts remain owned by `python scripts/validate-repo.py`; open owner decisions remain owned by `HUMAN_TODO.md`, which agents surface in every summary and tick only on verified completion, or a recorded owner answer to every part with its conditions met.

Generate or check the snapshot:

```console
python scripts/repository_snapshot.py \
  --source research/repository-state/active-work.json \
  --test-receipt research/repository-state/test-receipt.json \
  --validation-receipt research/repository-state/validation-receipt.json \
  --format markdown --output docs/generated/REPOSITORY-STATE.md

python scripts/repository_snapshot.py \
  --source research/repository-state/active-work.json \
  --test-receipt research/repository-state/test-receipt.json \
  --validation-receipt research/repository-state/validation-receipt.json \
  --format markdown --check docs/generated/REPOSITORY-STATE.md
```

Read the checkout-derived facts separately, without touching the gate:

```console
python scripts/repository_snapshot.py \
  --source research/repository-state/active-work.json \
  --format markdown --local-facts
```

Missing receipts are `unavailable`, never zero. A stale receipt remains useful historical evidence but is not promoted into a current fact. The Markdown projection retains each supplied receipt's exact source SHA, timestamp and test command where applicable.

The `next_ready` array is a bounded **authored selection** from the capture. Validation proves that every listed issue is represented as ready and unblocked; it does not claim that the generator chose or objectively ranked those priorities.

## Updating the active-work capture

1. Read live open PRs and relevant issues.
2. Record only the active queue and immediate ready work; do not copy the entire historical issue list.
3. Preserve the exact capture time and default-branch work-state SHA.
4. Record the receipt revision in `facts_sha`, and the catalog/`HUMAN_TODO.md` Git blob IDs observed at capture time. Those blob IDs are an observation the checkout may later diverge from; they never gate generation.
5. Record each child’s immediate branch in `base`, but set every descendant’s `stack_parent` to the chain’s root PR.
6. Mark owner-run work explicitly; only one active owner-run lane is permitted by default.
7. Regenerate the snapshot and run its drift check.
8. Review any WIP-limit warning; do not edit the generated verdict.

## Evidence retention and archive

`CURRENT_STATE.md` remains the append-only evidence ledger for now. When it becomes materially difficult to load or review, move older dated sections into `docs/evidence/YYYY-MM.md`, keep a dated index at the top of `CURRENT_STATE.md`, and preserve Git history. Do not rewrite old measurements to match new definitions.

Generated snapshots are replaceable projections. Raw runtime, browser, model and private-media evidence remains under ignored `.runtime/` or the documented external evidence root. Do not commit private source art or credentials merely to make the snapshot self-contained.

## Scope of this first slice

Delivered here:

- the taxonomy and WIP contract;
- a structured issue form and concise-first PR template;
- an offline deterministic generator with separate work/receipt provenance, stale-receipt handling and a drift gate that depends only on committed capture evidence;
- root-owned stack validation and a one-owner-run-lane gate;
- a checked generated snapshot and CI drift gate;
- a bounded capture of the current active queue.

Still open under #315:

- applying labels to the wider active issue set;
- generating GitHub captures automatically through a reviewed connector/export path;
- deciding an exact ledger archive threshold after observing growth;
- refining the queue based on actual use without turning it into bureaucracy.
