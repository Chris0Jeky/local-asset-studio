# Provider metadata response framing

Follow-up to #438 and #433. See [SOURCE-TRANSPORT.md](SOURCE-TRANSPORT.md) for endpoint, credential, redirect, cache and authority policies.

## A valid JSON document is not proof of a complete HTTP message

The default exchange reads through the real stdlib HTTP parser with a byte cap. A bounded `HTTPResponse.read(amount)` can return a complete JSON prefix when the connection closes before the advertised Content-Length. The transport now checks raw framing before reading and checks the declared body size afterwards.

| Wire condition | Result |
| --- | --- |
| One decimal Content-Length within the cap; all declared bytes arrive | Continue to media-type, JSON and provider-identity validation |
| Declared length exceeds the active cap | Refuse before body reading |
| Peer closes before the declared length | Connection failure; only the existing bounded GET retry policy applies |
| Duplicate Content-Length, including equal duplicates | Refuse instead of repairing ambiguous provider evidence |
| Invalid Content-Length, multiple Transfer-Encoding fields, unsupported transfer coding, or both length and transfer coding | Refuse before body reading |
| Properly framed chunked response | Retain the bounded decoded body; existing HTTP parse failures remain connection failures |
| No framing length and no transfer coding | Retain the bounded close-delimited body |
| Bodyless status such as 304 | Do not require the advertised representation bytes; existing cache-validator and exact-route checks still decide acceptance |

Duplicate lengths are deliberately rejected even where a general HTTP client could normalize identical duplicates. This metadata client does not need that permissive repair.

No failed read is finalized into a provider snapshot or cache record. The change grants no download, installation, execution, generation, training or promotion authority. Provider-supplied model hashes still do not verify downloaded model bytes.

## Regression and verification

`tests/test_adult_illustration_source_framing.py` feeds raw HTTP bytes into the real `http.client.HTTPResponse`, backed by in-memory bytes rather than a socket. It covers truncated-but-valid JSON, retry exhaustion, closed responses, absent receipt/cache publication, duplicate/conflicting headers, pre-read size rejection and successful framing controls.

Run:

```sh
python -m unittest discover -s tests -p 'test_adult_illustration_source*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

## Limits not changed by this patch

Close-delimited responses have no declared byte count against which to detect a shorter, still-valid JSON document. HTTP framing verification is not an authenticated provider content signature. The socket timeout is not an end-to-end wall-clock deadline, and decoded-body size is not a separate wire/chunk-extension/trailer budget. Historical payload retention and cache replacement remain separate concerns.

Protocol reference: [RFC 9112 section 6.3](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3). The implementation intentionally remains a strict metadata reader, not a general HTTP framing parser.
