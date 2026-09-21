# One-pass bounded JSON value framing

## Design and implementation plan, issue #401

The large-trace reader from merged PR #414 already provides opt-in streaming,
exact shared aggregation, strict EOF validation and the existing evidence-file
boundary. This change hardens that implementation; it does not introduce a
second trace format, reducer or file reader.

The original `_Values.value` attempted `JSONDecoder.raw_decode` on each growing
prefix after a short read. A long string arriving one byte at a time therefore
caused repeated decoding of almost the entire prefix. Values also reached the
strict decoder before the completed-value byte limit was checked.

Implementation sequence:
1. Lock the original parser's producer-fixture, short-read, cap and EOF contracts.
2. Reproduce repeated decode calls and oversized values reaching the decoder.
3. Frame one bounded value without decoding incomplete prefixes. Leave grammar,
   duplicate-key checks, exact Decimal numbers and aggregation with their existing
   owners. Check UTF-8 byte size before passing a value to the decoder.
4. Differential-test shared inputs, every split/prefix in selected fixtures and
   seeded producer-fixture mutations. Run the real Linux file and CLI suite.
5. Measure both the short-read work reduction and ordinary-read latency tradeoff;
   retain exact source/input/report identities and publish the evidence.

Base: `67f995f245518b36fb0192a61da780d337d53028`. No live profiler, model or
backend was contacted. No input file is rewritten and no output file is created
by the inspector; its result remains stdout only.

## Ownership and algorithm

`inference_trace_stream._Values` still owns the top-level trace envelope and
requires the final schema, complete document, trailing whitespace, real EOF and
expected hash before the shared reducer can return a report.

`inference_trace_values._JSONValues` owns a cursor over one decoded input chunk,
an incremental strict UTF-8 decoder and the byte-stream hash/count. A bounded
stack, quoted-string state and escape state frame a compound value. A delimiter
frames a scalar, so an incomplete fraction or exponent cannot commit a numeric
prefix. String runs are scanned with a regular expression; chunks are replaced,
not repeatedly concatenated to the entire value prefix. A `StringIO` accumulator
retains only the current bounded token. Each fragment's UTF-8 byte length is
checked before it is appended.

Framing is deliberately not JSON validation. The existing strict decoder sees
each complete token exactly once. Its duplicate-key hook, Decimal parser,
nonfinite-value refusal and common depth/surrogate validator remain authoritative.
The entire token must be consumed; framing a malformed object cannot make it
valid. No partial summary escapes after later corruption, a hash mismatch, an
incomplete UTF-8 sequence or a read error while establishing EOF.

The event reducer in `inference_trace.py` is unchanged: integer nanoseconds,
unsorted/nested interval union, lane/operator identities, redaction, unknown device
coverage and unverified job/producer identity retain their existing semantics.
The public `TraceError` import from the streaming module remains compatible.

## Bounds and entry point

All production caps remain fixed. Streaming permits at most 64 MiB input,
100,000 events, 256 KiB per JSON value, 64 top-level keys, 4,096 operator identities
and 64 lanes. Reads are at most 64 KiB; nested containers are limited to depth 32;
the final report stays within 64 KiB. The existing per-field restrictions remain.
The default eager reader stays at 1 MiB, 4,096 events and 128 operators.

```sh
python scripts/inspect-inference-trace.py saved-trace.json --stream --sha256 <exact-file-sha256>
```

The caller supplies one explicit saved file and, optionally, its expected hash.
The inspector neither submits generation nor estimates causal neural speedup.

The parser retains one bounded token and chunk. Exact interval aggregation still
retains intervals up to the fixed event cap; it is not constant memory independent
of event count. Interval sorting is unchanged. One-pass value framing is not a
claim that the complete inspection algorithm runs in linear time.

## Filesystem caveat: one parser pass is not one physical file pass

The existing `resource_receipts.read_evidence_stream` wraps this consumer with
regular-file/type/identity/size/change checks. Its later same-tick rewrite defense
performs a second bounded content-fingerprint read after parsing. That protection
is intentionally unchanged: removing it would let some same-length rewrites with
unchanged timestamps evade verification.

Consequently the parser consumes its supplied stream once, but the present CLI
can read the physical file twice. The issue's literal one-read wording needs to
be reconciled with this newer integrity requirement. This PR does not claim to
satisfy both by silently deleting a protection. Open work on the shared evidence
reader remains separate; this patch does not touch that file. Neither path is a
filesystem lease against hostile races after the verification interval.

## Local verification, 19 September 2026

Linux, Python 3.13.5. Direct GitHub cloning was unavailable. Original source and
all required dependencies were fetched through the GitHub connector and checked
against their Git blob IDs. Tests import complete real modules and run actual CLI
subprocesses, not extracted AST functions or substitute filesystem owners.

- Original streaming parser suite: **24 tests**, green before and after.
- New framing suite: **8 tests**, including deterministic decoder-call counts,
  predecode ASCII/multibyte/numeric byte limits, all two-piece boundaries for
  selected compound/scalar tokens, all incomplete fixture prefixes, duplicate
  escaped keys, read failure at EOF, report-cap timing and error-class compatibility.
- Original evidence-file and real CLI suite: **17 tests**, all passing on Linux.
  These cover incomplete consumers, bounded read requests, descriptor closure,
  source replacement/growth/in-place change, same-tick same-length rewrite,
  symlinks, FIFO refusal, read errors, large-file opt-in, hash binding and late
  errors without partial success or source/path disclosure.
- Combined trace command: `python -m unittest discover -s tests -p 'test_inference_trace_*.py' -v`:
  **49 passed, zero skipped**.
- The new permanent suite includes **300 seeded shared-input differential cases**.
  A separate **3,000 producer-fixture mutations** agreed across eager, original
  streaming and revised streaming readers: 1,107 accepted and 1,893 refused.
- Real repository CPU producer fixture through the complete `--stream` CLI:
  **8 recognized events**, no input mutation or added artifacts.
- All three requested workstream suites together: **85 tests passed**, zero skipped,
  in the fetched subset. This is not the full repository suite.
- `python -m compileall -q app scripts studio_workflow tests` and scoped
  `git diff --check` passed.

Fail-first runs reproduced the repeated-prefix and predecode-limit problems.
Self-review also caught and locked the legacy `TraceError` re-export. No Codex
review or cloud Actions result was used.

## Measured tradeoff, not a blanket speedup claim

Machine-readable trial data and source hashes are in
[`evidence/trace-value-framing-2026-09-19.json`](evidence/trace-value-framing-2026-09-19.json).

For a 16,046-byte trace containing a 16,000-character metadata string delivered in
one-byte reads, the original reader called the decoder **16,042 times**, presenting
**128,056,278 cumulative bytes**. The revised reader called it **5 times**,
presenting **16,037 bytes**. Complete reports matched. These are deterministic
work counters, not wall-time or allocation measurements.

The finite ordinary-read benchmark used 12,000 synthetic events, 2,048 argument
bytes per event and a 25,938,953-byte saved trace. Three trials per implementation
ran in fresh subprocesses, alternating implementation order. The eager bounds
were raised only inside the experiment to compare the same input; larger inputs
are not newly supported by the old default CLI.

| Implementation / run | Median milliseconds | Range milliseconds | Median process peak RSS |
| --- | ---: | ---: | ---: |
| Original streaming, pre-change run | 1,371.6 | 1,337.8–1,464.2 | 92.54 MiB |
| Revised streaming, final run | 1,507.6 | 1,471.1–1,513.6 | 92.67 MiB |
| Eager equal-bound comparison, final run | 1,285.6 | 1,280.2–1,297.8 | 171.54 MiB |

All 12 before/after eager/stream trial reports have the same input and result
hashes. Ordinary 64 KiB reads were slower with the new framing in this sample.
The change fixes short-read work amplification and enforces predecode bounds;
it does not establish a general latency or memory improvement over the original
streaming implementation. It retains streaming's lower peak memory than the
experimentally enlarged eager reader on this argument-heavy fixture.

Process RSS includes imports. These parser benchmarks exclude the file verifier's
second fingerprint read and do not measure full CLI I/O, Windows memory commit,
VRAM, live profiler allocations, real model performance or tail latency.

## Remaining acceptance

Keep #401 open for Windows file/CLI qualification and explicit reconciliation of
the one-physical-read wording with the existing same-tick integrity recheck. The
full repository validator/suite was not available in this sparse local checkout.
No claims are made about capture completeness, authenticated producer identity,
profiler overhead or accelerated neural execution.
