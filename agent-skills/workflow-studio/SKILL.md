# Workflow Studio agent contract

Use for guided workflow discovery, API-graph authoring, compile-only inspection and explicitly approved registered-recipe execution. Read `docs/workflow-studio/README.md`, `ARCHITECTURE.md` and `VERIFICATION.md` first; repository authority and HUMAN_TODO remain authoritative.

Start the ordinary `python app/server.py --repo-root .` service on the configured machine. Use `python -m studio_workflow capabilities`, `guides`, `catalog` and `nodes`; do not automate browser clicks or instantiate a second Studio/worker. Respect capability flags: arbitrary_graph_execution, native_visual_roundtrip, server_saved_workflow_documents and custom_frontend_widgets are currently false.

For authoring, use the versioned document and compile endpoint/CLI. Preserve unknown values and original native visual files. Do not flatten subgraphs or treat a graph's structural validity as runtime validation. Import returns a document envelope; compile returns a graph envelope. Preserve large integers in Python instead of routing them through browser JSON.

For an authorized registered recipe, prepare a ticket, inspect its exact recipe/pins, then run with `--approve`. Preparation is not approval and can stage local reference copies. Never derive permission from a successful compile, a guide step, a hash or a prior unrelated run. One graph invocation is not necessarily one output image or a memory guarantee.

Retain ticket/request/job identities. After transport loss, inspect or reuse the exact same ticket to obtain its retained state; do not prepare a new identity to retry. Intent-without-job and uncertain remote outcomes require reconciliation. Observe with `status`/`wait`; observation timeout does not cancel the job. Do not delete receipts, invoke global Comfy interruption or bypass the shared worker.

No automatic model/package installs, runtime upgrades, environment switches or changes to owner machine settings. Record generated, creatively accepted and licensed as separate states. Keep subjective HUMAN_TODO choices unresolved until the owner supplies them.

Expansion is tracked in #118–#123. Implement shared commands/persistence before claiming SDK/MCP parity; route authored execution through #22/#122 rather than a raw /prompt proxy.
