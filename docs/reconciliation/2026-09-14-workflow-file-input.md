# Bound workflow file reads before decoding

Issue #265. Inspected main `2f91421ecbe0e014cceef1074f4d79e4c57051df`;
tracked-source tree `25da90c8445bc5e94cc73fd814964563c256f102` was reproduced
before editing. This is a local CLI capture correction under #123, not new
execution authority or completion of the agent workstream.

## What changed

The authoring decoder already refuses documents over 1 MiB. Previously the CLI
allocated the entire input with `Path.read_bytes()` before that check. Recording
forwarders over real temporary files observed `read(-1)` in all eight file-input
routes. Oversized content was already rejected before HTTP; the missing bound
was on allocation, not server admission.

`studio_workflow.file_input.read_document` opens the file once, reads at most
`core.MAX_BYTES + 1`, closes it, and calls the existing strict decoder. The extra
byte distinguishes exact-limit input from oversized input. No separate stat
check is relied on, so growth just before opening cannot bypass the byte cap.
The pure core remains free of file I/O and owns the limit and JSON rules.

The top-level `import`, `compile`, `prepare`, `run`, `prepare-document`, and
`documents create/apply/preview` commands share this reader. The SDK's object
inputs and HTTP response framing are unchanged. Duplicate/reserved keys,
nonfinite values, excessive nesting, UTF-8 handling and wide integers continue
through the existing decoder. File contents, output protections, request IDs,
run-ticket identity and current exit/error contracts are unchanged.

## Reproduction and verification

Seven new unittest methods cover all eight adapters, oversized and growing
files, exact-limit real loopback preparation, strict JSON failures, missing or
directory inputs, closed handles and execution from another working directory.
The adapter-size test substitutes only the request boundary; the exact-limit
case uses the real loopback workflow command service with its inert worker.

Before implementation the corrected fixture produced 17 expected bounded-read
assertion/subtest failures. An initial unrelated fixture failure used `seed`
against a fake recipe supporting only `value`; the fixture was corrected before
recording that red run. The wide integer case explicitly widens its synthetic
node schema, not application validation. All seven focused methods pass.

Run from the repository root:

```sh
python -m unittest discover -s tests -p test_workflow_file_input.py -v
python -m unittest discover -s tests -p 'test_workflow*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Final full-suite and hosted Linux/Windows outcomes are recorded on the PR with
its source identity; they are not inferred from this test description. Original
baseline warnings and optional/live skips remain visible in the retained logs.

## Limits and rollback

This bounds the captured encoded bytes, not total decoded memory, filesystem
latency, special-file behavior or atomicity against concurrent in-place writes.
Explicitly named symlink inputs retain the existing path semantics. Invalid
`run` input retains its established exit protocol; this patch does not introduce
a new local-input error schema. Revert these caller changes and helper together;
there is no configuration, schema or stored-state migration.

No generation, model install, runtime restart, owner data or HUMAN_TODO change.
Creative choices already recorded remain recorded; no new artistic or licensing
acceptance is inferred.

Primary reference checked 14 September 2026:
[Python buffered reads](https://docs.python.org/3/library/io.html#io.BufferedIOBase.read).
