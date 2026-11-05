# Bounded Blender MCP scene descriptions

Date: 5 November 2026. Issue: [#1984](https://github.com/Chris0Jeky/local-asset-studio/issues/1984).
Base: local `5f3f43ee8bdad8547e954a4b369fff4b4e1cdeed`, tree
`8ec1a12bdf31fc03106eaa53a1fcb34f75db0916`, reconciled with GitHub main
`d7392c025027b2df8e4a045f44e54f05529f111f` before this slice.

## Failure and fix boundary

The issue records a large-scene repair decline when `blender_describe_scene` exceeded the agent's reply limit.
The old facade returned the complete native manifest without checking its serialized size. It also converted
explicit falsey argument values such as `null`, `false`, `0`, empty text and empty arrays to `{}`, allowing them to
reach the worker.

The first regression run executed **18 test methods**: **25 failing assertions/subcases, zero errors, one existing
native skip**. The default reply for a deterministic 250-object fixture with nested detail occupied **1,145,047
bytes** in the serialized MCP tool result. New options were not advertised or accepted; the invalid falsey
argument cases reached the worker.

The fix is confined to the MCP facade. `mode`, exact-name `objects`, `cursor` and `max_bytes` govern presentation;
the worker still receives `describe_scene` with no arguments. No native worker, `_object`, manifest schema,
checksum algorithm or edit operation changed. Small auto replies preserve the original full manifest. All other
successful descriptions use one versioned summary shape with complete object rows and explicit omissions.

## Result contract and measured size

The advertised byte budget is the server's serialized **MCP tool result**, including the content envelope and
escaped text: `len(json.dumps(reply["result"]).encode("utf-8"))`. The caller-owned JSON-RPC envelope/ID and newline
are outside that budget. Tests preserve long string and large integer IDs, parse the complete wire reply, and
deliberately do not claim those caller-owned bytes are capped.

At 02:32:51 UTC, the same synthetic 250-object description produced **32,614 result bytes** under the default
32,768-byte cap. The first page contained **117 whole objects**, with **133 remaining** and a 267-character cursor.
The source manifest stayed unchanged and its full semantic checksum still verified.

Recorded small fixtures kept their full content and original schema:

| Fixture | Serialized result bytes |
| --- | ---: |
| Articulated chest | 16,613 |
| Lab asset, Blender 4.5.13 | 14,328 |
| Lab asset, Blender 5.4.0 alpha | 14,362 |

These are retained fixture compatibility checks, not new native Blender executions.

## Regression coverage

- Effective default compatibility, including explicit `auto` and budget-only requests, plus the exact size
  threshold between a full manifest and summary.
- Large-scene fallback; whole-object counts; named section/field omissions; immutable source manifest and
  unchanged checksum.
- Exact filtering with case differences, composed/decomposed Unicode, quotes, backslashes, newlines and a literal
  `*`; parent metadata and existing world matrices are preserved without introducing local transform fields.
- Deterministic pages, exact selected-object coverage without duplicates, filter-excluded versus remaining counts,
  progress, empty-scene termination, and summary-only continuation after increasing the budget.
- Pre-worker type/range checks and malformed/changed-selection cursor refusal; stale full-scene checksums and
  out-of-range continuation offsets; bounded errors when a complete row cannot fit.
- Actual stdio serialization with nested escaping and preserved RPC IDs; oversized Unicode worker errors are
  replaced by a short bounded tool error.

Independent read-only review found no production blockers and checked another **140 pages** across 30 scene-size
and budget combinations, from empty to 250 objects and 4,096 to 65,536 bytes. Every page fit its result cap, all
selected objects appeared exactly once, cursors terminated, and source manifests stayed unchanged.

## Executed checks

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests -p test_blender_mcp.py -v` | 19 tests in 0.087 s: 18 passed, 1 native skip |
| `python -m unittest discover -s tests -p test_blender_worker.py -v` | 12 tests in 2.131 s: 11 passed, 1 native skip |
| `python -m unittest discover -s tests -p test_blender_lab.py -v` | 27 tests in 0.548 s: 22 passed, 5 native skips |
| `python -m unittest discover -s tests -p test_blender_repair_bench.py -v` | 24 tests in 3.047 s: 22 passed, 2 native skips |

Total: **82 tests, 73 passed, 9 native skips**. `python scripts/validate-repo.py` passed: **98 preset graphs/bindings,
194 pinned assets, 4,888 tracked paths**, 743 local-media manifest entries / 102 references, and 167 LoRA names.
`git diff --cached --check` passed. The staged payload contains only the facade, its tests, this note and the Blender
lab guide.

## Limits

No Blender runtime was configured locally. No live repair benchmark, model run, generation, new native export or
visual-quality claim accompanies this facade change. The worker still constructs and sends the full manifest to
the facade on each request; this bounds agent-facing output, not native computation or worker transport cost.
World-space transforms retain the existing manifest precision and are not interchangeable with local edit values.
The final published head still requires hosted CI.

Art direction/replacement of the paused asset wave (#1923), parallax usability (#1219), and the island default
switch remain owner decisions. No art or licensing acceptance is inferred.
