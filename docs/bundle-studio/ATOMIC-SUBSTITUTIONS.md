# Atomic setup substitutions

21 September 2026 · review-first transaction slice for #144.

## Purpose

A setup component is not safely interchangeable by filename alone. Replacing one
checkpoint, transformer, encoder, VAE, accelerator or adapter may also require a
reviewed sampler, scheduler, step count, CFG value, companion removal, download,
memory change and evidence invalidation.

`studio_workflow.setup_substitution` turns that complete dependency set into one
bounded, deterministic proposal. The existing revisioned setup-draft service can
then append the reviewed result as one revision or leave the shared draft
unchanged. Planning never applies the proposal.

```text
exact shared draft
      +
typed compatibility request + recomputed report
      +
immutable reviewed substitution profile
      |
      v
studio_workflow.setup_substitution
      |
      +-- requested component change
      +-- required dependent settings
      +-- incompatible component removals
      +-- retained-evidence invalidations
      +-- download / memory implications
      +-- blockers and source status
      |
      v
canonical proposal JSON + SHA-256
      |
      | explicit approval + expected draft revision
      v
SetupDrafts action: substitute
      |
      +-- recheck exact proposal
      +-- recheck compatibility context
      +-- recheck before-values
      +-- recheck draft revision, runtime, graph and staged inputs
      |
      v
one new draft revision, or none
```

No step above downloads a model, installs a node, switches a backend, changes the
selected Create recipe, copies an input or submits generation.

## Input contract

The planner accepts `studio.setup-substitution-request/v1` with exactly. The CLI
reads at most 448 KiB plus one sentinel byte before decoding, so an oversized local
file is refused without an unbounded allocation:

- `draft` — the complete setup draft that the user is reviewing;
- `compatibility_request` — the typed target slot, candidates and retained
  evidence accepted by `studio_workflow.setup_compatibility`;
- `compatibility_report` — the exact report previously shown to the user;
- `candidate_id` — the selected candidate in that report;
- `profile` — one immutable reviewed dependency profile for that exact candidate.

The report is not trusted because it arrived from a caller. The planner
re-evaluates the compatibility request and requires byte-equivalent canonical
content. A changed or hand-edited report is refused.

### Reviewed profile

`studio.setup-substitution-profile/v1` separates four change classes:

1. `requested_changes` — the component change the user asked for;
2. `dependent_changes` — required values such as steps, CFG, sampler or
   scheduler;
3. `incompatible_components` — every bound control belonging to an adapter or
   companion that must be removed together;
4. `invalidations` — retained example, evidence or receipt controls that no
   longer describe the resulting bundle.

The profile also retains:

- candidate and exact resource identity;
- a content-addressed `sha256:<64 lowercase hex>` review revision; mutable
  labels such as `review:latest` are refused;
- component role;
- download status and byte estimate;
- memory-delta estimate;
- bounded explanatory notes;
- source locator, source revision, retrieval date and current/stale/blocked
  status.

Every changed or removed control carries its expected `before` value. If the
current draft is missing that control or its value changed, the entire proposal
is refused. Duplicate controls across requested changes, dependencies, removals
and invalidations are rejected rather than resolved by ordering.

Profiles are reviewed compatibility evidence, not an inferred interpretation of
a filename. They do not prove current inventory, installed bytes, runtime
support, licence permission or output quality.

## Example: accelerator substitution

A reviewed accelerator profile may produce this complete transaction:

```text
requested
  lora_name: old.safetensors -> accelerator-x.safetensors

required
  steps:     30 -> 8
  cfg:        5 -> 1
  sampler: euler -> dpmpp_2m

remove incompatible
  lora2_name: lora-y.safetensors -> absent
  lora2:      0.7 -> absent

invalidate retained evidence
  example_evidence: example-42 -> absent

implications
  download: required, 123456 bytes estimated
  memory:   -2048 bytes estimated
```

The proposal presents all seven control changes before approval. Applying only
the filename, keeping the incompatible adapter, or retaining the stale example
is not an available partial outcome.

## Compatibility states

The selected candidate keeps the evaluator's full hard conflicts, unknowns,
limitations, evidence summary and recommendation status.

- **Recommended** — applicable when the exact profile source is current.
- **Possible** — applicable without inventing a recommendation rank.
- **Needs review** — complete diff remains inspectable, but application is
  blocked until missing facts are established.
- **Incompatible** — complete diff remains inspectable, but hard conflicts block
  application.

Conflicting strong evidence remains visible and keeps a candidate at Possible;
it is not averaged into false confidence. A stale or blocked profile source also
keeps the full proposed diff visible while `can_apply` remains false.

## Canonical review boundary

The successful planner result contains:

- `before` and fully derived `after` drafts;
- the ordered requested, required, removal and invalidation changes;
- candidate compatibility evidence and diagnostics;
- invalidations, implications, source and source status;
- draft, compatibility-report and profile SHA-256 preconditions;
- explicit blockers and `can_apply`;
- canonical `proposal_json` and its SHA-256;
- false authority flags for provider access, installation, runtime switching,
  selection mutation and generation.

The proposal hash covers the request and all derived output. Canonical proposal
bytes are capped at 448 KiB so even worst-case JSON escaping fits the existing
1 MiB shared-command envelope. The shared-draft command requires both those
exact bytes and the acknowledged SHA-256. It recomputes the proposal before
writing.

## Atomic shared-draft application

Use the existing `setup_draft_command` surface with action `substitute`:

```json
{
  "action": "substitute",
  "workspace_id": "<32 lowercase hex>",
  "request_id": "reviewed-accelerator-x",
  "draft_id": "<draft identity>",
  "expected_revision": 4,
  "proposal_json": "<exact canonical proposal>",
  "approved_proposal_sha256": "<64 lowercase hex>"
}
```

The command uses the existing Studio lock, SQLite request journal, draft head
check, revision table and storage budget. Before appending it rechecks:

- request identity and exact proposal hash;
- recomputed compatibility report and profile;
- every reviewed before-value;
- current shared draft and expected revision;
- recorded backend identity, endpoint and root;
- graph identity;
- staged input identities.

A successful command appends exactly one revision containing the fully derived
draft. The previous revision remains readable. Repeating the same request ID and
content returns the original receipt instead of applying twice.

A stale revision is rejected before a request receipt is created. A proposal,
compatibility, runtime, graph or input mismatch records a failed receipt while
the draft head remains unchanged. A failed SQLite append rolls back the draft
revision and retains failure recovery through the request journal.

The substitution action has no staging phase and reports:

- an empty `staged` list;
- `staging_may_have_occurred: false`;
- `generation_submitted: false`.

Model download, installation, environment switching and generation remain
separate explicit workflows.

## CLI and agent boundary

Plan from retained local JSON:

```sh
python -m studio_workflow.setup_substitution substitution-request.json
```

Exit 0 prints the complete proposal. Invalid input exits 2 with a bounded
`invalid_substitution` error. The CLI has no apply, provider, install or generate
flag.

Agents use the same `setup_draft_command` contract as the application. Read
scope cannot submit the mutating command; author scope may submit an explicitly
approved `substitute` command. There is no agent-only bypass and no second draft
store.

## Current boundary

This slice does not yet:

- derive reviewed profiles automatically from filenames or provider prose;
- project live installed model inventory into the compatibility request;
- inspect the currently active ComfyUI node schema for every candidate;
- download or install missing bundle components;
- switch runtime environments;
- render the transaction in the Bundle/Create selector UI;
- claim that download or memory estimates are current measurements.

The parent stack supplies provider-neutral compatibility evaluation and the
retained Civitai/Civitai.red evidence bridge. This child supplies the complete
transaction and revision-checked application primitive. #144 remains open for
representative reviewed profiles, live inventory/schema projection and the
normal user-facing substitution flow.

## Regression coverage

The contract suite covers:

- one requested accelerator change plus dependent schedule changes;
- incompatible adapter removal and retained-example invalidation;
- deterministic proposal bytes and input immutability;
- stale or tampered compatibility reports;
- Recommended, Possible, Needs review and Incompatible states;
- conflicting strong evidence without invented confidence;
- current, stale and blocked profile sources;
- stale before-values, duplicate controls and non-finite values;
- exact candidate/resource identity binding;
- one-revision commit, retained history and idempotent replay;
- stale shared revisions;
- proposal tampering;
- runtime and graph drift;
- append failure without a partial revision;
- identical author-agent application and read-scope refusal;
- staged-input changes refused without explicit staging;
- zero uploads, staging, runtime switching and generation.

Refs #144 · #755 · #766
