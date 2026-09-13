# Saved run recovery for agents

Continuation of [saved-run lineage](SAVED-RUN-LINEAGE.md), 13 September 2026.
This adds SDK, CLI and five MCP tools to the same service. It neither broadens
supported graph types nor adds an execution endpoint, scheduler or database.

## Start from a saved document

Start the ordinary Studio server with the normal local configuration. From the
repository root, list saved workflows and read the selected document:

```bash
python -m studio_workflow documents list
python -m studio_workflow documents get DOCUMENT_ID
```

Use its actual ID, current revision and matching registered image preset. The
following uppercase names are placeholders, not newly registered presets:

```bash
python -m studio_workflow runs prepare DOCUMENT_ID --expected-revision 1 --preset PRESET_ID --request-id illustration-preparation-001 --ticket-out run-ticket.json > run-record.json
```

This prepares and persists a source record; it does not run generation. Review
`run-record.json`: `record.request` identifies the source revision and preparation,
while `record.report` contains the exact controls, ticket, hashes and expected job.
The exported `run-ticket.json` uses the unchanged ordinary run-ticket format:

```bash
python -m studio_workflow run --ticket run-ticket.json --approve
python -m studio_workflow runs observe illustration-preparation-001
```

The second command only observes existing local job evidence. It does not poll
ComfyUI, resume observation, cancel work, resubmit a graph or approve anything.

## Recover rather than prepare another attempt

After a lost reply, browser closure, CLI restart or agent restart:

```bash
python -m studio_workflow runs get illustration-preparation-001 --ticket-out recovered-ticket.json
python -m studio_workflow runs observe illustration-preparation-001
```

The GET does not call schema discovery or create another ticket. It works when
ComfyUI is unavailable, provided Studio and the original Workspace are accessible.
Only a later explicit ordinary `run --approve` can attempt execution/reconciliation;
recovering the record alone never does so. Keep the original request ID even if a
GET initially returns 404 while a preparation might still be in flight. Do not
invent another request identity merely to resolve an ambiguous response.

There are three different identifiers: the caller-chosen **preparation ID**, the
UUID inside **ticket.request_id**, and the expected **job ID**. The command above
uses the preparation ID, not a prompt ID or ticket UUID.

```bash
python -m studio_workflow runs list DOCUMENT_ID --limit 25
python -m studio_workflow runs list DOCUMENT_ID --limit 25 --before NEXT_BEFORE
python -m studio_workflow runs by-job JOB_ID
```

Stop paging when `next_before` is null. Lists contain metadata, not embedded
execution tickets. Legacy runs prepared through other routes are not backfilled.

## SDK

```python
from studio_workflow.sdk import WorkflowClient

client = WorkflowClient("http://127.0.0.1:8191")
saved = client.saved_runs.prepare(
    "DOCUMENT_ID", expected_revision=1, preset_id="PRESET_ID",
    request_id="illustration-preparation-001",
)
# No automatic execution or retry follows preparation.
recovered = client.saved_runs.get("illustration-preparation-001")
observation = client.saved_runs.observe("illustration-preparation-001")
page = client.saved_runs.list("DOCUMENT_ID", limit=25)
source = client.saved_runs.by_job(saved["record"]["report"]["job_id"])
```

`SavedRuns` is a client-only namespace using the existing bounded loopback
transport. It validates request IDs, revisions and cursors before sending. Returned
record/ticket hashes and call identities are checked before exposing a ticket.
Large integer seeds remain JSON integers in Python and exported files. The original
`Client` exception contract is unchanged; only saved-run methods translate HTTP
failures to `ClientError` with `status`, `code`, and `result` preserved.

## MCP tools

Existing [stdio MCP setup](MCP-AGENTS.md) remains unchanged. No optional package is
added to ordinary Studio startup and no host configuration is edited by this PR.

| Tool | Mode | Arguments |
| --- | --- | --- |
| `saved_run_prepare` | execute | `request_id`, `document_id`, `expected_revision`, `preset_id` |
| `saved_run_get` | read or higher | `request_id` |
| `saved_run_list` | read or higher | `document_id`, optional `before`, `limit` |
| `saved_run_observe` | read or higher | `request_id` |
| `saved_run_source` | read or higher | `job_id` |

The default read mode cannot prepare. Discovery and dispatch enforce the same
permissions. Execute-mode preparation only creates the record: `recipe_run` is
still a separate tool with its existing exact-ticket hash binding. Permissions
are adapter scopes, not operating-system access control or authenticated human
approval. Read mode may reveal an execution ticket; it cannot call execution tools
through this adapter. Host-level approval decisions remain separate.

Like the original MCP tools, results use `data_json` with `data_sha256` so a
JavaScript host does not silently round int64 values embedded in a workflow.
Decode with exact integers. Read successes carry observation states rather than
claiming job success. In particular, `not_observed` means evidence is absent, not
that generation failed or was never submitted.

## Errors and exported files

No SDK, CLI or MCP path automatically retries or rebases. HTTP 409 includes the
source request context; inspect the current document and deliberately choose any
new work. A transport loss after preparation may hide a committed record. MCP
reports `outcome_unknown` and retains the preparation arguments. Read failures do
not authorize replacement preparation.

CLI exit codes for `runs`: **0** successful metadata operation (or an observed
queued/running/completed job), **2** request/transport/export failure, **3** missing,
mismatched or uncertain job evidence, **5** observed failed/partial/cancelled job,
**6** HTTP 409 conflict. Exit 0 from preparation is not a generation success signal.
MCP read results instead preserve the observation state in a successful tool reply;
clients must inspect it rather than treating `ok` as completed generation.

Existing ticket output paths, including broken symlinks, are refused before HTTP.
A missing parent output directory is refused before HTTP. Final export uses an
exclusive create and fsync. If another file appears between preparation and write,
it is not overwritten: the CLI error includes the received original record so
its ticket can be recovered to another path. An incomplete local write can leave
an owned partial file; preserve it for inspection and GET-export to a different
name. This is not an automatic rollback of the already committed server record.

## Scope and validation

The existing builder Run control still uses its tab-local preparation path. These
commands are the explicit persisted alternative, not silent UI migration. Use
Save to Workspace to create the source first. A later UI slice can expose these
same commands with dirty-draft decisions and saved run history.

The focused client suite covers all SDK/CLI/MCP operations with real SQLite and
the production projector/ticket service on synthetic nodes. It exercises lost
responses, no automatic retry, changed heads, exact seed export, corruption and
wrong response identities, output races, permission gates, one-shot observation
and retained error context. One SDK test uses real loopback HTTP. The dedicated
MCP CI jobs also run a real **subprocess stdio -> HTTP -> SQLite** scenario, restart
the agent in read mode, recover the original ticket after a later document edit,
and verify no generation endpoint was used. Test endpoint/Host fixtures are not
claims about the installed workstation's agent configuration.

The pinned optional MCP SDK is required by that CI lane, so its protocol test
cannot silently pass by skipping there. The ordinary base suite can skip it when
the optional SDK is not installed. Local dependency files were copied byte-for-byte
from the inspected parent; hosted full-checkout CI establishes wider integration.

No installed GPU/Comfy inference, native widget acceptance, model/package upgrade,
workstation restart, remote deployment or change to HUMAN_TODO.md is part of this
work. #122/#123 remain open for broader graph execution, references, UI integration,
per-node events and ownership-scoped cancellation. Automated GitHub review reached
its account quota during this continuation; green tests are not review completion.
