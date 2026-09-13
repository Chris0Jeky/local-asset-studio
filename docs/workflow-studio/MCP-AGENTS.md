# Workflow agents over MCP

Implementation slice for #123, building on #130's shared documents and #126's
registered-recipe tickets. This adapter runs as a small **stdio client of the
ordinary Studio server**. It does not create another Studio, database, GPU worker,
HTTP listener, browser session or dependency installer. Arbitrary edited graphs
remain authoring/check/export-only (#122).

## Start with authoring

From the repository root, create an isolated **tools** environment. Do not use
ComfyUI's portable Python or modify its packages:

```powershell
py -3.12 -m venv "$HOME\.local-asset-studio-mcp"
& "$HOME\.local-asset-studio-mcp\Scripts\python.exe" -m pip install -r integrations/workflow-mcp/requirements.txt
```

On Linux/macOS create the environment at `~/.local-asset-studio-mcp` and use its
`bin/python` interpreter. The tools environment stays outside the checkout and is
not a new runtime requirement for Studio. The optional dependency is deliberately pinned
to `mcp==1.28.1`, not whichever incompatible major happens to be newest. Transitive
dependencies are resolved by pip; this is not a full reproducible environment lock.

Start the ordinary configured Studio through its existing launcher. An agent host
can launch the adapter using an absolute interpreter and script path:

```json
{
  "mcpServers": {
    "asset-studio": {
      "command": "C:/path/to/tools-python/python.exe",
      "args": [
        "C:/path/to/local-asset-studio/scripts/workflow-mcp.py",
        "--url", "http://127.0.0.1:8191",
        "--mode", "author"
      ]
    }
  }
}
```

Replace only those two filesystem paths with actual local paths. The script finds
its own repository, so the host need not support a `cwd` option. This is a generic
stdio host configuration, not an automatic edit of any installed agent's settings.
A host with a different configuration format needs the same command/argument vector.

For a terminal or a host that already uses the repo as its working directory:

```bash
python -m studio_workflow.mcp_server --mode author
python scripts/workflow-mcp.py --describe
```

`--describe` is the smoke command: it prints local schemas with **no Studio request
and no MCP dependency import**. Normal stdio mode reserves stdout for the protocol;
diagnostics go to stderr. It waits for the host's MCP handshake, not keyboard input.

## Permission modes are process configuration

| Mode | Tools available | Deliberately absent |
| --- | --- | --- |
| `read` (default) | Capabilities, recipe catalog, paged installed nodes, saved list/read/history, edit preview, graph check, job observation | Document commits, reference staging, generation |
| `author` | All read tools plus document create/apply/restore/fork | Recipe preparation and execution |
| `execute` | All author tools plus registered-recipe prepare/run | Raw graph execution, arbitrary HTTP, shell/eval, model installs, environment switching, global interrupt |

Both tool listing and dispatch enforce the mode. MCP annotations are descriptive
hints, **not the authorization mechanism**. Modes constrain this adapter, not
other local clients that can access Studio's loopback HTTP API. Choosing execute
mode delegates those operations to the agent host; a hash proves ticket identity,
not that a separate human authenticated or approved the request. Keep host-side
approval enabled where a human must authorize every generation.

Read-only here means no authored revision or model work. The pre-existing
shared-document service may initialize its tables on first access; node inspection
may refresh the existing Comfy schema cache. Recipe preparation can stage existing
local reference files. None of these is a generation request.

## One document, one command contract

Use `workflow_list`, then `workflow_get`. Keep the returned document ID and revision.
`workflow_preview` and `workflow_apply` take the same command JSON as the HTTP/CLI
service; the bridge does not implement a competing reducer.

Example tool arguments, with actual IDs/revisions substituted from the read:

```json
{
  "document_id": "WORKFLOW_ID",
  "expected_revision": 4,
  "request_id": "lighting-change-001",
  "commands_json": "[{\"op\":\"rename\",\"name\":\"Warm lighting study\"}]"
}
```

For an input edit the command shape is
`{"op":"set_input","id":"1","input":"seed","value":9223372036854775807}`.
Use the node/input that actually exists. Static compilation separately checks the
installed schema; storing a draft is not a claim that its graph is runnable.

Read → preview → inspect the diff → apply at the **same expected revision**. If a
human edits meanwhile, HTTP 409 becomes an MCP tool error retaining the code and
request context. Re-read and propose a deliberate new edit; do not automatically
raise the expected revision and overwrite the person's work.

## Exact JSON, including 64-bit seeds

Document, command and ticket inputs are **JSON strings**, not nested MCP numbers.
Results expose a fixed structured envelope:

```json
{
  "ok": true,
  "operation": "workflow_get",
  "data_json": "{...the exact service object...}",
  "data_sha256": "64 lowercase hex characters",
  "context": {"document_id": "..."}
}
```

`data_json` is canonical UTF-8 JSON from the Python service client. The hash covers
those canonical bytes, not the envelope and not a native JSON object parsed by a
JavaScript host. Python `json.loads` preserves integers. A JavaScript agent must
retain the string or use an exact-integer parser; ordinary `JSON.parse` can round
large seeds. The same envelope appears in MCP `structuredContent` and text content
for hosts that only render text. No generated image/model bytes are embedded.

Strict bounded decoding rejects duplicate keys, reserved prototype keys, nonfinite
numbers and excessive nesting. Requests are capped at 1 MiB after decoding and
binding; replies at 2 MiB of underlying canonical data; there are at most four
simultaneous calls. The Studio transport's own cap is 16 MiB. Envelopes duplicate
text for MCP compatibility and therefore add overhead beyond the data cap. A large
reply fails visibly instead of silently truncating a workflow or substituting data.
Use `studio_nodes` with `query`, `offset`, `limit` (1–100) and the returned schema
hash on later pages. Pagination fetches the cached catalog through Studio; it is
not a new Comfy polling service. Saved history retains the service's bounded summary
and its omission metadata; it is not an unbounded event stream.

## Registered recipe execution

Only execute mode exposes these tools:

1. `recipe_prepare` takes `recipe_json`, containing the existing registered
   `preset_id`, supported controls/references and `batch_count: 1`.
2. Retain its `data_json` (the complete ticket) and `data_sha256`. Inspect the
   actual recipe and intended inputs before requesting execution.
3. `recipe_run` takes that unchanged `ticket_json` and
   `approved_ticket_sha256` equal to the preparation result hash.
4. Observe the returned job with `job_status`. It performs one read; it never
   resumes, duplicates, cancels or changes the queue.

The existing ticket service owns the durable request receipt and at-most-one
retained dispatch attempt. The adapter neither strengthens this into distributed
exactly-once execution nor freezes unknown external model/package files. Existing
resource/runtime gates remain authoritative, with the limitations of that service.
An invocation can contain several output nodes; one invocation is not a promise of
one image. Authoring an arbitrary document still cannot queue it through this tool.

## Errors, cancellation and recovery

Every dispatched tool error sets MCP `isError`, `ok: false` and an error code. Codes
include `tool_not_allowed`, `invalid_arguments`, `invalid_workflow`,
`revision_conflict`, `gateway_busy`, `request_failed`, `outcome_unknown` and
`reconciliation_required`. Context retains request IDs/revision/ticket hash where
available; source error messages are bounded, not instructions to execute.

There are **no automatic write retries**. A document request with the same retained
ID and unchanged payload recovers the original receipt, even if a later human edit
advanced the head. A response may report both original `revision` and current
`head_revision`; do not treat them as interchangeable. Reusing a ticket means
observing its retained attempt, not creating a replacement ticket.

A timeout, truncated response, lost connection, post-write oversized response or
host shutdown can leave an unknown outcome. Keep the original inputs and reconcile
through the same service. Cancellation of an MCP call is **not cancellation of the
shared Studio operation**. The adapter does not abandon its in-flight HTTP thread
on ordinary cancellation; forced process termination can still lose the response.
It never calls Comfy's global interrupt or clears another job. No live progress,
resumable events, artifact download, or owned-job cancellation is claimed here.

## Verification and boundaries

- `test_workflow_agent_bridge.py`: dependency-free contracts with real loopback
  HTTP for origin, exact values and conflict propagation, plus fault/permission
  fixtures. 22 tests passed in the authoring environment.
- `test_workflow_mcp.py`: optional official SDK handshake/list/call/output-schema
  tests and a real subprocess stdio → HTTP → shared SQLite scenario. It proves an
  agent edit, an intervening direct human-service edit, exact-request recovery and
  stale-write refusal. Its "lost response" leg discards an already returned reply;
  it does not simulate power failure.
- The dedicated `Workflow MCP contracts` CI lane installs the pinned SDK on
  Ubuntu and Windows and requires it before running protocol tests. The ordinary
  Studio suite can skip only the four optional protocol tests when MCP is absent.

The authoring environment lacks the optional SDK/full private checkout, so the
protocol and full-suite claims require the published CI run, linked from the PR.
No installed agent host, user workstation, Comfy GPU, native widget, generated
artwork or licensing acceptance was exercised. HUMAN_TODO remains unchanged.

## Primary sources and design decisions

Reviewed 13 September 2026:
- MCP tools and structured output: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- Official Python v1 low-level server: https://py.sdk.modelcontextprotocol.io/v1/low-level-server/
- Official client/stdio lifecycle: https://py.sdk.modelcontextprotocol.io/v1/client/
- Official in-memory protocol testing: https://py.sdk.modelcontextprotocol.io/v1/testing/
- Exact optional distribution: https://pypi.org/pypi/mcp/1.28.1/json

We use the official SDK for protocol framing/lifecycle, a small dependency-free
bridge for application semantics, and Studio for every operation. Protocol SDK
upgrades should run the same tests in isolation, not upgrade ComfyUI's environment.
Follow-ups remain #123 (host integration, artifact/event/operation parity), #119
(schema adapters), #120 (reusable modules), #121 (native graphs), #122 (authored
execution). This slice intentionally closes none of those wider issues.
