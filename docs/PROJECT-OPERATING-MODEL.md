# Repository operating model

This guide keeps Local Asset Studio's active queue legible while preserving the detailed evidence that makes the project reliable. It records the operating model delivered for issue #315. It does not replace GitHub, `STATUS.md`, `CURRENT_STATE.md`, `HUMAN_TODO.md` or the domain-specific runbooks.

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

Review ledger size during planned monthly maintenance. `CURRENT_STATE.md` remains the dated execution ledger; `docs/STATUS.md` remains the current assessment. A new result may supersede an old claim by a dated correction, but it never silently replaces that claim or converts a failed check into a pass.

When the ledger exceeds **1 MiB**, an archive PR may move completed calendar-month sections older than **90 days** to root-level `CURRENT_STATE-YYYY-MM.md` files. Keeping archived ledgers at the same path depth preserves their existing relative evidence links. This is a bounded maintenance procedure, not a new CI gate or automatic scheduled job. No archive is required for the 26 October capture, whose ledger is below that threshold.

An archive change must:

1. Keep active work, unresolved defects, pending qualification, uncertain commands and owner decisions in the current records. An old date alone never makes a section complete.
2. Keep each failure, causal investigation and later correction together. If a related sequence spans months or remains unresolved, leave the whole sequence in the live ledger until it can be moved without losing context.
3. Copy the selected section bodies exactly, including source SHAs, prompt IDs, timings, limitations and original wording. Before removing the duplicated bodies from the live ledger, compare the original and archived bytes and retain their SHA-256s in the archive PR evidence.
4. Leave each original heading in `CURRENT_STATE.md` with a link to the archived heading, preserving incoming anchors. Add the covered dates, source revision and root-level archive links to `docs/history/README.md`. Verify both embedded evidence paths and fragment targets before moving a section. If exact copying would break a cross-section anchor, retain the linked section group in the live ledger until it can be archived coherently. Do not move supporting verification documents or rewrite evidence bodies just to reduce ledger size.
5. Keep `HUMAN_TODO.md` authoritative and unchanged by archival. A completed generation or passing suite cannot convert an owner choice into acceptance.
6. Run repository validation, check the retained heading links and all embedded archive path/fragment links, and review the resulting current assessment and active-work capture. A historical correction belongs beside the original record or in a dated linked annotation, never in a silently edited receipt.

Generated snapshots are replaceable projections. Raw runtime, browser, model and private-media evidence remains under ignored `.runtime/` or the documented external evidence root. Do not commit private source art or credentials merely to make the snapshot self-contained.

Git history remains available, but is not the only locator for moved evidence: the live heading links, archive index and source revision keep the record discoverable. Labels, automated GitHub capture and a project board are optional future conveniences; the documented taxonomy, authored bounded capture and deterministic generator are sufficient to operate this model without a mandatory external service.

## Delivered operating model — 26 October 2026

The operating-model acceptance in #315 is represented by:

- the taxonomy/readiness tables and bounded active issue/PR capture;
- the authored next-ready list with explicit dependencies;
- the linked WIP limit, root-owned stack validation and single owner-run lane;
- the deterministic generated view, SHA-bound CI receipts and drift check;
- current authored `docs/STATUS.md` alongside the dated `CURRENT_STATE.md` ledger and the retention procedure above;
- the concise-first PR template and evidence-linked implementation PRs;
- explicit owner overrides and maintenance bypass without a mandatory external service.

Labels for a wider issue set, automated connector capture and further queue refinements may be proposed as independent improvements when needed. They are optional representations or conveniences, not prerequisites for the delivered model. GitHub remains authoritative for live work; the checked capture always states its observation time.
