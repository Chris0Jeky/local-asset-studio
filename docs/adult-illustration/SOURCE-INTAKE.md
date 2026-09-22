# Evidence-gated Hugging Face and Civitai source intake

Architecture for issue #433. Source discovery should make Local Asset Studio more reproducible, not turn a model page into an install button.

## Decision

A source page is an **external claim set**. It is not an installed model, a compatible route, a licence decision, a safe workflow or proof of artistic quality. The Studio must retain the exact provider identity and advance it through existing Model Library, acquisition, graph and experiment owners.

The evidence sequence is:

```text
discovered
  -> source snapshot proposed
  -> source and terms reviewed
  -> exact files selected
  -> bytes acquired with receipts
  -> hashes verified
  -> reconciled into existing inventory/bundle
  -> graph validated
  -> executed
  -> visually reviewed
  -> task accepted
  -> promoted
```

Every transition is explicit. A later state cannot be inferred from an earlier one.

## Provider identities

### Hugging Face

Retain:

- repository ID (`owner/model`);
- immutable commit revision, not only `main`;
- model-card revision and access date;
- every selected path;
- LFS/Xet pointer identity where exposed;
- expected bytes and SHA-256;
- config, encoder, tokenizer, VAE, adapter and auxiliary files needed by the proposed bundle;
- repository licence metadata plus any card-specific terms or restrictions.

A branch name, filename or page title is not an immutable model identity. Repositories can replace files while preserving familiar names.

### Civitai

Retain separately:

- model ID;
- model-version ID;
- file ID;
- AIR identifier where returned;
- model/version/file names;
- `baseModel` and `baseModelType` as provider claims;
- file size, primary flag and metadata;
- SHA-256 plus AutoV2/AutoV3/BLAKE3 or other returned hashes;
- creator-declared trigger words, settings and licence fields;
- exact page/API snapshot and access date.

Civitai's current developer documentation exposes version lookup by version ID and by recorded file hash. Hash lookup is useful for reconciling existing bytes, but a provider match does not establish local compatibility or permission. API/cache delay, removed versions, multiple files and mirrors remain explicit failure modes.

## Claims and observations

Never flatten these into one record:

| Record | Example | Authority |
| --- | --- | --- |
| Provider claim | “SDXL”, trigger words, recommended sampler | research input only |
| Provider file fact | file ID, bytes, SHA-256, AIR | source/file identity |
| Terms snapshot | licence text and creator permissions at access time | review input, not legal conclusion |
| Local inventory | bytes exist at a controlled path and hash matches | installed-file evidence |
| Graph validation | loader and node schema accept the exact bundle | structural evidence |
| Runtime observation | job completed with measured resources | execution evidence |
| Human review | identity/pose/style task accepted | creative evidence |
| Promotion | approved for a named task/route | explicit programme decision |

A sample image or embedded generation metadata is another provider claim. Never execute an embedded workflow merely because it was attached to an image or model page.

## Source-intake record

`research/adult-illustration/source-intake-example.json` demonstrates:

- provider-specific IDs;
- immutable or unresolved revision;
- claims separated from local evidence;
- file identities and hashes;
- source/terms state;
- explicit false download, install and execution authority.

The checked-in Civitai record is synthetic and exists only to exercise the contract. It must not be treated as a real model selection.

## Safe operator flow

1. **Discover** — paste a canonical URL or search read-only provider metadata.
2. **Snapshot proposal** — capture IDs, moving revision, terms, files and unresolved fields. No bytes are downloaded.
3. **Review** — select the exact version/files and inspect storage, terms, base lineage, component requirements and known incompatibilities.
4. **Pin** — resolve an immutable revision and exact expected hashes/bytes.
5. **Prepare acquisition** — emit a deterministic [zero-authority acquisition plan](ACQUISITION-HANDOFF.md) with destination, credentials boundary and checksum expectations. Preparation performs no network action.
6. **Acquire explicitly** — a separately authorized operation downloads to staging, records redirects and verifies bytes before promotion into inventory.
7. **Reconcile** — #9 records the exact bundle and detects duplicates or conflicts.
8. **Qualify** — #405/#406 validate graph, runtime, control behavior and accepted output.

## Implemented acquisition-plan boundary

The local-only planner consumes one validated `studio.adult-illustration-source-snapshot/v1` record and one explicit operator selection. It emits `studio.adult-illustration-acquisition-plan/v1` with:

- exact provider, immutable source and snapshot identities;
- one unique `.safetensors` file with positive bytes and SHA-256;
- one reviewed Model Library folder role and plain destination name;
- a bounded intended-use statement;
- an optional, explicitly unverified terms-review pointer;
- exact dry-run arguments for the existing Hugging Face or Civitai downloader;
- unresolved terms, collision, inventory, compatibility and storage gates;
- zero authorized candidates and false runtime authority.

Prepare and validate plans with:

```console
python scripts/studio_adult_illustration_acquisition_plan.py prepare \
  --snapshot snapshot.json \
  --file-id <exact-snapshot-file-id> \
  --destination-folder checkpoints \
  --destination-name candidate.safetensors \
  --intended-use "private local qualification" \
  --out acquisition-plan.json

python scripts/studio_adult_illustration_acquisition_plan.py validate \
  --plan acquisition-plan.json \
  --snapshot snapshot.json
```

The CLI reads bounded regular local files, rejects symlinks and duplicate JSON keys, preflights output paths, creates outputs exclusively and never imports or invokes a downloader. The plan is content-addressed, but a matching plan ID does not substitute for structural and semantic validation. See [Adult Illustration acquisition handoff](ACQUISITION-HANDOFF.md) for the complete contract and review checklist.

## URL and transport rules

- HTTPS only.
- Supported provider hosts only; no arbitrary URL fetcher.
- Never choose “latest” implicitly.
- Pin redirects and final source identity in the acquisition receipt.
- Do not send provider credentials to a mirror or include secrets in receipts.
- Bound metadata size, file count, description length and redirects.
- Treat HTML, archive contents and safetensors metadata as untrusted input.
- Reject path traversal, absolute paths, duplicate filenames and unexpected file types.
- Verify SHA-256 after download even when AutoV2 or another provider hash is available.
- Keep staged, verified and installed locations distinct.
- Do not overwrite a known file under a familiar name.

## Terms and publication

Capture the exact terms presented for:

- model weights;
- source code;
- outputs;
- commercial use;
- hosted services or model-as-a-service;
- redistribution;
- derivatives and trained adapters;
- creator-specific restrictions.

“Publicly downloadable” is not a licence. Provider metadata may be incomplete or contradictory. Store the snapshot and route unresolved use to review. Artistic acceptance, rights clearance and publication readiness remain separate states.

## Source changes

A subsequent intake of the same provider/version should produce a diff:

- page/card text changed;
- licence or permission changed;
- file added, removed, renamed or rehashed;
- `baseModel` or architecture claim changed;
- trigger words/settings changed;
- version unpublished or replaced;
- local file maps to a different provider record by hash.

Do not mutate the historical snapshot. Add a new revision and mark dependent plans stale where relevant.

## Agent contract

Agents may search, inspect and prepare a bounded snapshot proposal. They may also propose one exact file and destination and produce a deterministic zero-authority acquisition plan. The result must include:

- exact source and moving/immutable identity;
- proposed files with storage total;
- hashes present or missing;
- terms state;
- component and compatibility unknowns;
- existing-inventory matches;
- plan identity and unresolved gates where a file was selected;
- the next explicit approval boundary.

Agents may not download, install, activate, execute, accept terms, provide credentials, select a mirror, choose a latest version, or advance evidence merely because the provider API returned successfully or a plan validated.

## Acceptance path

The first complete proof should carry:

1. one checkpoint or diffusion model;
2. one LoRA/adapter;
3. one auxiliary control/tagger model;

from a source-reviewed snapshot to exact hash reconciliation through existing acquisition and inventory services. At least one intentionally malformed or changed source must fail closed with a useful diff.
