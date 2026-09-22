# Provider endpoint spelling and redirect admission

Follow-up to #433/#438 on the #579 public metadata transport. This is independent
of #687 framing, #732 snapshot consistency and #747 operation ownership; retain
those corrections when integrating the stack.

## Validate before interpretation

`urlparse` separates a final semicolon parameter from the path. Comparing only
that path admitted `.../model-versions/123;ignored` as version endpoint `123`.
URL parsing also removes some controls, and joining can remove dot segments or
repair an incomplete absolute reference. Checking only the resulting URL can
therefore approve a different spelling than the provider supplied.

Endpoint checks now use `urlsplit`, keeping semicolons inside the checked path.
A shared spelling check rejects raw non-ASCII/whitespace/control characters,
backslashes, fragments (including an empty fragment), malformed percent escapes
and literal or percent-encoded dot segments. Authority must be a supported host
with no userinfo and either no port or the literal port 443. An empty userinfo
component is not treated as the absence of one.

Redirect references receive spelling checks **before** `urljoin`; malformed
absolute HTTPS references and empty authorities also refuse. The resolved URL
then passes the existing provider-specific path/query and same-provider checks
before another exchange. This is intentionally stricter than a general browser:
`./123` is refused, not repaired. Ordinary relative revision references remain
valid. HTTP header outer whitespace normalization is unchanged.

Hugging Face revision components accept unreserved ASCII or well-formed percent
escapes, preserving encoded slashes and non-ASCII revisions. Valid request URL
bytes and request/cache hashes are not rewritten. Existing cache re-entry uses
the same stricter endpoint check and rejects newly disallowed stored routes; it
does not silently normalize or migrate old records.

## Scope and limits

This is metadata URL admission, not a general URI parser, DNS/network sandbox,
provider authentication, deadline, immutable payload retention, or proof of local
model compatibility. It does not add endpoint families, credentials, downloads,
installation, inference or execution authority. The offline source parser remains
a separate evidence reader; the live GET boundary is what this patch hardens.
HUMAN_TODO q-29 remains unchanged.

Reference: [Python URL parsing security](https://docs.python.org/3/library/urllib.parse.html#url-parsing-security).

## Offline checks

Seven regression methods use the real URL functions, fixture metadata and temporary
cache files. They cover initial admission, pre-follow refusal, cache re-entry and
valid relative/encoded revision controls without contacting providers.

```sh
python -m unittest tests.test_adult_illustration_source_endpoint_identity -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```
