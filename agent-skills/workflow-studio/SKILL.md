# Workflow Studio agent contract

Use for guided workflow discovery, API-graph authoring, compile-only inspection and explicitly approved registered-recipe execution. Read `docs/workflow-studio/README.md`, `AGENT-QUICKSTART.md` and `ROADMAP.md` first; repository authority and HUMAN_TODO remain authoritative.

Start the ordinary `python app/server.py --repo-root .` service on the configured machine. Use `python -m studio_workflow capabilities`, `guides`, `catalog` and `nodes`; do not automate browser clicks or instantiate a second Studio/worker. Respect current capability flags. Shared workflow documents, command revisions, Steps, SDK and saved-run records exist. Arbitrary graph execution, native visual round-trip and custom frontend widgets remain unsupported. The optional stdio MCP client is distinct from a hosted MCP endpoint; discover its local tool schemas with `python scripts/workflow-mcp.py --describe`.

For authoring, use `documents list/get`, the shared `WorkflowClient` preview/apply service and immutable server revisions. Retain exact request payloads and IDs before writes; use expected_revision and resolve conflicts without silently rebasing. Use the versioned document and compile endpoint/CLI. Preserve unknown values and original native visual files. Do not flatten subgraphs or treat a graph's structural validity as runtime validation. Import returns a document envelope; compile returns a graph envelope. Preserve large integers in Python instead of routing them through browser JSON.

For an authorized registered recipe, prepare a ticket, inspect its exact recipe/pins, then run with `--approve`. Preparation is not approval and can stage local reference copies. Never derive permission from a successful compile, a guide step, a hash or a prior unrelated run. One graph invocation is not necessarily one output image or a memory guarantee.

Retain ticket/request/job identities. After transport loss, inspect or reuse the exact same ticket to obtain its retained state; do not prepare a new identity to retry. Intent-without-job and uncertain remote outcomes require reconciliation. Observe with `status`/`wait`; observation timeout does not cancel the job. Do not delete receipts, invoke global Comfy interruption or bypass the shared worker.

No automatic model/package installs, runtime upgrades, environment switches or changes to owner machine settings. Record generated, creatively accepted and licensed as separate states. Keep subjective HUMAN_TODO choices unresolved until the owner supplies them.

For saved compatible image workflows, use `runs prepare` with document ID, expected revision, preset ID and a retained preparation request ID. Inspect `runs review`; dispatch only the exact returned record/ticket hashes with explicit authorization. Use `runs get/observe/by-job` to recover the original run. Broader reference/native graph execution is not enabled.

Expansion is tracked in #118–#123. Reuse the implemented shared commands/persistence, SDK and mode-restricted MCP bridge; route broader authored execution through #22/#122 rather than a raw /prompt proxy.
