# Review reference descriptions in Studio

This continuation of #333/#336 adds a local validation and transfer-preview boundary.
The browser UI is a separate stacked slice. Actual vision inference remains the
operator/agent assistant; scheduled **Analyze** execution still belongs to #35/#178.

## API

`POST /api/prompt/reference-review/inspect` accepts `{"analysis": <report-or-helper-envelope>}`.
It checks the report and returns the existing role-compatible review template.
Helper envelope timing/model claims confer no authority and are not copied into the review.

`POST /api/prompt/reference-review/preview` accepts `analysis`, `review`, `images`,
`intent` (the complete current CreativeIntent), and explicit boolean `adopt_brief`.
`images` contains one `{reference_id, media_base64}` per reference, in report order.
The server verifies the original SHA-256 and decodes each PNG/JPEG/WebP within the
8 MiB, 16 MiPixel, one-frame limits. Filenames are never interpreted as server paths.
There is no temporary-file publication, Workspace insertion or Comfy staging.

The response includes the proposed intent, before/after changes, base and result
hashes, and the full source/selection receipt. It replaces the ordered reference
set, updates only selected facets and merges explicitly selected tags. Other
facets, avoid terms, constraints, exact words, parameters, identity and locks remain.
The original instruction changes only when `adopt_brief` is true. An empty editor
can explicitly adopt the analyzed instruction or, for an empty request, its reviewed
summary. Changed locked fields refuse the whole projection, without partial application.

Only this preview endpoint accepts up to 48 MiB of JSON for at most four originals.
Every image has its own predecode byte and decoded-pixel limits. Other Prompt Lab
routes retain their 1 MiB JSON limit and all routes retain strict duplicate-key and
nonfinite-value rejection. The endpoint is guarded by the existing loopback Host /
same-origin checks. It performs no model calls and cannot submit a generation.

## Source contracts

The original file-based `reference_analysis.draft(report, review, root)` remains
supported. The keyword-only `source_bytes` alternative is for already captured
in-memory originals and is mutually exclusive with `root`; it still verifies all
IDs, byte limits and hashes. The web adapter additionally validates actual pixels.
A fabricated analysis can be internally consistent: hashes do not authenticate
its author, prove a VLM ran, or establish the correctness of its description.

Uncertain traits require an explicit edited description. Questions and assumptions
remain in the returned receipt. Style/pose descriptions do not certify geometry,
identity preservation, model-slot compatibility or a useful repair.

## State boundary

A preview binds a caller-supplied current intent. Its hash is not a shared SQLite
revision and the endpoint persists nothing. A consumer must compare its still-
current draft and reference selection before applying a response. The browser
slice supplies that compare-before-apply and a guarded one-step Undo. Persistent
cross-client documents remain #38; native reviewed setup remains #232/#335.

The originals are sent only to the local Studio validator, not a generator or
hosted provider. To generate later, use the actual registered reference route and
its separate upload/preflight/approval. A text-only handoff must not discard these
reference records to bypass a compiler warning.

## Proving checks

- `python -m unittest discover -s tests -p 'test_reference_review.py'`
- `python -m unittest discover -s tests -p 'test_reference_*.py'`
- `python -m unittest discover -s tests -p 'test_studio_prompt*.py'`
- `python tests/check_full_suite_lifetime.py`
- `python scripts/validate-repo.py`

These checks prove software contracts with synthetic sources, not local VLM or
artwork quality. HUMAN_TODO choices and existing generation allowances are unchanged.
