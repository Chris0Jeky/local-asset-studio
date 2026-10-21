# Bounded provider metadata transport

Implementation continuation for [#438](https://github.com/Chris0Jeky/local-asset-studio/issues/438), stacked on the offline source-snapshot parser in [#441](https://github.com/Chris0Jeky/local-asset-studio/pull/441).

This layer may perform an explicit public metadata GET to one reviewed Hugging Face or Civitai API endpoint. It cannot request model-file URLs, send credentials, install packages or nodes, execute a model, submit a graph, start training, or authorize generation.

## Why this layer is separate

The source system has four distinct stages:

1. **Transport** obtains bounded provider metadata bytes after explicit operator opt-in.
2. **Snapshot parsing** validates the provider payload and converts it into an immutable zero-authority proposal.
3. **Acquisition planning** may later select reviewed files and compile a separate download plan under #356.
4. **Inventory and qualification** reconcile acquired bytes and prove local compatibility under #9, #144 and the route qualification issues.

A successful transport operation proves only that one public metadata response was obtained or recovered from an exact cache identity. It does not prove that provider claims are correct, that the selected model is safe or useful, that terms permit a planned use, that any file has been downloaded, or that a route works locally.

## Public library API

```python
from studio_prompt.adult_illustration_source_transport import (
    BoundedProviderTransport,
    MetadataPolicy,
    SnapshotResponseCache,
    SnapshotEvidenceStore,
    fetch_civitai,
    fetch_huggingface,
)

transport = BoundedProviderTransport(
    policy=MetadataPolicy(
        timeout_seconds=15.0,
        max_attempts=2,
        max_redirects=3,
        max_response_bytes=2_097_152,
        retry_backoff_seconds=0.25,
    ),
    cache=SnapshotResponseCache(".runtime/adult-illustration/source-cache"),
    evidence_store=SnapshotEvidenceStore(".runtime/adult-illustration/source-evidence"),
)

result = fetch_huggingface("OWNER/MODEL", "EXPLICIT_REVISION", transport)
```

Importing the module performs no network or filesystem activity. The network exchange begins only when a caller invokes `fetch_huggingface` or `fetch_civitai` with a constructed transport.

The returned `studio.adult-illustration-source-fetch/v2` envelope contains:

- the validated `studio.adult-illustration-source-snapshot/v1` proposal;
- a transport receipt;
- a versioned raw-payload reference with its digest, exact byte count, retention state and, when retained, store and provenance identities;
- explicit false download, installation, execution, generation and training authority.

## Explicit CLI

The command refuses network access unless `--allow-network` is present:

```console
python scripts/studio_adult_illustration_source_fetch.py huggingface \
  --repo OWNER/MODEL \
  --revision EXPLICIT_REVISION \
  --allow-network \
  --cache-dir .runtime/adult-illustration/source-cache \
  --evidence-dir .runtime/adult-illustration/source-evidence \
  --out .runtime/adult-illustration/source-fetch.json

python scripts/studio_adult_illustration_source_fetch.py civitai \
  --version-id 123456 \
  --allow-network \
  --cache-dir .runtime/adult-illustration/source-cache \
  --evidence-dir .runtime/adult-illustration/source-evidence \
  --out .runtime/adult-illustration/source-fetch.json
```

`--out` uses exclusive creation. Existing files, symlink destinations and invalid parent directories are rejected before any provider exchange. Errors are machine-readable and keep every authority field false.

Use `--refresh` to conditionally revalidate an exact cached request. It does not select a newer model version or change the requested Hugging Face revision.

## Exact endpoint allowlist

Only these public metadata endpoint families are accepted:

- `https://huggingface.co/api/models/{owner}/{repo}/revision/{revision}?blobs=true`
- `https://civitai.com/api/v1/model-versions/{positive_version_id}`
- the equivalent `www.civitai.com` host for Civitai metadata

The following remain outside this transport:

- Hugging Face `/resolve/` and raw file paths;
- Civitai download URLs;
- model cards, images or arbitrary web pages fetched as HTML;
- custom-node repositories and package registries;
- provider search, recommendations, implicit latest versions or pagination discovery;
- private and gated resource access;
- any URL carrying user information or credentials.

Every redirect is followed manually. The destination must remain inside the same provider and the same reviewed metadata endpoint family. Cross-provider redirects and redirects to file endpoints are rejected before a second request.

## Request boundary

The parser constructs the initial request identity. The live transport accepts only:

- method `GET`;
- `Accept: application/json`;
- the reviewed Local Asset Studio user agent;
- no authorization, cookie, proxy authorization or API-key header.

The stdlib exchange disables environment proxy discovery, disables automatic redirect handling and asks for identity encoding. Python's default TLS verification remains active. There is no option in this layer to disable certificate or hostname verification.

Conditional validators are internal transport headers. They are derived only from a validated exact cache record and are not part of the caller-supplied request surface.

## Bounded retry policy

The defaults are:

| Control | Default | Allowed range |
| --- | ---: | ---: |
| Timeout | 15 seconds | greater than 0 and at most 120 seconds |
| Attempts | 2 | 1 to 4 |
| Redirects | 3 | 0 to 5 |
| Response bytes | 2 MiB | 1 byte to 2 MiB |
| Retry backoff | 0.25 seconds | 0 to 10 seconds |

Retries apply only to the reviewed GET operation after timeout, connection failure, HTTP 429, 502, 503 or 504. Backoff is bounded and exponential. A final non-200 response reaches the existing parser and is rejected. No write-like operation exists in this transport.

`Retry-After` is retained as response evidence where present, but it does not override the configured local bound or schedule unbounded waiting.

## Cache contract

`SnapshotResponseCache` stores only provider JSON metadata responses. It never stores model files, archives, images, credentials or executable content.

The cache key is SHA-256 over the exact canonical request identity:

- method;
- full URL;
- reviewed `Accept` value;
- reviewed user agent.

Each cache record also contains:

- strict schema identity;
- exact request identity;
- final URL and redirect chain;
- selected response headers;
- base64-encoded raw JSON response;
- byte count and SHA-256;
- persisted UTC write time (`stored_at`, ISO-8601);
- explicit false authority fields.

`stored_at` is the record's own write-time field. Filesystem mtime is never
used as a substitute. Legacy v1 records without `stored_at` remain readable;
their receipts report age unknown. A malformed or implausibly future
`stored_at` rejects the record instead of producing age evidence. There is no
TTL: a cache hit may remain indefinitely.

Cache reads revalidate the schema, request key, request identity, raw-byte count, SHA-256, strict JSON shape, JSON content type, final endpoint and every redirect endpoint. A tampered or stale envelope is rejected before provider parsing or network fallback.

Writes are atomic and occur only after:

1. transport-level bounds pass;
2. strict JSON parsing passes;
3. the provider-specific snapshot parser succeeds;
4. the parser's raw-payload SHA-256 matches the transport receipt.

This delayed commit prevents malformed but syntactically valid provider payloads from becoming cache hits.

A normal cache hit performs no network exchange. `--refresh` sends `If-None-Match` and/or `If-Modified-Since` when the exact cached response exposes those validators. HTTP 304 reuses the validated cached payload only when a validator was sent and any returned validator is consistent. Revalidation never upgrades evidence or changes authority.

## Immutable raw evidence (#694)

The request cache is mutable: a fresh 200 replaces the entry for that request.
It is not historical evidence storage. `SnapshotEvidenceStore` is optional and
independent of the cache. Without `--evidence-dir` or `evidence_store=`, a v2
export reports `retention_state: disabled`, even when the request cache is enabled.

The evidence store uses `payload-evidence.sqlite3` under its own directory. Raw
metadata bytes are keyed by SHA-256. One SQLite transaction publishes a body and
its bounded source-provenance record; existing digest bytes are never replaced.
Different bodies for the same request remain independently resolvable after a
refresh and process restart. Identical bodies share storage, while each fetch
keeps its own request, response route, allowlisted headers and acquisition record.

Retention is finalized only after the facade's provider parser succeeds and its
raw digest matches the transport-owned response. Cache hits and 304 responses
retain that operation's in-memory effective body; they never reread a cache that
another process may have refreshed. A 304 records `revalidated-304` provenance
pointing to the existing body, not a fabricated new wire payload. A cache hit is
recorded as `cache-hit`; a fresh response is `network-200`. `captured_at` is the
local capture/revalidation time, not an invented original provider observation
time. Cache-only legacy write times may remain unknown.

Evidence and cache publication are separate. Evidence storage/quota failure is
reported in the raw reference while the validated snapshot can still be returned.
A cache publication failure retains the existing transport exception/abort rules;
an evidence transaction may already exist, but no successful fetch export is
claimed. A raw caller retrying the same finalization does not append duplicate
provenance. Aborting discards owned response bytes and pending reference state.

### States and offline resolution

`raw_payload_ref` records `schema`, `sha256`, `body_bytes`, `cache_key`, `store_id`,
`observation_id`, `retention_state` and `detail`. The cache key is diagnostic
provenance; it never selects an immutable body. Store IDs avoid confusing a new
store at the same path with the original one. Moving/copying the complete store
preserves its ID. `retained` records a confirmed publication at capture time,
not a promise that a later lookup must still succeed.

| Capture state | Meaning |
| --- | --- |
| `retained` | The body and provenance transaction committed. |
| `disabled` | No evidence store was requested. |
| `quota_exceeded` | A declared budget refused retention; no existing evidence was evicted. |
| `publication_failed` | The transaction could not be confirmed. Bytes may exist after a lost commit acknowledgement; retention is not asserted. |
| `corrupt` | Existing evidence or its store failed identity/integrity validation. It is not silently overwritten. |
| `pruned` | An explicit pruning tombstone prevents automatic re-retention in that store. |

Resolve an export or its inner raw reference without provider access:

```console
python scripts/studio_adult_illustration_source_fetch.py resolve \
  --ref .runtime/adult-illustration/source-fetch.json \
  --evidence-dir .runtime/adult-illustration/source-evidence \
  --out .runtime/adult-illustration/resolved-evidence.json
```

The JSON result reports `available`, `missing`, `corrupt`, `pruned`,
`store_mismatch` or `unavailable`; an unretained capture preserves its specific
capture state. An `available` result contains hash-verified original bytes as
`body_base64` and the matching provenance. Resolution validates the count and
digest on every read and bounds body/provenance reads. `resolve` returns exit 0
for a completed lookup, including unavailable evidence: inspect `state`.
Malformed input/store errors return exit 2. Inputs are bounded to 4 MiB and
`--out` remains exclusive-create. Resolution does not create a missing store.

Library callers can use `store.resolve(ref)` or
`resolve_payload_reference(ref, evidence_store=store)`. These operations never
fetch, repair missing bodies, or grant download/execution authority.

### Retention budgets, concurrency and pruning

`EvidencePolicy` fixes a store's logical budgets at creation:

| Budget | Default | Maximum |
| --- | ---: | ---: |
| Raw body plus provenance bytes | 64 MiB | 256 MiB |
| Digest rows, including pruning tombstones | 1,024 | 100,000 |
| Observation/provenance rows | 4,096 | 100,000 |
| One raw metadata body | 2 MiB | Existing transport ceiling |
| One provenance record | 128 KiB | Fixed |

Use `--evidence-max-bytes`, `--evidence-max-payloads` and
`--evidence-max-observations` when creating a store, or pass `policy=EvidencePolicy(...)`.
Reopening without quota options uses the persisted policy. A conflicting policy
is refused before provider access; another writer cannot silently widen it.

Independent connections/processes serialize quota admission, deduplication and
pruning using `BEGIN IMMEDIATE`, with a two-second SQLite busy timeout. There is
no automatic eviction, retry loop or retention replay. The database uses FULL
synchronous commits and DELETE journaling, with a page allocation cap of twice
the logical byte budget plus 1 MiB. Logical quotas exclude fixed database/index
overhead; transactional journal space can temporarily require additional disk.
SQLite allocation or disk faults report failed publication rather than retention.
These are application-level bounds, not a claim of universal platform durability.

Pruning requires an explicit digest:

```console
python scripts/studio_adult_illustration_source_fetch.py prune \
  --evidence-dir .runtime/adult-illustration/source-evidence \
  --sha256 EXACT_PAYLOAD_SHA256
```

Pruning clears the body but retains provenance and a tombstone, so old references
report `pruned` after restart. It frees the body's logical byte budget; it does
not free digest/observation row quotas, shrink the database file or promise secure
erasure of SQLite pages. A pruned digest is not silently restored by a cache hit,
304 or later 200. For exhausted row budgets, archive the complete old store and
use a separately named new store; keep the old store for its references.
`prune` returns exit 2 if publication cannot be confirmed.

### Legacy v1 exports

Old v1 exports contain `{sha256, cache_key, retained_in_cache}`. That historical
boolean is not trusted as proof of availability. Supply the complete old export
and its original cache to `resolve --cache-dir PATH`, or use
`resolve_payload_reference(ref, cache=cache, request=original_request)`.
Only an exact matching request and body digest return `available`, explicitly
labeled `legacy-mutable-cache`. Missing or overwritten historical bytes return
`legacy_unavailable`; corrupt cache records remain `corrupt`. No newer body is
substituted, no historical timestamp is invented, and no network fallback occurs.

Raw retention proves the availability and identity of provider metadata. It is
separate from provider-claim validation, legal approval, model licensing, local
compatibility and execution authority. The original credential isolation,
provider allowlist, response/parser limits and false authority fields remain.

## Transport receipt

`studio.adult-illustration-source-transport-receipt/v1` records:

- provider and original request URL;
- deterministic request key;
- cache state: `disabled`, `miss`, `hit`, `refreshed` or `revalidated`;
- whether a network exchange occurred;
- attempts and redirects;
- effective policy limits;
- conditional validator names sent;
- wire and effective status;
- final metadata URL;
- response payload SHA-256;
- `cache_stored_at`: persisted UTC write time for `hit`/`revalidated`, else null;
- `cache_age_seconds`: measured seconds since `cache_stored_at` for `hit`/`revalidated`, else null;
- `credentials_used: false`;
- `model_bytes_downloaded: false`;
- false download/install/execution/generation/training authority.

`cache_stored_at` is `null` with `cache_age_seconds` `null` when age is
unknown: legacy records without `stored_at`, and `miss`/`refreshed` receipts
whose fresh 200 payload only commits to the cache on `finalize`. A 304
revalidation retains the original payload write time, so age means time since
this payload was stored, not time since validation. Age is informational, not
a freshness guarantee: there is no TTL and `--refresh` behavior is unchanged.

The receipt is evidence about transport behavior, not permission to use the source.

## Test boundary

Tests use injected fake exchanges only. They cover:

- Hugging Face and Civitai through the same transport interface;
- exact cache hits with zero exchange calls;
- conditional 304 revalidation;
- conflicting validators;
- timeout and rate-limit retries;
- same-provider metadata redirects;
- cross-provider and file-endpoint redirects;
- response and redirect bounds;
- credential rejection before exchange;
- HTML and oversized responses;
- cache corruption and endpoint tampering;
- output preflight before exchange;
- zero-authority result, snapshot, cache and receipt records.

CI invokes only `--help` for the live CLI. It never contacts a provider.

## Remaining gates

1. Review and merge #441 before this stacked transport PR.
2. Compile an explicitly reviewed source selection into the existing #356 acquisition-plan boundary. Preparing the plan must still download nothing.
3. Reconcile later acquired bytes through #9/#144 using exact hashes and inventory evidence.
4. Qualify graph compatibility, resource use, runtime behavior and creative quality under #405/#406/#409/#439.
5. Keep provider terms and the intended use under human review. A metadata transport receipt cannot clear rights.

No startup, UI, generation, installation or background process imports or invokes this transport automatically.
