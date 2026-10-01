# Asset family and output-specific recall

Implementation slice of #1206. This service extends the existing Workspace and composed Studio HTTP handler. It does not create an asset store, journal, model runner, or source-staging path.

## Delivered service

`GET /api/assets/family/{asset_id}?workspace_id={workspace_id}` returns ancestors oldest first, exact parent edges, named missing/trashed steps, recipe names, and recorded seed/strength text. Multiple parents remain multiple edges, never an invented single chain. Cycles and damaged lineage are explicit gaps.

Add `&children=true` to request direct children. The ordinary ancestry read does not scan for children. Search inspects at most the newest 5,000 asset rows and returns at most 20 children. `children_truncated` discloses result limits, scan limits, or unreadable lineage. It must not be presented as a complete catalogue-wide child index.

`GET /api/assets/recall/{asset_id}?workspace_id={workspace_id}` returns the existing exported recipe baseline separately from the chosen output's effective controls. It reads the output's recorded seed and its uniquely matching submission's positive/negative text, including companion bindings. This prevents recalling a batch's original seed or unresolved wildcard wording as though it produced the selected output. Seeds travel as decimal text, including uint64 values.

Recall rejects missing/trashed assets, unresolved jobs, specialized tile/parallax/native jobs, ambiguous submissions and divergent companion text. It does not stage files, modify a draft, approve a recipe, or submit generation. The consumer must check the baseline through the existing recipe-check service, retain its current draft identity across the asynchronous read/check, and obtain explicit confirmation before applying a one-output draft. Generate remains separate.

## Headless use

```console
python -m studio_workflow.asset_family_client inspect ASSET_ID --workspace WORKSPACE_ID
python -m studio_workflow.asset_family_client inspect ASSET_ID --workspace WORKSPACE_ID --children
python -m studio_workflow.asset_family_client recall ASSET_ID --workspace WORKSPACE_ID
```

These commands use the existing bounded, literal-loopback Client. `--base` selects an explicit loopback Studio origin. No automatic retry, file write, upload or model call occurs. Successful JSON is written once to stdout; a request/validation failure produces one error object and exit status 2. The SDK entrypoint is `FamilyClient.inspect` / `FamilyClient.recall` over the same Client.

## Bounds and evidence

Ancestry is bounded to 12 levels, 64 nodes, 128 edges and 16 parents per row. Retained lineage/source JSON is bounded to 16 KiB before decoding. Recall imposes structural bounds and a 256 KiB recipe limit. Reads check Workspace identity in the same SQLite transaction as asset observations and return `Cache-Control: no-store` through the existing production handler.

`observation_only: true`, `generation_submitted: false` and `media_bytes_verified: false` are deliberate boundaries. Attribution is not proof of unchanged media, artistic acceptance, source rights or current runtime compatibility. Existing server validation and dispatch remain authoritative.

Executed locally: 24 new family/service/CLI/real-HTTP tests and 60 existing asset-read tests passed. The tests include four-step ordering, missing and trashed ancestors, cycles, multiple parents, depth and child bounds, malformed data, exact output words/seeds, specialized-route refusal, foreign Workspace, malformed HTTP queries, GET-only SDK use and zero mutation. Exact-head Linux/Windows qualification is provided by the dedicated workflow and remains a merge gate.

## Remaining #1206 acceptance

The main Asset dialog and result-tile family strip, explicit split-recall buttons, draft-preserving workbench application, source-picker handoff, keyboard/narrow/zoom behavior and registered native-browser journey remain UI integration work. This service PR does not claim those controls are shipped or close #1206. A separate prepared frontend implementation must pass native browser and use-case qualification before it is enabled. Local Chromium cannot navigate loopback in this execution environment; that is not browser evidence.
