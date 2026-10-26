# Library page completion: bounded read evidence

Refs #1627 and #177. This record covers the backend candidate based on the exact
tree of main `7a89410d34c2580c3b9d47ffd806193e006d4069`. Frontend/native integration
and hosted merge qualification are separate evidence gates.

## Behavior

- `include_collections=true` reads the bounded collection bundle, assets and
  catalogue stamp in the same SQLite transaction. A second WAL writer changing
  collection membership visibility between projections cannot mix snapshots.
- Explicit `reanchor=true` refreshes a retained keyset boundary after a confirmed
  edit without resetting to the newest page. Ordinary continuation remains strict;
  scope, epoch, future revision, query and page-size conflicts still refuse.
- Exact `job_id` filtering precedes pagination and has a supporting index. HTTP,
  CLI and read-only agent/MCP contracts use the same filter owner. Omitting it
  preserves the legacy summary response and cursor query identity.
- An unavailable private detail record is named in `unavailable_assets`; complete
  usable records remain available. Explicit selected-ID details still refuse an
  unavailable record. No partial editor baseline or missing state is invented.
- Writer-accepted 30-by-60-character Unicode tags survive UTF-8, UTF-16LE and
  UTF-16BE reads. Complete details pages shorten their observed prefix to fit the
  existing 2 MiB serialized response cap, with continuation after the last observed
  ID, including unavailable rows.
- A registered 1,024-character title, including worst-case JSON escaping, fits
  the bounded 12,288-character cursor. The HTTP query cap is 20,480 characters to admit the maximum
  percent-encoded search, job filter and remaining flags.

## Causal and regression execution

Local Python 3.12.14, temporary SQLite databases, synthetic metadata only:

| Gate | Result |
| --- | --- |
| Initial 12 new completion tests against unchanged production | 21 errors: unsupported new options plus reproduced Unicode metadata and whole-page refusal cases |
| Same 12 after implementation | pass, 0.288 s |
| Add maximum Unicode title and UTF-16 tests | 14 tests, one error reproducing the old cursor bound |
| Corrected cursor bound and exact original-title expectation | 14 pass, 0.326 s |
| Existing and extended asset read/client/HTTP/encoding/deadline/scalar contracts | 79 pass, 11.577 s |
| Collection list and explicit selected-ID contracts | 6 pass, 0.132 s |
| Read-only workflow/agent bridge contracts | 18 pass, 1.230 s |

Two intermediate fixture mistakes are retained in local logs: the Unicode cursor
assertion initially expected a lowercased title although the production sort
retains the original key with a SQL collation; two new HTTP fixtures initially
assigned one job ID to duplicate output indices and hit the existing unique
constraint. Correcting those fixture inputs/expectations did not weaken any
production refusal or change its ordering. Loopback HTTP tests used the scoped
test permission required by this environment.

Independent review reproduced two additional boundaries after the initial
candidate: malformed UTF-8 in a private TEXT field was decoded by SQLite before
the per-record handler, and a real registered title containing 1,024 NULs needed
six-byte JSON escapes rather than four-byte Unicode storage. Both new regressions
failed against that candidate. Private text now crosses the SQL boundary as
bounded BLOBs and is decoded per row using the database encoding; malformed bytes
name the unavailable ID without hiding valid peers or altering stored bytes.
The cursor/query caps above include the registered escaped-title case. The
independent mixed stress probe also walked 42 large records and three unavailable
sources against 100 large collections in all three sort orders, without missing
or duplicated IDs; its largest response was 2,039,441 bytes.

The corrected review candidate passed **16 completion tests in 0.414 s**, **79
read/HTTP/client regression tests in 12.355 s**, and **6 collection tests in
0.259 s**. Validation passed 93 graphs/bindings, 187 pinned assets and 4,460
tracked paths. An intermediate HTTP test mistakenly assumed that a mixed
Unicode/control title would exceed the old cap; its actual cursor was 8,171
characters. The fixture now uses a real worst-case escaped title and finds its
200-character Unicode search in notes. It verifies a cursor above 8,192
characters with all supported filters, without weakening the input bounds.
Review-stage logs are `review-before.log`, `review-after.log`,
`review-regressions.log`, `review-regressions-final.log`,
`review-collections.log`, and `review-validate.log` in the same directory.

Logs: `.runtime/library-read-completion/{before,after,unicode-before,unicode-after,
asset-read-regressions,asset-read-regressions-after,collections,workflow-reads}.log`.
The tests make no model calls or media reads. Response bounds do not establish
constant query time, browser memory budgets or owner art acceptance. The broader
resource work in #177 and owner decisions in `HUMAN_TODO.md` remain open.
