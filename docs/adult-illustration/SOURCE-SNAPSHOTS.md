# Bounded Hugging Face and Civitai source snapshots

Implementation slice for [#438](https://github.com/Chris0Jeky/local-asset-studio/issues/438). It turns one retained provider API response into an immutable, zero-authority source proposal. It does **not** download a model, install a node, accept terms, call ComfyUI, select a route, or prove local compatibility.

This is the executable parsing layer beneath [Source intake](SOURCE-INTAKE.md). It accepts an injected transport and is independently usable with the local-response-only CLI for reproducible fixtures, operator-captured responses, audits and agent dry runs. The separate [bounded provider metadata transport](SOURCE-TRANSPORT.md) implements an explicit public GET boundary without changing the parser's authority or provider semantics.

## Boundary

A successful snapshot proves only that:

- one explicit provider request identity was constructed;
- a bounded JSON response was parsed;
- provider and response identities matched;
- file, hash, lineage, access and terms claims were retained where present;
- the raw response bytes received a SHA-256 identity;
- every model-byte, installation, execution, generation and training authority stayed false.

It does not prove that a returned hash is authentic, that every required component was listed, that the terms are complete, that the files are safe, that the route fits the RX 9070 XT, or that the model produces useful artwork.

## Library contract

`studio_prompt.adult_illustration_source_intake` exposes:

```python
from studio_prompt.adult_illustration_source_intake import (
    HttpRequest,
    HttpResponse,
    snapshot_huggingface,
    snapshot_civitai,
    diff_snapshots,
    read_snapshot_json,
)
```

The snapshot functions accept an injected callable:

```python
def transport(request: HttpRequest) -> HttpResponse:
    ...
```

The parser invokes it exactly once. It does not retry, follow redirects itself, inspect credentials, write files or select a default network client. Callers may use a fake transport, the retained-local-response adapter, or the separately reviewed `BoundedProviderTransport`. The transport must satisfy its own credential, TLS, timeout, redirect, cache and audit boundary before returning an `HttpResponse`.

## Hugging Face proposal

The adapter requires:

- an exact `owner/model` repository ID;
- an explicit requested revision;
- a matching response repository ID;
- a returned immutable 40-hex commit;
- safe unique POSIX file paths;
- positive byte counts where published;
- valid SHA-256, LFS and Xet identities where published.

It retains provider claims such as licence, base model, pipeline, library, tags, language and access state. `private`, `gated` and `private_gated` remain visible and never turn into an automatic credential or acquisition flow. Every returned file begins with `selected: false`.

## Civitai proposal

The adapter requires one explicit positive model-version ID. It never chooses “latest.” The response must return that exact version plus a positive model ID.

It retains:

- model, version and file IDs;
- AIR identity where present;
- base-model and base-model-type claims;
- version/model names and type;
- trigger-word claims;
- primary/file-type/format metadata;
- byte counts and provider hashes;
- creator/provider permission fields as a terms snapshot.

Those permission fields remain claims for later review. Public availability, a version ID or a file-hash match does not establish local compatibility, redistribution rights, hosted-service permission or artistic acceptance.

## Parser and transport invariants

The common response boundary rejects:

- non-HTTPS request, final or redirect URLs;
- provider-crossing redirects or more than five redirects;
- request/response identity mismatches;
- non-200 responses;
- non-JSON content types;
- responses larger than 2 MiB;
- malformed UTF-8 or JSON;
- duplicate object keys;
- NaN or infinity;
- more than 20 levels of JSON nesting;
- excessive nodes, strings, arrays, files, tags or claims;
- absolute, parent-traversing, colon-containing or backslash file paths;
- duplicate file paths and provider file IDs;
- malformed sizes and hashes.

Selected response headers are retained in a bounded allowlist. Credentials, cookies and authorization headers are never copied into the snapshot.

The live transport adds stricter endpoint-family validation, explicit timeout/retry/redirect limits, proxy-disabled stdlib exchange, conditional cache validation and a transport receipt. The snapshot parser remains the authority for provider-specific payload semantics.

## Snapshot structure

Each proposal uses `studio.adult-illustration-source-snapshot/v1` and contains:

- provider and request identity;
- final URL, redirect chain and selected response headers;
- raw payload SHA-256;
- provider-specific source record;
- immutable revision where proven;
- access, terms, lineage and metadata claims;
- unselected files and hashes;
- explicit false authority fields.

The record is compatible in spirit with `studio.adult-illustration-source-intake/v0`, but it remains a proposal. Promotion into the checked-in source-intake catalog should be an explicit reviewed diff rather than an automatic write.

## Local-response CLI

The local-response CLI never opens a socket. Supply one retained raw provider JSON response:

```console
python scripts/studio_adult_illustration_source_snapshot.py huggingface \
  --repo OWNER/MODEL \
  --revision EXPLICIT_REVISION \
  --response path/to/huggingface-response.json \
  --out path/to/source-snapshot.json

python scripts/studio_adult_illustration_source_snapshot.py civitai \
  --version-id 123456 \
  --response path/to/civitai-response.json \
  --out path/to/source-snapshot.json
```

Compare two immutable proposals:

```console
python scripts/studio_adult_illustration_source_snapshot.py diff \
  --before path/to/older-snapshot.json \
  --after path/to/newer-snapshot.json
```

Output files are exclusive-create. Errors are machine-readable and retain false download/install/execution/generation/training authority.

For explicit live metadata acquisition, use `scripts/studio_adult_illustration_source_fetch.py` only through the controls documented in [Source transport](SOURCE-TRANSPORT.md). It requires `--allow-network`, accepts no credentials and cannot request provider file endpoints.

## Snapshot diffs

Two snapshots must represent the same provider source identity. The diff records:

- raw payload change;
- added, removed and changed files;
- terms change;
- lineage change;
- access change;
- metadata change;
- deterministic diff identity.

Historical snapshots are never rewritten. A changed source should instead stale dependent acquisition, bundle and qualification plans.

## Next implementation gates

1. Review and merge the offline parser and stacked bounded transport in order.
2. Compile reviewed file selections into the existing #356 acquisition plan. Preparation downloads nothing.
3. Reconcile acquired bytes through #9/#144 inventory and bundle ownership.
4. Run graph/runtime/creative qualification under #405/#406/#409/#439.
5. Preserve provider terms and intended-use decisions for human review.

No later gate should mutate the source snapshot into evidence it did not originally contain.

## Verification

Focused parser tests cover provider identity, immutable revision resolution, file hashes and AIR, gated/private metadata, cross-provider redirects, content type/status, duplicate/non-finite/deep/oversized JSON, unsafe and duplicate files, immutable diffs, local-only CLI operation and exclusive output.

The live-transport tests use injected fake exchanges only and additionally cover exact cache hits, ETag revalidation, retries, redirect endpoint families, credentials, cache corruption, output preflight and transport receipts. CI never contacts a provider.
