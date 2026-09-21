# Larger saved traces without a whole-document object graph

15 September 2026. #401 under #364/#374/#172. Based on main
`b29205cfc95ca4e64d72ae38d53df30c83968997`; independent of the open #383
fixed profiler probe and of the figure-crop preparation change.

## Use and compatibility

```bash
# Existing small-reader mode, unchanged limits and v2 summary semantics:
python scripts/inspect-inference-trace.py .runtime/short-trace.json
# Explicit larger, incremental mode; no runtime is contacted:
python scripts/inspect-inference-trace.py .runtime/model-trace.json --stream
python scripts/inspect-inference-trace.py .runtime/model-trace.json --stream --sha256 <exact-file-sha256>
```

The command writes only JSON to stdout. Exit 0 means supported saved-trace
inspection, not complete capture, verified producer, successful generation or
usable performance evidence. Exit 2 returns a fixed, payload-free refusal. A late
syntax error, wrong hash or changed input returns no partial success metrics.
The tool does not create output files, install/import Torch, attach to ComfyUI,
start a worker, submit a job or change #383's default probe.

The existing `studio.inference-trace-summary/v2` shape and meanings stay intact.
Reports on shared valid inputs are exactly equal across readers. Small mode
retains its existing acceptance; large mode additionally bounds individual JSON
values and top-level keys. Both keep producer identity unverified, job association
unbound and inference-speed qualification false. See [TRACE-READER](TRACE-READER.md)
for supported event categories, privacy, inclusive totals and cross-lane limits.

| Bound | Default reader | Explicit `--stream` |
| --- | ---: | ---: |
| Saved input bytes | 1 MiB | 64 MiB |
| Events including ignored events | 4096 | 100,000 |
| Distinct category/operator identities | 128 | 4096 |
| Category/process/thread lanes | 64 | 64 |
| Displayed operator rows | 32 | 32 |
| Encoded report bytes | 64 KiB | 64 KiB |
| JSON container depth, root = 1 | 32 | 32 |
| Individual event or metadata value | Overall input cap | 256 KiB UTF-8 |
| Top-level keys | Overall input cap | 64, each at most 256 characters |
| File read request | Bounded whole input | At most 64 KiB |

There are no CLI switches for arbitrary limit increases. An oversized event or
metadata value is refused even when the complete file is below 64 MiB. A 4096-name
model capture may still exceed these limits; refusal is not evidence that the
missing portion contained no work.

## Architecture and lifetime

```text
existing evidence-file owner
  regular/plain-directory check + descriptor/path identity bracket
    bounded read-only consumer view
      incremental UTF-8 decoder + one JSON value + lookahead chunk
        common exact event reducer
          bounded interval pairs + operator aggregates
      validate closing structure, schema, complete EOF and source hash
  recheck descriptor/path identity and total bytes before returning
redacted v2 report
```

`inference_trace._summarize_events` is the single event interpreter shared by the
small reader and the incremental reader. The new reader yields validated values
and discards event arguments after each iteration; it does not duplicate the
category rules, nanosecond arithmetic, redaction, row ranking or interval union.
Unsorted and overlapping spans retain exact union semantics. Operator totals can
span several lanes and remain explicitly inclusive, not wall time or self time.

Retained timing intervals are **O(number of recognized events)**, capped by the
100,000-event ceiling. Sorting the interval pairs needs additional bounded
scratch. This is not constant-memory parsing of an unlimited trace. What is
removed is the full input byte string, decoded full document and retained argument
object graph. A 256 KiB value can itself expand into Python objects; that is a
bounded value limit, not an exact process-memory quota.

The stdlib JSON decoder can accept a numeric prefix before its exponent or
fraction has arrived. The parser waits for a legal delimiter or actual EOF and
checks the value cap **before** fetching another chunk. Incremental UTF-8 handles
split code points. Ignored metadata is still parsed and validated: it is not an
unvalidated escape hatch for duplicate keys, malformed numbers or deep payloads.
Top-level keys may arrive in any order; `schemaVersion` is checked even when it
follows `traceEvents`. Trailing whitespace is hashed; extra documents refuse.

The source hash covers every consumed raw byte. Matching it proves byte identity,
not provenance or association with a particular job. The filesystem owner refuses
an incomplete consumer and reuses the existing before/after type, identity, size
and timestamp checks. The consumer API is trusted Python code, not a sandbox;
conservative plain-directory/reparse restrictions are unchanged. Ordinary source
replacement or growth cannot turn an observed subset into a successful report.
Other resource-receipt parsing, schemas and #359's timing concerns are untouched.

Rejected alternatives: merely raising the eager-reader limit (larger object
graph); a new trace database/service (unnecessary ownership); approximate interval
union (would change the evidence semantics). No mandatory parser dependency was
added for this bounded subset.

## Implementation and proof

The sequence was failing contracts -> shared reducer extraction -> incremental
parser -> existing-file-owner consumer -> explicit CLI mode -> platform gates.

Local evidence:
- 23 initial missing-feature assertions failed before implementation.
- A later long-number regression showed that an apparently complete numeric
  prefix could accumulate the entire source before its cap was checked. The
  failing read-count test now passes after moving that gate before refill.
- All **24 new parser tests**, **25 original reader tests**, and **five v2
  contracts** pass. This includes the committed real CPU producer fixture,
  one-byte/irregular input, UTF-8/escape/exponent boundaries, 2048 distinct
  operator identities, a >1 MiB source, exact hashes, all caps and late refusal.
- 500 deterministic extra mixed-chunk/UTF-8/numeric cases matched eager reports.
- **13 file-owner tests** pass against AST-extracted exact reader definitions:
  incomplete/invalid consumers, source replacement/growth, no unbounded reads,
  descriptor closure, read failures, FIFO/symlink and pre-read bounds.
- The locally available #383 snapshot's **28 probe tests** also pass with the
  refactored reader; this is not new publication or deployment of that PR.

Local GitHub DNS prevents a clone. The CLI's broader module imports and the full
receipt suites require the complete repository: three new real subprocess/CLI
tests, existing file/receipt tests and all parser contracts run in the new Ubuntu
and Windows workflow. The unchanged full lifetime suite and validator remain
integration gates. No isolated/AST test is represented as a full local import,
whole-checkout test run, or workstation GPU proof. Final hosted evidence is
recorded with exact heads in the PR discussion.

## Synthetic parser comparison

The fixture has 12,000 events and 2048 padding characters in each event's argument
object: **25,938,953 input bytes**. It is intentionally argument-heavy, not a real
diffusion trace or an estimate of a typical trace. Both paths read the same saved
file; input creation is outside the measured child. Three fresh processes per
implementation alternate order. Every complete output report hashes identically.

The baseline is the exact pre-change eager algorithm with **benchmark-only**
raised input/event/operator caps matching the new mode. Those raised caps were
never supported by the old CLI. This isolates eager object retention versus
incremental processing; it is not a claim that default small mode regressed.

| Measurement | Eager algorithm, experimental raised bounds | Incremental mode |
| --- | ---: | ---: |
| Median process peak RSS | 171.54 MiB | 92.55 MiB |
| Median parse + aggregate time | 1362.15 ms | 1317.83 ms |
| Time range | 1318.90-1383.78 ms | 1303.38-1374.93 ms |

Observed median RSS reduction: **79.00 MiB**. Timing ranges overlap: no stable speed
improvement is established. Python 3.13.5, Linux x86-64. Process RSS includes imports
and is not Windows commit, GPU memory or the producer's live allocations. Three
samples do not qualify tails. [Every sample and source identity](evidence/trace-stream-12000.json).

```bash
mkdir -p .runtime
git show b29205cfc95ca4e64d72ae38d53df30c83968997:app/inference_trace.py > .runtime/inference_trace_baseline.py
python tests/benchmark_trace_stream.py --baseline .runtime/inference_trace_baseline.py --events 12000 --argument-bytes 2048 --repeats 3
python -m unittest discover -s tests -p 'test_inference_trace*.py' -v
python -m unittest discover -s tests -p 'test_resource_receipts*.py' -v
```

## Source boundary and next work

The supplied *Low-Level Engineering Optimisation Audit and Roadmap* recommends
sequential processing and lifetime allocation on pp. 8-9, interpretable profiling
on pp. 13-18 and a minimum-copy ledger on p. 22. Those source principles motivate
this repository-specific parser/file-boundary design. The report does not supply
this inference format, these numeric limits or these measurements.

Python's [JSONDecoder.raw_decode documentation](https://docs.python.org/3.12/library/json.html#json.JSONDecoder.raw_decode)
explains why a decoded value can finish before the end of its buffer. That API is
not a streaming document validator; the framing, delimiter, UTF-8, EOF and limit
gates here supply the remaining contract.

This makes larger **saved** captures inspectable. It does not cap a live producer,
qualify Windows/HIP activity, attach a trace to a job/process epoch, measure
profiler-on/off interference, or choose a kernel/transfer/compile intervention.
Those remain #364/#302. Future coordinator-owned capture must preserve exact
identities, bounded producer lifetime/export policy, all failed/uncertain outcomes
and finite approved allowances. The reader's success cannot grant that authority.

Rollback restores the previous small reader and removes the explicit stream CLI
mode; no original trace, historical report, job or Workspace data is rewritten.
HUMAN_TODO decisions and runtime defaults are unchanged.
