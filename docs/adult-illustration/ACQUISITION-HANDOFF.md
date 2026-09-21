# Adult Illustration acquisition handoff

Issue #433 owns the boundary between a retained provider metadata snapshot and the existing model-file acquisition tools. This document describes the first implementation of that boundary.

The handoff is deliberately **zero authority**. It selects one exact file and prepares a checksum-pinned, dry-run-only command description. It does not contact a provider, run a downloader, accept terms, reserve storage, install a model, mutate the model library, start ComfyUI, submit generation or authorize training.

## State model

These records must remain separate:

| State | Evidence | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Source snapshot | Retained provider JSON, canonical provider identity, immutable revision/version, files and terms claims | What the provider reported at one point in time | Permission, local compatibility, installed bytes or quality |
| Acquisition plan | One validated snapshot, one selected file, one destination proposal and deterministic dry-run arguments | Which exact bytes an operator proposes to acquire | Download approval, destination availability or successful transfer |
| Transfer receipt | Separately authorized downloader result with final source, bytes and digest | What bytes were transferred and verified | Model-family compatibility or usable workflow binding |
| Inventory record | Reconciled local path, digest and bundle ownership | Which verified bytes are present locally | Graph validity, runtime stability or useful output |
| Qualification evidence | Exact graph, runtime, resources, attempts, failures and human review | What worked for a named task and configuration | Universal compatibility, unrestricted use or general artistic superiority |

A later record may reference an earlier record, but it may not rewrite it or infer missing evidence.

## Supported input

The planner accepts one fully validated `studio.adult-illustration-source-snapshot/v1` object from the source-snapshot and source-transport layers.

The source must be:

- Hugging Face or Civitai;
- non-synthetic;
- immutable and `pinned`;
- public metadata, with no private or gated Hugging Face access;
- free of disabled, deleted, draft, hidden, rejected, unpublished or taken-down state;
- non-executing and zero authority;
- structurally valid under the source-intake parser.

The selected file must be unique in the snapshot and must have:

- the provider-specific stable file ID;
- a safe relative `.safetensors` path;
- a positive byte count;
- a lowercase 64-hex SHA-256;
- `selected: false` in the immutable source snapshot.

The destination is a proposal only. Its folder must be one of the existing `studio_workflow.model_contracts.FOLDERS` roles, and its name must be a plain bounded `.safetensors` basename.

## Plan contract

`studio.adult-illustration-acquisition-plan/v1` retains:

- provider, source record and immutable revision/version identity;
- canonical source URL;
- canonical snapshot SHA-256 and raw provider-payload SHA-256;
- terms claims plus their own canonical SHA-256;
- exact source file ID, provider file ID where applicable, source path, bytes and SHA-256;
- provider-specific hashes as claims;
- destination folder, name and relative path;
- a bounded operator-authored intended-use statement;
- an optional terms-review reference, explicitly marked unverified;
- exact dry-run arguments for the existing provider downloader;
- unresolved human, storage, collision, inventory and compatibility gates;
- an `authorized_candidate_cap` of `0`;
- false download, install, execution, generation and training authority.

The plan ID is the lowercase SHA-256 of canonical JSON for the whole unsigned plan. Validation recomputes provider identities, file and destination identities, terms identity, handoff arguments, gate state and the plan ID. Supplying the original snapshot causes the plan to be rebuilt from that snapshot and compared exactly.

A malicious record is not accepted merely because an attacker recomputed `plan_id` after changing it.

## Local-only CLI

Prepare one plan:

```console
python scripts/studio_adult_illustration_acquisition_plan.py prepare \
  --snapshot .runtime/adult-illustration/source-snapshots/example.json \
  --file-id hf-file-0123456789abcdef0123 \
  --destination-folder checkpoints \
  --destination-name example-candidate.safetensors \
  --intended-use "private local route qualification" \
  --terms-review-ref HUMAN_TODO.md#q-29 \
  --out .runtime/adult-illustration/acquisition-plans/example.json
```

Validate a stored plan by itself:

```console
python scripts/studio_adult_illustration_acquisition_plan.py validate \
  --plan .runtime/adult-illustration/acquisition-plans/example.json
```

Rebind it to the exact retained snapshot:

```console
python scripts/studio_adult_illustration_acquisition_plan.py validate \
  --plan .runtime/adult-illustration/acquisition-plans/example.json \
  --snapshot .runtime/adult-illustration/source-snapshots/example.json
```

Omit `--out` to write canonical formatted JSON to standard output.

### Local file boundary

The CLI:

- reads local JSON only;
- reads at most 4 MiB per input;
- requires regular, non-symlink inputs;
- detects path replacement or size changes while a file is opened and read;
- requires strict UTF-8;
- rejects duplicate JSON object keys and non-finite values;
- preflights the output before reading or validating inputs;
- creates outputs exclusively and never overwrites an existing path;
- refuses output symlinks and symlink output parents;
- emits machine-readable zero-authority errors on expected validation or I/O failure.

The CLI imports neither downloader script and contains no provider client. `prepare` and `validate` perform no network operation.

## Provider-specific handoff

### Hugging Face

The source identity is `owner/model` plus an immutable 40-hex commit. The selected file ID is derived from its exact source path. The plan describes this dry-run shape:

```console
python scripts/fetch-hf.py \
  --repo owner/model \
  --path path/to/model.safetensors \
  --revision <immutable-commit> \
  --dest-folder checkpoints \
  --name example-candidate.safetensors \
  --dry-run
```

The acquisition-plan CLI does not execute that command. The existing downloader performs its own live metadata lookup and destination checks when an operator runs it later.

### Civitai

The source identity includes positive model-version and provider file IDs. The plan describes this dry-run shape:

```console
python scripts/civitai-fetch.py \
  --version-id 123 \
  --file-id 456 \
  --dest-folder checkpoints \
  --name example-candidate.safetensors \
  --dry-run
```

No credential is embedded. The plan records that any eventual transfer credential is external and unresolved. Public metadata access does not authorize a model download or acceptance of creator terms.

## Gates that remain unresolved

Every new plan starts with these gates:

| Gate | Initial state | Required follow-up |
| --- | --- | --- |
| Human terms review | `required`, or `reference_declared_unverified` when a pointer was supplied | A person reviews the retained terms and intended use |
| Destination collision | `unresolved` | Inspect the live model-library destination and partial files |
| Inventory reconciliation | `required` | Match any verified bytes to #9 inventory and bundle ownership |
| Local compatibility | `unresolved` | Review architecture, encoders, VAE, graph and runtime requirements |
| Storage budget | `unresolved` | Confirm destination capacity and the full proposed bundle cost |

A terms reference is a pointer to a possible human decision. It is never interpreted as a permission grant.

## Staleness and change handling

A plan is stale when any effective source input changes, including:

- raw provider payload identity;
- canonical snapshot bytes;
- provider model, revision, version or file ID;
- source path, byte count or SHA-256;
- terms claims;
- destination or intended use;
- planner schema or handoff rules.

Do not edit a historical plan in place. Retain it, create a new plan from the new snapshot and compare the records. A familiar filename or unchanged provider page title is not evidence that the bytes or terms are unchanged.

## Error record

Expected CLI failures return exit code `2` and emit `studio.adult-illustration-acquisition-plan-error/v1` on standard error. The record names the operation and error while keeping:

- `executable: false`;
- `authority: none`;
- every download, install, execution, generation and training authority flag false.

Argument-parser usage errors remain ordinary command-line errors. They occur before an acquisition operation exists.

## Operator review before any transfer

Before separately running a downloader, review all of the following:

1. The snapshot came from the intended provider resource and immutable version.
2. The selected file, byte count and SHA-256 are exact.
3. Required encoders, VAE, configs, adapters or auxiliary files are represented by separately reviewed plans.
4. The destination does not already contain a known file, partial transfer or conflicting asset.
5. Storage is sufficient for staging, verification and the complete bundle.
6. Terms are acceptable for the exact intended local, publication, commercial or service use.
7. Credentials, if required later, remain outside arguments, plans and receipts.
8. The transfer is explicitly authorized through the existing acquisition owner.

After transfer, reconcile the verified bytes into inventory before graph or runtime qualification. Do not treat a successful dry run, download or model load as artistic acceptance.

## Agent boundary

An agent may:

- inspect a validated snapshot;
- propose one exact file and destination;
- produce or validate a deterministic acquisition plan;
- explain unresolved gates and stale evidence;
- prepare a review diff.

An agent may not infer a latest version, select an unpinned mirror, accept terms, provide credentials, execute a downloader, install bytes, mutate configuration, submit a generation, mark a route compatible or promote a model based on this plan.

## Verification

```console
python -m unittest tests.test_adult_illustration_acquisition_plan -v
python -m unittest tests.test_adult_illustration_acquisition_plan_cli -v
python -m unittest discover -s tests -p "test_adult_illustration*.py" -v
python scripts/studio_adult_illustration_acquisition_plan.py --help
python scripts/validate-repo.py
```

CI runs the CLI help path and offline contracts only. It does not invoke either downloader.
