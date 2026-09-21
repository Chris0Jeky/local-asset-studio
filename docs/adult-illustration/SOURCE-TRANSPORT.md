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
)

result = fetch_huggingface("OWNER/MODEL", "EXPLICIT_REVISION", transport)
```

Importing the module performs no network or filesystem activity. The network exchange begins only when a caller invokes `fetch_huggingface` or `fetch_civitai` with a constructed transport.

The returned `studio.adult-illustration-source-fetch/v1` envelope contains:

- the validated `studio.adult-illustration-source-snapshot/v1` proposal;
- a transport receipt;
- a raw-payload SHA-256 and cache reference;
- explicit false download, installation, execution, generation and training authority.

## Explicit CLI

The command refuses network access unless `--allow-network` is present:

```console
python scripts/studio_adult_illustration_source_fetch.py huggingface \
  --repo OWNER/MODEL \
  --revision EXPLICIT_REVISION \
  --allow-network \
  --cache-dir .runtime/adult-illustration/source-cache \
  --out .runtime/adult-illustration/source-fetch.json

python scripts/studio_adult_illustration_source_fetch.py civitai \
  --version-id 123456 \
  --allow-network \
  --cache-dir .runtime/adult-illustration/source-cache \
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
- explicit false authority fields.

Cache reads revalidate the schema, request key, request identity, raw-byte count, SHA-256, strict JSON shape, JSON content type, final endpoint and every redirect endpoint. A tampered or stale envelope is rejected before provider parsing or network fallback.

Writes are atomic and occur only after:

1. transport-level bounds pass;
2. strict JSON parsing passes;
3. the provider-specific snapshot parser succeeds;
4. the parser's raw-payload SHA-256 matches the transport receipt.

This delayed commit prevents malformed but syntactically valid provider payloads from becoming cache hits.

A normal cache hit performs no network exchange. `--refresh` sends `If-None-Match` and/or `If-Modified-Since` when the exact cached response exposes those validators. HTTP 304 reuses the validated cached payload only when a validator was sent and any returned validator is consistent. Revalidation never upgrades evidence or changes authority.

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
- `credentials_used: false`;
- `model_bytes_downloaded: false`;
- false download/install/execution/generation/training authority.

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
