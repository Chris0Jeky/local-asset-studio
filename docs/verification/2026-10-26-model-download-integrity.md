# Model download integrity follow-up — 2026-10-26

Issue: [#1633](https://github.com/Chris0Jeky/local-asset-studio/issues/1633)

## Scope and disposition

This follow-up covers publication recovery reporting, the ordering of the direct
peer check and TLS handshake, and deterministic offline transport coverage. It
does not download weights or run a generation backend.

| Issue finding | Disposition |
| --- | --- |
| Windows recovery can fail when a reader denies share-delete | Recovery remains best effort. Both rename refusals are tested, and the failure identifies the published file that still needs inspection. There is no guarantee that unverified bytes can always be moved aside. |
| Quarantine path and cleanup instruction can be lost | Publication failures carry the full `unverified_path` and `cleanup` fields. Both model-library receipts and browser-intake journals retain them separately from bounded message text. |
| Direct peer policy ran after TLS | The connection now performs the TCP connect, checks the direct peer, and only then wraps TLS. A disallowed rebound peer receives no TLS handshake or HTTP request. |
| Transport injection and ambient proxies obscured coverage | The guarded HTTPS handler remains installed when other handlers are supplied. Explicit HTTPS fixture replacement remains a trusted tests-only seam. Tests control proxy configuration and cover direct connections and CONNECT proxies separately. |
| A next-hop peer rejection allegedly leaked the previous redirect response | Not reproduced. The causal regression demonstrates the previous response is closed before the next connection begins. No production redirect change is needed for this claim. |

## Recovery contract

`publish_verified` still attempts a no-clobber rollback to the staging name and,
if that fails, a unique `.unverified` quarantine name. A persistent Windows
share-delete denial can prevent both operations. That case leaves the published
path in place and records instructions to avoid loading it, close any reader,
then inspect and move or remove the file manually before retrying.

When rollback or quarantine succeeds, the exception names the actual retained
path and asks for manual inspection and cleanup when the file is no longer
needed. Reporting does not delete that file. A competing staging file is also
preserved. The `unverified_path` field is not limited by the model-library
message's 300-character budget or the intake journal error's 500-character
budget. `cleanup` is retained separately, and the library message begins with
the actionable instruction.

The full fields are available in the model-library failure receipt returned by
the library snapshot and in the browser-intake `needs_inspection` journal. These
are failure records, not installed verification receipts. Path retention is
evidence about this failure; another process may subsequently move or change
the file.

## Transport contract

The direct peer can be inspected only after a TCP connection exists. The guard
prevents TLS and HTTP from reaching a disallowed direct peer; it cannot prevent
the initial TCP connection. Normal HTTPS uses the existing verified SSL context
and the origin hostname for SNI and certificate checks.

A configured CONNECT proxy owns destination resolution and routing. Its socket
peer is the proxy, so it is not classified as the origin server. Proxy behavior
is explicit trust in that operator configuration. TLS through the tunnel still
authenticates the origin hostname. The tests cover a private proxy address,
CONNECT sequencing, SNI, a valid local certificate, and hostname rejection in
both direct and proxy modes.

`transport_handlers` is a trusted Python tests-only injection point, not a URL,
catalog or user-configuration option. An explicit HTTPS fixture handler may
replace socket handling for inert loopback tests. Supplying an unrelated handler
alone no longer removes the guarded HTTPS transport. Production callers do not
supply this seam.

The redirect characterization uses the real urllib redirect path with inert
response bytes. The first response has a body; its close event must occur before
the rejected second connection is dialed. Local CPython 3.12 and the inspected
[CPython 3.14 redirect implementation](https://github.com/python/cpython/blob/v3.14.0/Lib/urllib/request.py)
both drain and close the prior response before `parent.open` begins. A peer
failure during that subsequent open therefore does not cause the alleged prior
response leak. The
[CPython 3.14 HTTPS connection implementation](https://github.com/python/cpython/blob/v3.14.0/Lib/http/client.py)
also confirms the preserved TCP/CONNECT, origin-SNI and SSL-context sequence.

## Verification

The targeted red phase ran the new behavior assertions against unchanged
production code: installation recovery had five assertion failures; peer
transport had seven assertion failures (including five rebound-address
subtests); intake journal retention had one assertion failure. The redirect
close characterization passed before any production change.

The focused verification command is:

```console
PYTHONPATH=tests python -m unittest test_model_install_safety test_model_library test_model_intake test_model_download_transport test_model_redirects
python scripts/validate-repo.py
git diff --check
```

The five test modules passed: 115 tests in 5.994 seconds, with five existing
platform skips on this Linux checkout. The repository validator passed with 93
preset graphs/bindings, 187 pinned assets and 4,440 tracked paths; the staged
diff check was clean. The real TLS fixture exchanges five inert bytes over a
local socket pair using its own test trust context; the existing redirect tests
use a temporary loopback server. All resolver/provider responses are inert or
mocked. No provider request, model download, runtime start or generation is part
of these checks.

Native Windows share-delete behavior is covered by deterministic rename-denial
fault injection here, not a native Windows execution. Full repository and
hosted integration validation remain separate publication gates.
