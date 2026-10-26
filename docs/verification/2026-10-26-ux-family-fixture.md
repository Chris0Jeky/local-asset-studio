# UX family observation fixture — 26 October 2026

## Finding and correction

The UX journey fixture extends the real prompt and asset HTTP handlers, but its
base `studio` is `None`. Family GET requests consequently reached the real
`asset_family.observe` without an asset owner and raised
`AttributeError: 'NoneType' object has no attribute 'assets'` in the request
thread. The browser caught the unavailable family observation, so the affected
journeys could pass their primary assertions without a JavaScript `pageerror`.

The Library run at head `83f37cb28871ca786aad71600e562a3494e6dad3`,
[run 40364666406 / job 121718997770](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364666406/job/121718997770),
contains seven such exceptions: one each in review-and-keep-winner,
reuse-keeper-as-reference and vary-a-keeper, and two each in
make-a-texture-tile and split-a-scene-into-parallax-layers. Its passing primary
journey assertions remain useful, but that run is not evidence of clean HTTP
handling or successful family observations.

This follow-up changes only the UX fixture adapter. Family GET requests retain
the loopback Host guard and use the production `family_query` parser, the shared
fixture's synchronized temporary `AssetWorkspace`, and the production
`asset_family.observe` projection. A mapping of the fixture's current synthetic
jobs supplies the existing denoise/strength enrichment. Query interpretation,
lineage traversal, Workspace scope and bounded child discovery stay with their
production owners. The fixture's media, mutations and browser assertions are
unchanged; unrelated prompt routes still use their existing adapters.

## Causal checks

The isolated base is `48544a698f08030157d844eafab2aa34fffa47d8`, the local
Library integration corresponding to the old published Library tree. Three new
direct-handler tests initially fail with the same `NoneType.assets` exception.
They require a real lineage response with synthetic job enrichment, current
child results after the fixture data changes, and preserved Host, Workspace and
strict-query refusals. They also verify that the read does not mutate synthetic
assets/jobs or submit a fixture POST.

The existing `reuse-keeper-as-reference` native Chromium journey was run before
the adapter change. It passed its existing assertions while logging one matching
HTTP request-thread exception, zero page errors and three measured dead ends.
The unchanged journey after the correction passes with zero request-thread
exceptions, zero page errors and zero measured dead ends. Both runs observe four
fixture POSTs, on `/api/assets/reference` and `/api/estimate`, and zero generation
submissions. This is one targeted synthetic journey, not a rerun of the full UX
matrix or an installed-model exercise.

| Gate | Result |
| --- | --- |
| New direct-handler tests before correction | 3 failures, all the original missing asset-owner exception |
| Complete offline use-case matrix after correction | 71/71 pass, no skips |
| Targeted native journey before correction | Primary assertions pass; 1 HTTP exception, 0 page errors |
| Same native journey after correction | Primary assertions pass; 0 HTTP exceptions, 0 page errors |

Commands:

```sh
python -m unittest discover -s tests -p test_use_case_matrix.py -k FamilyFixtureReads -v
python -m unittest discover -s tests -p test_use_case_matrix.py -v
python tests/studio_use_cases.py --case reuse-keeper-as-reference --out .runtime/ux-family-review/native-green.json --screenshots .runtime/ux-family-review/native-green-shots
```

The local environment uses `/tmp/las-continue-venv/bin/python` and
`PLAYWRIGHT_BROWSERS_PATH=/tmp/las-continue-playwright`. Original stdout/stderr is
retained in `.runtime/ux-family-review/contracts-red.log`,
`contracts-green.log`, `native-red.log` and `native-green.log`, alongside both
JSON journey receipts and screenshot directories. `candidate.json` binds the
tested source and evidence hashes. Fresh hosted qualification belongs to the
follow-up's published head; the earlier Library workflow is retained separately.

## Tested source SHA-256

| File | SHA-256 |
| --- | --- |
| `tests/studio_use_cases.py` | `a0f30044cb8609acb5cd78339e1ea3f004e28a259bed034c209d2ed31cecf030` |
| `tests/test_use_case_matrix.py` | `ffbfc6965e7000c66c9114b2ee2a7f34f23b2cf4e41252bba7bc4fe82a519ddb` |
| Unchanged `tests/studio_browser_smoke.py` | `626191f35f438cb22078572fd8321eeb77186147a6237b5bcab506f745e1af99` |
| Unchanged `studio_workflow/asset_family.py` | `b3a1d30a49d88d30045d93cdc76eb551024f6a602a50fb32e4a5fd91b9aacd0d` |
| Unchanged `studio_workflow/asset_read_http.py` | `6ae9d7234ec53e0a7e49257c32582aaa56f79b57f31ce47b4db22eecb3207ed6` |
