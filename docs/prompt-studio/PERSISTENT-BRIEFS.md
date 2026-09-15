# Save and reopen reference-led briefs

The prompt project service saves the complete CreativeIntent, its selected profile
and optional reference analysis/review context in the **existing Workspace SQLite
database**. It does not store original images, stage them to ComfyUI, run analysis,
change a runtime, or authorize generation. An empty instruction is a valid saved
draft; the compiler can still report that it is not ready to generate.

## Document and commands

A `studio.prompt-document/v1` object contains `name`, `profile_id`, `intent` and
`reference_context`. The context is either null or `{analysis, review}` using the
existing reference report and trait-selection contracts. Original observations
remain separate from current intent. The selected review may be unfinished or
historical relative to that intent; saving it does not apply it. Questions and
unknowns remain present. Context validation checks structure and role boundaries,
not current pixels or whether a model actually ran. Every read reports
`source_bytes_verified:false`. A profile ID is retained as a declaration; removing
a profile from the catalog does not make old history unreadable.

All routes are under `/api/prompt/projects/` on the normal loopback Studio server.

| Operation | Fields |
| --- | --- |
| GET `capabilities` | None; returns the current Workspace identity and limits |
| GET `list` | `workspace_id` |
| GET `read` | `workspace_id`, `id`, optional `revision` |
| GET `history` | `workspace_id`, `id`, optional `before` revision |
| GET `status` | `workspace_id`, `request_id` |
| POST `create` | `workspace_id`, `request_id`, `document` |
| POST `save` | `workspace_id`, `request_id`, `id`, `expected_revision`, `document` |
| POST `restore` | `workspace_id`, `request_id`, `id`, `expected_revision`, `restore_revision` |

All writes use one transaction for the Workspace identity, revision comparison,
immutable revision and command receipt. Same ID plus same action/content returns
the original saved revision. Different content under that ID refuses. Two clients
saving the same expected revision cannot both succeed. Restore **appends** a new
revision rather than rewinding or destroying later history. Changed locked fields
or removal of locks refuses an entire save/restore; save a deliberate alternative
as a new project instead. These loopback commands are not reviewer authentication.

A status receipt identifies a historical command. Its `project.revision` may be
older than `project.head_revision`; it does not claim the current project still
matches that save. An unknown receipt is a 404, not proof a delayed request cannot
commit. No read replays a write. Retain the original request and inspect before an
explicit exact retry. Transport/storage failure is unconfirmed, never success.

## Agent access

`studio_prompt.project_client.PromptProjectClient` reuses the existing loopback
client, disabled proxies, redirect refusal, bounded HTTP framing and no-write-retry
semantics. It preserves structured errors such as `revision_conflict`.

```python
from studio_prompt.project_client import PromptProjectClient
from studio_prompt.schema import new_brief
import uuid

client = PromptProjectClient()
workspace = client.capabilities()['workspace_id']
request = {
    'workspace_id': workspace,
    'request_id': uuid.uuid4().hex,
    'document': {
        'format': 'studio.prompt-document/v1',
        'name': 'Reference study',
        'profile_id': 'sdxl-prose-v1',
        'intent': new_brief('Keep this character; use the second pose'),
        'reference_context': None,
    },
}
# Retain request locally before this explicit write. No image generation occurs.
receipt = client.command('create', request)
current = client.get(workspace, receipt['project']['id'])
```

The same operations are available with `python -m studio_prompt.project_client`.
Use `--help`; write commands take a complete `--request` JSON file. `--output` is an
exclusive new output file, checked before transport. A failed output write after
a successful server save does not undo that command: inspect its original ID.
No MCP tool list or general-purpose command bus is added by this increment.

## Storage and remaining boundaries

Startup initializes three namespaced tables using AssetWorkspace's connection
owner. Reads use a scoped snapshot transaction and do not initialize/migrate state.
Limits: 128 projects, 256 revisions each, 256 KiB per document, 32 MiB combined
revision and canonical-command payload history, 512 KiB per request. History is
paged at 32 entries. At a cap, refuse new writes without deleting old revisions
or replay-prevention records. Safe archive/compaction remains a separate design.
The byte cap covers retained payloads, not SQLite indexes, WAL or total file size.

This follows existing workflow-document receipt patterns without treating a prompt
brief as an executable workflow graph or creating another database. The original
file-based reference draft function and its in-memory variant still check every
source byte. The new pure `validate_review` only permits saved context validation.

Browser Save/Open is a dependent UI slice. #38 retains broader shared intent
commands and generator integration; #35 retains real helper qualification;
#232 retains native reference staging/binding and #313 owner-accepted results.
No tests here prove VLM understanding, anatomical correctness or image fidelity.
The owner's original files, runtime and HUMAN_TODO decisions remain untouched.
