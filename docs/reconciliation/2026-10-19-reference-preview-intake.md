# Reference preview request allocation — 19 October 2026

## Scope and cause

The remaining aggregate-intake finding in issue #361 was on the exact
`POST /api/prompt/reference-review/preview` route. Its 48 MiB request was read in
one allocation, decoded to UTF-8 and parsed into base64 strings before any image
byte cap ran. The resulting body, parsed strings, up to four decoded originals
and Pillow work could overlap. The existing 8 MiB original and 16 MiPixel limits
did not bound those prior transport allocations.

This change keeps the existing JSON request and response. A scoped parser reads
the outer object and image rows in bounded chunks. It passes ordinary metadata
through the existing strict JSON decoder, and replaces each base64 token with an
internal captured-bytes object that cannot be constructed by JSON. Image type,
size, SHA-256, pixel and frame checks still run, followed by the existing
`reference_analysis.draft(..., source_bytes=...)` mandatory byte/hash checks.
There is no client verification flag, new dependency, filesystem publication,
model call, generation submission or UI step.

The browser still chooses up to four exact originals and previews the same
before/after intent. Field order, UTF-8, escaped slash and ASCII Unicode escapes
remain valid. Duplicate JSON keys remain invalid, including escaped duplicates
and duplicates encountered after earlier images have been captured. Existing
comma-containing selected tags and all prior review behavior are untouched.

## Bounds and ownership

| Boundary | Enforced behavior |
| --- | --- |
| Request framing | One decimal Content-Length, at most 48 MiB; no Transfer-Encoding or duplicate length headers |
| Body reads | At most 65,536 bytes per read; read1 when available; one 30-second read deadline |
| Metadata before JSON decoding | At most 1 MiB lexical bytes, 16,384 structure markers and 64 nested containers per value |
| Image count | Refuse a fifth image before consuming its string |
| Base64 | At most 11,184,812 decoded JSON characters per image; only complete, correctly padded base64 quanta |
| Decoded original | At most 8,388,608 bytes; check the next block's decoded size before base64 decoding allocates it |
| Retained originals | At most four original byte captures, 32 MiB total |
| Pixels and codec owners | Existing PNG/JPEG/WebP, 16 MiPixel and one-frame checks; explicit core closure and no previous codec owner at the next image open |
| Completion and refusal | Captures cleared on success, parse failure, I/O failure or dispatch refusal; previous socket timeout restored |
| Connection state | A failed preview closes; a fully consumed successful HTTP/1.1 preview may reuse its connection |

The 48 MiB wire allowance was not reduced. Four maximum originals need
44,739,248 base64 characters, about 42.67 MiB, leaving room for the 1 MiB metadata
allowance and framing within that existing cap. The full-envelope probe also
fills the remaining wire allowance with insignificant trailing whitespace.
Normal report, review and current-intent semantic caps remain below the separate
metadata ceiling. Large ignored helper-envelope fields now share that ceiling.

The bounded intake retains at most 32 MiB of compressed originals. Allowing an
additional current-buffer copy conservatively adds at most one 8 MiB original;
wire, base64 and decoded block buffers are individually about 64 KiB or smaller.
Metadata also has bounded lexical, structure and depth costs. Those figures are
transport accounting, not a total process memory guarantee. Pillow can create
additional Python and native codec buffers, especially for WebP. Multiple
concurrent clients can multiply per-request demand; this is not a host or worker
admission gate.

## Causal tests

The original implementation failed all eight initial regression tests, with ten
failures because the framing test has multiple cases. It requested one
1,051,626-byte read for a valid padded preview and read all 265,082 bytes of an
oversized-original fixture before refusing. It also accepted a valid JSON prefix
despite an incomplete declared body, accepted duplicate length headers, rejected
legitimate short reads and built deeply nested/oversized ignored metadata.

Further red tests established that leaving a Pillow context manager did not
release its decoded core, a previous codec owner survived at the next image open,
and trickle progress had no total read deadline. Each now has a passing causal
regression. The final direct matrix also covers base64 padding split across
1–7-byte reads, data after padding, escaped slash/Unicode forms, exact UTF-8 byte
accounting, decoded-size overflow at an unchanged base64 length, arbitrary field
order, malformed JSON, nonfinite numbers, duplicate fields after captures,
premature EOF, capture cleanup, socket-timeout restoration and request boundaries.

Real loopback HTTP tests use the production Host, origin and Content-Length
guards. They verify HTTP/1.1 connection reuse after success, refusal and closure
for incomplete/ambiguous requests, a stalled body deadline, both loopback origins
and the unchanged 1 MiB allowance on other routes and query variants.

## Full-envelope measurements

The retained measurement was executed on 19 October 2026 with Python
3.12.14, Pillow 12.3.0 and Linux x86-64. Each fresh measurement subprocess accepts
four distinct original images, each exactly 8 MiB and 4096 × 4096 pixels, in one
exactly 48 MiB JSON body. Both the original local baseline
`70e920ac8f355459643fd5f15fba9a48f7b5f3fa` and the modified handler return a verified
four-reference preview for PNG, JPEG and WebP. Baseline modules are read from
local Git; the fixture bytes are identical between implementations.

| Codec | Original Python peak | Streaming Python peak | Original RSS increase | Streaming RSS increase |
| --- | ---: | ---: | ---: | ---: |
| PNG | 140.07 MiB | 33.99 MiB | 200.77 MiB | 100.25 MiB |
| JPEG | 140.08 MiB | 33.98 MiB | 200.97 MiB | 100.18 MiB |
| WebP | 188.23 MiB | 97.64 MiB | 408.50 MiB | 299.91 MiB |

The original handler made one 50,331,648-byte read; the new handler made 768 reads
of at most 65,536 bytes. Python live allocations at the returned response were
about 1.44 MiB in these runs. The streaming cases took 0.62–1.14 seconds under
tracing. Timing is observational, not a performance threshold.

Python peaks come from tracemalloc and exclude native Pillow allocations. RSS
includes Python, native codecs and allocator behavior; it must not be added to
the Python column. Linux measurements use `/proc/self/status` VmRSS/VmHWM, with
the pre-request RSS subtracted for the increase column. A first probe using a
numeric psutil PID was discarded because the sandbox PID namespace did not
match its mounted `/proc`; the corrected probe reads `/proc/self` directly.
No production memory-admission code was changed.

Fixtures are uniform-colour images padded to the compressed-byte cap. They cover
the full supported count, byte and pixel envelope, not every worst-case codec
allocation. Fixture construction and file-backed body bytes are outside each
measured subprocess. WebP remains substantially more expensive than PNG/JPEG;
neither these figures nor the pixel check certify arbitrary codec peak memory,
concurrent-request memory, host generation headroom or real vision quality.

Reproduce on the checked-out change:

```bash
python tests/reference_preview_memory.py --output .runtime/reference-preview-intake/memory.json
```

To compare an available local baseline, add `--baseline <local-git-revision>`.
The JSON receipt includes implementation file SHA-256 values, interpreter and
Pillow versions, full byte counts and both memory measures. Session evidence is
retained under `.runtime/reference-preview-intake/`: the original red logs,
pixel/codec/deadline red logs, discarded measurement diagnostic, and
`memory-envelope.json` with the final 48 MiB run.

## Verification and disposition

The focused final checks are recorded in the accompanying change: the new direct
intake matrix, existing/expanded review family, existing analysis contracts and
repository validator. The actual published head still requires the repository's
full hosted CI and independent review before merge; a local focused pass is not
a substitute for those gates.

This completes the aggregate preview-intake acceptance of #361. Its previously
delivered review findings remain separate completed evidence. Closure is
appropriate after current-head qualification confirms the combined issue
acceptance. This work does not establish VLM understanding, model/runtime
performance, repair quality, generation success or art acceptance. Existing
owner decisions and HUMAN_TODO items remain unchanged.
