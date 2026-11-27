# Prepared Production intent factory

Implementation location after integration:
`prototypes/pro/P36/P36-B-20261126-2/production_intent.py`.

## Stable APIs

```python
capture_production_intent(
    experiments, project_id, stage_index,
    *, family_id, stage, studio_root=None,
)
validate_intent(intent)  # canonical SHA-256; raises ValueError on malformed input
revalidate_intent(experiments, intent, *, studio_root=None)
```

`studio_root` is an independently trusted caller input; its default is the pinned
prototype's repository root. Neither capture nor revalidation derives a trusted
root from a candidate. `experiments` is independently supplied as well. Revalidation
requires both roots to equal the captured source identity before reopening the
actual database, plan, catalog, template, library and model/input bytes.

Capture/revalidation return `passed`, structured `blockers` and either `intent`
or null. They always state `preparation_only=true`, `generation_submitted=false`,
`submission_authority=false`, `budget_authority=false`, `runtime_ready=false`.
A passed report describes retained preparation and current serial file reads,
not current permission to submit, an active GPU lease/queue observation or an
atomic freeze of engine-open bytes.

### Intent shape

The strict top-level fields are:

```text
schema = las.p36-worker-intent/1
operation = comfy.generate.v1
family_id, stage, project_id, stage_index, job_id
preset_id, backend_id, graph, seed, batch_count = 1
source_snapshot
```

`job_id` is Studio's `project_storage.stage_job_id(project_id, stage_index)`.
`graph` is the exact retained prepared graph. With batch one, equal seed bindings
and no prompt wildcards, `_batch_graph(job, 0)` does not change it. The dispatcher
should bind the serialized operation-body bytes/hash too; this reader does not
serialize or send a POST.

`source_snapshot` has these exact keys:

```text
studio_root, experiments_root, workspace_id
project_record, budget_record, plan_file_sha256
catalog_sha256, preset_record, preset_sha256, template_sha256
library_sha256, bundle_sha256, observed_files, preparation_only = true
```

`project_record` is the actual `{id, root_id, plan, state, created}` SQLite row,
with JSON fields decoded strictly. The full immutable plan, current project
state and complete preflight bundle remain bound. `budget_record` is the real
`{id, allowance, reserved}` row. These records are observations, not a new budget
or a decision to start/resume. A change in either invalidates the prior intent.

Each `observed_files` row is exactly
`{kind, path, bytes, mtime_ns, sha256}`, where kind is `model` or `input`. The
reader freshly hashes each declared file, rejects a change during the read,
matches the retained bundle and applicable exact-path library pin, and reuses
Studio's model-requirement projection to detect missing graph dependencies.
Full catalog/library hashes deliberately make unrelated source changes visible;
the caller must inspect and prepare a new intent rather than silently update it.

## Hook and refusal boundary

The intended hook is **before `Studio.create_job`**. Capture refuses if the
deterministic future job directory already exists. Such a job belongs to the
existing retained-submission/observation protocol, not a fresh operation. The
coordinator may publish its synthetic job only after a durable claim; it must
retain the captured intent and stop trying to recapture that operation as new.

The factory opens source databases with SQLite `mode=ro` and `query_only`; it
constructs no Studio, Production or ModelLibrary. It invokes no runtime/network
function and creates no source directory. It reuses `project_storage.require`,
the existing Production fingerprint, pure graph checks and model-requirement
projection. Metadata reads use the existing prototype's narrower 2 MiB bound.

It refuses unsupported native operations, non-comparison plans, batch counts
other than one, prompt wildcards, private requests/paths, linked paths, unknown
or malformed projects, dirty materialized plans, graph/template mismatch,
unresolved dependencies, mismatched file bytes/pins and an existing target job.
It does not independently rerun Studio.prepare, recognize images, authenticate
the owner or validate current runtime node schema. The schema hash remains a
recorded preflight fact; the installed-worker adapter must reobserve its runtime.

## Shared fixture helper

```python
make_production_case(
    root, *, experiments=None, family_id='p36-fixture', stage='turnaround'
)
```

The helper is in `production_intent_fixtures.py`. Both roots must lie under the
repository `.runtime/`. It returns:

```text
studio_root, experiments, project_id, stage_index = 0
family_id, stage, intent, studio, model_path, input_path
```

It uses actual `Production.create`, `Studio.prepare`, `production_preflight`,
plan publication and SQLite storage. Node-info, system and disk-capacity readings
are explicit synthetic fixtures. Threads are disabled, no HTTP server starts,
and there is no live network or generation. The custom fixture sampler and tiny
model/input bytes are never loaded or decoded. Startup job loading is suppressed
so an existing actual-Workspace fixture can be reused without normalizing its
minimal historical job files.

## Focused verification

Initial test-first run failed because the requested module did not exist. The
first fixture execution then correctly hit Studio's real minimum-free-storage
gate; the fixture now supplies an explicitly synthetic disk-capacity observation
alongside its existing synthetic node/system observations. No machine setting or
real runtime check was weakened.

```sh
py -3 -m unittest discover -s prototypes/pro/P36/P36-B-20261126-2 -p test_production_intent.py -v
```

Last run: **24 tests passed**, **0 skips**, **4.544 seconds**, exit **0**. It covers
read-only capture, exact graph/source/pin bindings, decimal seed spelling,
malformed input, missing/link/unreadable paths, budget/state/Workspace changes,
source changes during final recheck, and preservation of a shared Workspace's
exact retained job hashes. Parent integration and the coordinator's aggregate
proof remain separate. All new implementation files stay in the P36 run after
integration; this work changes no installed app or UI.

Independent review reproduced a serialized-intent numeric-alias bypass: Python
dictionary equality treated an integer graph input and a floating-point input as
equal. Graph, plan, final row recapture and complete-intent comparisons now use
canonical bytes. A regression changes only the serialized candidate graph's seed
from integer `7` to `7.0`; strict validation and revalidation both refuse it.
