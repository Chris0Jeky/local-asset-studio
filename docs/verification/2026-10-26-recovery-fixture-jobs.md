# Recovery browser fixture job ownership — 26 October 2026

## Finding and boundary

The recovery response-ownership, conflict-envelope and Workspace browser fixtures
constructed a synthetic Studio with `assets` but no `jobs` mapping. Opening an
asset also requests its family through the real HTTP handler. The shared
`studio_workflow.asset_family._node` reads `studio.jobs` to enrich that observation,
so these incomplete test owners raised `AttributeError` in their server threads.
The family panel catches an unavailable observation; JavaScript `pageerror` does
not report a Python request-thread exception.

The existing exact-command, revision, scope, held-response and focus assertions
passed. They inspect the real metadata route, journal and SQLite owner directly;
the failed advisory family request does not supply their observations. Those
results remain protocol evidence, but the old runs were not exception-free HTTP
journeys or evidence that the family panel loaded normally.

This follow-up adds only `jobs={}` to those three synthetic Studio owners. The
fixtures have no generation-job service, so an empty map represents their actual
setup. Production family handling, requests, test assertions and counts are
unchanged. The refusal fixture already has this correction in the preceding
refusal integration. Shelf, lifecycle, library, grid, source-filter and metadata
fixtures likewise provide the map.

## Retained hosted observation

The corrected recovery PR head was
`2c144d936e1b62170468c08434c6e17950a40024`:

| Gate | Run / job | Observation |
| --- | --- | --- |
| Response ownership, Linux | [40364539033 / 121718554421](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539033/job/121718554421) | 13 assertions pass; two missing-`jobs` exceptions |
| Response ownership, Windows | [40364539033 / 121718555143](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539033/job/121718555143) | 13 assertions pass; two missing-`jobs` exceptions |
| Conflict envelope, Linux | [40364539117 / 121718556611](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539117/job/121718556611) | 10 assertions pass; one missing-`jobs` exception |
| Conflict envelope, Windows | [40364539117 / 121718555895](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539117/job/121718555895) | 10 assertions pass; one missing-`jobs` exception |
| Workspace within asset-detail browser (0) | [40364539027 / 121718555461](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539027/job/121718555461) | 25 scope assertions pass; six missing-`jobs` exceptions |

The first four job logs explicitly check out the PR head. Asset-detail's existing
workflow checks out the integration merge
`5b94bd420b67538714751daba44e11496d4c4e63`, combining that head with
`b4515ca73e274e07b5642616d3f5e26289880432`; it is recorded separately.

## Causal local check

The follow-up starts from the complete stack's local integration
`8d077d772ae24bf53a054e30d5b87bdee00436ec` (`codex/mcp-release`). Before editing,
the unchanged native session fixture again passed all 13 assertions while
raising the same two missing-`jobs` exceptions. Its receipt remains under
`.runtime/fixture-jobs-red-session/receipt.json`; the full log is
`/tmp/fixture-jobs-red-session.log`.

After the three owner corrections, the existing native gates report:

| Fixture | Assertions | Page errors | HTTP request-thread exceptions | Source SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `asset_recovery_session_browser.py` | 13/13 | 0 | 0 | `bf4e167e90ec729c48adc5445261917cedf3cf75a40c84a49a3259385554a83e` |
| `asset_conflict_envelope_browser.py` | 10/10 | 0 | 0 | `560c07c80583a0c1c47db2db8cc879721c885b61fc6b8cf39239886bb3e2de16` |
| `asset_workspace_browser.py` | 25/25 | 0 | 0 | `d0707b678a86d51c701b2d82d5997fa90e2672c06b836113d0c5fcd8ffe00c37` |

Each process exits zero and each receipt has `failure: null`. This change
preserves every existing assertion and count. Local runs use Playwright
1.56, Chromium 141 and temporary loopback HTTP/SQLite with synthetic image bytes;
they do not certify the hosted Playwright 1.57 run or an installed Studio/model.

Commands use the existing fixtures, for example:

```sh
python tests/asset_recovery_session_browser.py --out .runtime/fixture-jobs-green-asset_recovery_session
python tests/asset_conflict_envelope_browser.py --out .runtime/fixture-jobs-green-asset_conflict_envelope
python tests/asset_workspace_browser.py --out .runtime/fixture-jobs-green-asset_workspace
```

Full stdout/stderr is retained as `/tmp/fixture-jobs-green-<fixture>.log` alongside
the named receipts. Hosted qualification belongs to this follow-up's published
head; the already-running recovery, Library, refusal and MCP heads are unchanged.
