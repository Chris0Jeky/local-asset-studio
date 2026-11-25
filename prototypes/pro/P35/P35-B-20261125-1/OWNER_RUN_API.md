# P35 owner runner contract

`owner_run.py` requires Python 3.12 or newer and only uses the standard library. It is an adapter to the existing Studio Production coordinator. The selected plan contains ordinary recipe intents; the adapter never submits a graph directly to ComfyUI, launches a process, downloads a model, uploads a reference, switches a backend, resumes a run, or marks art/licence acceptance.

## Commands

```console
python owner_run.py --plan owner-plan.json --prepare --runtime C:\path\to\repo\.runtime
python owner_run.py --plan owner-plan.json --start --runtime C:\path\to\repo\.runtime
python owner_run.py --plan owner-plan.json --status --runtime C:\path\to\repo\.runtime
```

`--prepare` creates and verifies every Studio comparison project without starting generation or reserving Studio generation allowance. `--start` prepares if necessary, then starts each chunk exactly once and waits for verified execution completion before the next. A repeated completed command observes only. `--status` uses GET requests only and leaves the journal byte for byte unchanged; it writes new raw response evidence beneath `.runtime`.

The default endpoint is `http://127.0.0.1:8191`. `--base-url` accepts only canonical numeric loopback HTTP URLs with an explicit port and no credentials, path, query or fragment. HTTP redirects are refused and proxy environment variables are ignored. Requests include the same-origin `Origin` header Studio requires. Alternate loopback addresses/ports are useful for inert fixtures; the actual Studio currently expects `127.0.0.1:8191`.

The default runtime root is the current working directory's `.runtime`. The launcher should pass the repository's absolute `.runtime` explicitly. GET/start requests default to a 60-second HTTP bound; `--request-timeout` accepts 0.01–60 seconds. Preparation has a separate `--prepare-timeout` (default 600 seconds, range 0.01–1800) that applies only to `POST /api/production`. Choose it before the first attempt. Its value is retained in the journal and in each fsynced create intent before the request is sent. Increasing this limit never retries an earlier request. The default polling interval is 5 seconds; `--poll-interval` accepts 0.01–60 seconds.

Exit codes: `0` successful preparation, completion or read-only status; `2` refusal, halt or uncertainty; `130` handled Ctrl+C. Standard output is a JSON summary. Raw request/response bodies and local paths are not emitted in the summary.

## Offline plan: `p35-owner-run/v1`

Required top-level fields:

| Field | Contract |
| --- | --- |
| `schema` | Exactly `p35-owner-run/v1`. |
| `campaign_id` | 64 lowercase hex characters, derived by the compiler from its frozen campaign inputs. |
| `plan_id` | SHA-256 of the full plan except this field, serialized with sorted keys, compact separators, UTF-8, `ensure_ascii=False`, `allow_nan=False`. |
| `backend_id` | Exactly `primary`. |
| `expected_identity` | Exactly `{app:"local-asset-studio", workspace:<absolute owner-selected repo path>, version:"production-workspace-1"}`. All three values must match `GET /api/identity`. The API exposes no instance identifier. |
| `max_attempts` | Integer 1–240; total selected variants must fit. Smoke selection should normally use 12. |
| `max_seconds` | Integer 60–14400 for the campaign's start/observation window. |
| `chunks` | 1–120 ordered route/case chunks. Each selects two or three distinct seeds. |

Required chunk fields:

| Field | Contract |
| --- | --- |
| `id` | Unique `[a-z0-9][a-z0-9_-]{0,63}`. |
| `name` | Exactly `P35 <first 16 campaign_id characters> <id>`. |
| `expected_inputs` | Array of unique `{file,sha256}` records for existing Studio uploads. Must exactly cover named `reference`/`last_reference` controls and every filled reference slot. |
| `expected_models` | 1–64 unique `{file,sha256,bytes}` records. `file` is a normalized POSIX path relative to the model directory. Actual prepared model filenames, hashes and byte counts must match the entire set. |
| `expected_graph_sha256` | One distinct digest per ordered seed variant. These must be derived from the frozen route's actual preparation semantics. Studio graph hashes use sorted compact JSON with **`ensure_ascii=True`**, unlike the owner-plan digest. |
| `payload` | Exactly `{name,recipe,variants,max_seconds,max_generations}`. `name` equals the chunk name, and `max_generations` equals the variant count. |

Optional `expected_pruned_reference_slots` defaults to `[]`. It declares native trailing slots Studio appends when a shorter reference board is supplied, e.g. `[{"slot":2,"role":"pose"}]`. Slots must be contiguous after the explicitly supplied references. Every appended response record must exactly equal Studio's `{slot,role,file:null,pruned:true,contribution:"",avoid:""}` record. Undeclared slots, different roles or hashes on a pruned slot are refused.

The recipe contains exactly the required `preset_id`, scalar `controls`, `references`, and `expected_template_sha256`, plus optional `parent_assets` (up to eight IDs). Each variant contains exactly `label` and `controls:{seed:<integer 0..2**63-1>}`. Extra generation, parent-project, workflow, script, handoff and combine-plan routes are not accepted. The template pin, exact ordered prepared graph pins, uploaded input pins and complete model pins are checked together before every start. Sidecar graphs are evidence only and carry no execution authority.

## Live API contract

Only these endpoints are used:

| Method and route | Expected result |
| --- | --- |
| `GET /api/identity` | `200`; exact pinned app/workspace/version values. |
| `GET /api/backends` | `200`; active primary, no switch/admission blocker, primary installed/online/ready, no held GPU lease. The first primary URL/root is pinned in the journal. |
| `GET /api/production` | `200` array; exact-name collision checks and read-only reconciliation of lost create responses. |
| `POST /api/production` | `201`; one bounded comparison-create payload, returned project must be `planned`. |
| `GET /api/production/<32hex-id>` | `200`; full plan, pinned inputs/models/graphs, raw state, attempts, jobs and prompt IDs. |
| `POST /api/production/<32hex-id>/start` | `202`; `{}` body, one intent per chunk. |

Studio comparison success normally means `awaiting_review`. The adapter records execution complete only when every stage has a completed attempt and matching completed job, the job belongs to this project, has `batch_count:1`, and retains the same single known prompt ID as its attempt. `reviewed`/`completed` are also accepted only with the same execution evidence. An owner `stop_requested` flag halts progression even if the final stage finished. Visual classification remains `unreviewed` and licence classification remains `unknown` regardless of execution success.

## Journal and uncertainty

State is retained under `.runtime/p35-owner-runs/<plan_id>/`. The exclusive `run.lock` uses `O_EXCL`. A contender acquires ownership before reading a mutable journal, preventing a stale contender from overwriting another run's completed accounting. `journal.json` is created exclusively, then updated atomically. File data is flushed and `fsync`ed before any create/start POST. POSIX directory entries are also fsynced; Windows replacement uses `MoveFileExW` with replace-existing and write-through flags.

Every side effect has a durable intent containing its exact request before the network call. Raw received bodies and HTTP receipt metadata are saved under `evidence/`, with their byte hashes. Known prompt IDs are retained. HTTP errors, malformed responses, response loss, timeout, interruption, unexpected states and unproven completion halt progression. An ambiguous create has no trusted project ID; status uses the unique name only to show candidates. An ambiguous start retains the known project ID; status can observe it. Neither case permits automatic adoption, replay, resume or lock removal.

Clean preparation/completion releases this process's lock. Any failure or crash preserves the lock and prior durable intent. No command automatically reclaims it. Retrying generation requires a new manually reviewed plan and reconciliation of the existing projects; moving/deleting the journal or changing the runtime directory is not a recovery procedure.

The local `attempts_reserved` counter conservatively counts start intents against the plan cap; it is not a claim that those attempts reached the GPU. Preparation does not consume the generation/observation campaign window: `run_started_at` remains null until immediately before the first start. Later chunks are admitted only when their full reviewed `max_seconds` fits the remaining campaign window. At observation timeout the adapter stops issuing work and leaves the outcome uncertain. Studio checks its own time budget at stage boundaries; an already active GPU job can finish after either budget. No hard interrupt, queue deletion or runtime termination is attempted.

### Slow preparation and owner recovery

Studio's `production_preflight` hashes every pinned model afresh for every seed while preparing. The following nominal hash-input volumes are derived from the frozen component byte counts in `routes.json`, multiplied by two or three seeds. They are arithmetic from the source inventory, not measured disk traffic, throughput or preparation time; repeated reads may be served from an OS cache, and other validation adds work.

| Route | Two-seed create | Three-seed create |
| --- | ---: | ---: |
| Klein 4B reference | 24.904 GB | 37.355 GB |
| Klein 9B Copy Pose | 33.899 GB | 50.848 GB |
| Klein 9B skeleton | 33.733 GB | 50.599 GB |
| Qwen three-reference | 47.466 GB | 71.199 GB |

Here GB means decimal billions of bytes. A three-seed Qwen preparation would need more than 1.187 GB/s effective hashing/input processing to finish these hashes alone within 60 seconds. The 600-second separate prepare default reduces the chance of an avoidable lost create reply without weakening uncertainty handling.

If creation still times out, keep the original journal and lock. Use `--status` for GET-only inspection after giving Studio time to finish the pending request. A temporary zero-match listing is not proof that creation failed; it does not authorize another POST. Multiple matches, changing state, or an unknown outcome remain blocked. If exactly one existing planned project is identified, the owner can review that existing project's complete retained recipe, graph/model/input pins and absence of reservations/attempts, then use its existing Studio Start action explicitly. The runner does not adopt that candidate, and its original journal remains uncertain. Any later campaign shard must be reviewed anew, exclude reconciled work, and account for prior conservative start intents. Do not delete locks, recreate the same payload, or reset a runtime as a retry shortcut.

## Limits and validation scope

Plans are limited to 2 MiB, each HTTP response body to 8 MiB, journals to 16 MiB, and retained evidence to 512 MiB / 12,000 receipts. Duplicate JSON keys and non-finite numbers are rejected. Requests and response bodies are bounded. Exhausting a limit halts the run.

The integration suite uses inert loopback HTTP servers and real CLI subprocesses. It covers lost create/start responses, timeouts, killed processes, Ctrl+C, concurrent launches and stale snapshots, wrong backends/workspaces, redirects, proxy variables, unsupported URLs, changed graph/input/model pins, malformed/completion states, exact native board padding, attempt/time caps, and GET-only status with unchanged journals. It performs no Studio/GPU generation, upload, model access, runtime change or download. Windows launcher behavior, Windows power-loss durability and the owner's actual GPU environment remain unverified.
