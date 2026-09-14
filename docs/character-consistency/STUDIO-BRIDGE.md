# Controlled edits through the existing Studio

This is the runtime follow-up to [the offline editing bridge](EDITING.md), scoped to #71/#65. `scripts/character_edit_bridge.py` is a local-agent **client**, not another server, model runner or GPU queue. It can prepare an edit, upload its references, create an ordinary Production comparison, explicitly start it, retrieve a completed candidate and compose that candidate through the original mask. Transport/artifact IO and pure preparation contracts live in the companion `character_edit_bridge_io.py` and `character_edit_bridge_plan.py` modules.

The same project is visible in the existing Studio Production/Review interface.
Use an explicit [campaign receipt](CAMPAIGN-BUDGETS.md) to share a cap across
independent v2 edit revisions; omitting it retains legacy v1 behavior. The
separate [Krita document session](KRITA-DOCUMENT-SESSION.md) can import a protected
result as a reversible native layer. Creative acceptance and multi-actor neural
generation remain separate #71 work.

## Supported first slice

One actor, an approved canon attestation, one identity reference and optionally one costume/style/pose reference. Operations: anatomy repair, costume change and local repaint. The first native slot is the **current context crop with composition role**; remaining slots retain the actor reference roles. The existing `qwen-2ref` or `qwen-3ref` preset is chosen by the exact reference count. No reference is silently dropped or labelled as a different role.

Qwen receives semantic image guidance, not a ControlNet skeleton or the grayscale write mask. The original edit mask is enforced during deterministic final compositing. A correct mask and successful generation do not prove the intended anatomy/costume change occurred.

The source crop must be opaque, PNG and have no ICC/EXIF processing ambiguity. Existing RGB+tRNS and RGBA handling in the pixel bridge is unchanged. This **neural** bridge deliberately rejects genuinely transparent source crops rather than inventing a matte/alpha policy. Alignment padding only is converted to explicit black RGB. No crop resampling occurs on the way in. Candidate dimensions must match the padded crop exactly, on the recipe's own dimension grid (multiples of 16 for the native Qwen presets) and within its pixel ceiling; `prepare` refuses a crop that is off the grid rather than resizing anything. The recipe itself scales the composition reference to one megapixel before the encoder, which is what `TextEncodeQwenImageEditPlus` does to every reference regardless; the candidate canvas is a separate explicit latent bound to width and height. Resolve a larger crop or an explicit scale/alpha pipeline separately rather than silently resizing the result.

Each comparison supports one to four distinct integer seeds. Primary candidates plus the reserved repair count must fit the existing Production allowance, at most sixteen. This slice does not execute repairs or warmups. Do not hide those inside a candidate. The old twelve-case #64 study is not changed or charged by this programme.

## Workflow

Use an existing valid edit document/intent/plan from [EDIT-RUNBOOK.md](EDIT-RUNBOOK.md), with actual references and an actual recorded canon decision. The synthetic CPU demo has no approved canon and is **not** silently promoted by this client. Commands below assume a workspace at `C:/AI/character-lab/my-edit`, a compiled `edit-plan.json` and a current exported `document.json` in that workspace. Output names are new workspace-relative paths; quoted Windows paths with spaces are supported.

### 1. Prepare locally; no HTTP and no inference

```console
python scripts/character_edit_bridge.py prepare --workspace C:/AI/character-lab/my-edit --plan edit-plan.json --out handoff-v1 --seeds 2026091201 2026091202
```

This checks the real canon schema/attestation, reference hashes, mask scope and the current local route evidence. It emits the exact context bundle, model-facing context, role map, compiled instruction, local native-template hash and all source dependencies. The identity image must be an identity reference of the approved canon. It is not sufficient to point an actor at some other image while retaining the same canon file.

The compiled positive instruction must fit Studio's 8,000-character input limit, including the bridge's visible instruction suffix. Overlength input is rejected before an output directory or upload is created; text is never silently truncated.

Read `handoff-v1/handoff.json`, including the scope and policy warnings. An approval record is a local attestation, not cryptographic reviewer authentication. No tool here can infer the owner's creative choices.

### 2. Stage through Studio; uploads and preflight only

Start Studio normally. Then:

```console
python scripts/character_edit_bridge.py stage --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json
```

The client verifies the Studio workspace identity, live raw template and the pinned authored catalogue entry (excluding only derived UI defaults, runtime-block text and missing-LoRA display fields); uploads and reads back exact PNG bytes; previews each seed through the real Studio reference compiler; checks role order, dimensions and single-image semantics; then creates one ordinary Production comparison. It independently projects the prepared control/reference bindings into the pinned template and requires each native preview to match. A slot swap between the catalogue read and Preview cannot become a new self-consistent baseline. It then verifies the resulting graph and the exact Comfy input hashes pinned by Production. Stage never calls `/api/jobs`, `/prompt`, a model loader or a generation start endpoint.

The returned project contains the actual Production bundle and identifier. Inspect it and the normal Studio comparison before starting. Model/node preflight still belongs to Studio and can fail if its configured runtime is incomplete. Installation state is not inferred from a source-reviewed preset.

### 3. Explicitly start the recorded comparison

```console
python scripts/character_edit_bridge.py start --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json
python scripts/character_edit_bridge.py status --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json
```

Start rechecks original source bytes, workspace identity, template, authored catalogue bindings and pinned Production plan. A runtime-blocked preset is rejected separately from catalogue identity. Its intent is persisted **before** the HTTP request. Studio reserves the existing root allowance and owns execution, prompt IDs, stopping and any uncertain-job reconciliation. The client does not poll in a background loop, repeat Start, start ComfyUI or interrupt another job. Use the existing Studio Stop control for a running comparison.

One receipt directory, `.edit-bridge-<edit-plan-sha256>/`, is used per immutable edit plan in the local workspace. Repeating the command or supplying another seed list/output folder does not create another comparison allowance. A matching server-side project name also blocks accidental duplicate creation. This is a cooperative local-client rule, **not a global authorization boundary against arbitrary clients or copied/rehashed plans**. Linking independent edit revisions and future repair plans to a shared campaign root remains #65/#71.

### 4. Retrieve a candidate; selection does not mean approval

```console
python scripts/character_edit_bridge.py collect --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json --index 0
```

The index is zero-based in the seed list. The client checks the deterministic Production stage/job relationship, one completed image, the recorded job recipe and prompt ID, Workspace ownership and the downloaded byte hash. It refuses silent resizing or substituting an unrelated asset. A successfully completed early stage can still be collected if a later stage failed. Failed/rejected candidates and the original sources remain intact.

The candidate and a source-bound execution receipt are staged, verified and published together under the existing command lock. An interrupted staging directory is retained, while a fresh explicit Collect can retrieve the same completed job without another generation. No review endpoint is called; the receipt remains `unreviewed`. Re-running collection never overwrites published files. See [the recovery and role contracts](EDIT-RECOVERY.md) for process-death handling and the retained legacy-partial boundary.

### 5. Compose into a new local revision

Export the **current** document snapshot from the editor/workflow before applying. Then:

```console
python scripts/character_edit_bridge.py compose --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json --index 0 --current-document document.json --out proposed-revision-2
```

A changed source, mask, canon, reference or exported document revision blocks application. The existing pixel bridge verifies the prepared bundle and restores original RGBA outside the write mask. Its result includes changed-pixel and protection counts. Inspect original/candidate/final at target size: a no-op or a wrong hand remains a failed creative edit even with perfect preservation.

This writes a new file, not an accepted asset and not a change to an open Krita canvas. Checking an exported document cannot detect unsaved native edits that have not been exported; a real native revision lock remains a separate requirement. Import the proposed result as a new layer through the native bridge once that integration exists, or review it in the editor without overwriting the original.

## Recovery rules

| Interrupted operation | Recovery |
|---|---|
| Upload/preflight | Rerun Stage with `--resume-uploads` explicitly. Known uploads are read back, not uploaded again. An upload whose response was lost may leave an orphan file and be copied again; this is non-generative and spends no model allowance. No existing file is deleted. |
| Production creation | `reconcile` is GET-only. It adopts exactly one matching project only after checking its graph, reference hashes, budget and ownership. Zero or several matches stay unresolved. It does not repeat creation. |
| Start | Use `reconcile-start` only for a retained `start_pending` receipt after a lost response. It rechecks the original inputs, Studio identity and exact project provenance with GET requests, then records `started` only when Production retained the same project's exact stage reservation and an allowed post-Start state. It never repeats Start or Resume, changes a reservation, queues work, or treats inference as successful. A planned/mismatched/unknown project stays pending for Studio inspection. A completed result can still be collected. Studio owns execution recovery. |
| Client process killed | A command lock can remain. First confirm that its PID is no longer running and no bridge writer is active, then remove only that lock. Preserve state, events and all outputs. This client never kills processes or steals a lock. |
| Existing candidate/output | Inspect and retain it. Choose a new composition output for another review; do not erase receipts to gain another generation budget. |

```console
python scripts/character_edit_bridge.py reconcile --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json
python scripts/character_edit_bridge.py reconcile-start --workspace C:/AI/character-lab/my-edit --handoff handoff-v1/handoff.json
```

State replacement is atomic in the local filesystem, with fsynced file contents and retained intent phases. It is not a distributed transaction, an exactly-once guarantee or a power-loss guarantee for every filesystem. The Production database-commit/plan-file recovery gap remains owned by #65; this client leaves such an uncertain result visible instead of creating a replacement.

Pre-review handoffs without the authored-catalogue pin are rejected. Preserve their receipt directories and any existing Production project. Do not delete a journal or blindly recompile to gain another allowance. Inspect the old project in Studio first; a started/uncertain project must be reconciled and its actual outputs retained before planning any new generation. An explicitly abandoned, never-started plan can be replaced by a reviewed new edit revision; this is not automatic migration or cross-revision budget enforcement.

## Artistic-control policy

The chosen route must satisfy the compiled edit preferences. The client adds no content classifier, hosted fallback or creative keyword list. Its own HTTP connection is numeric IPv4 loopback, ignores proxy environment variables and rejects redirects; the Studio, model and custom-node stack still require their own network/policy audit. The stored Qwen policy remains **unknown/unverified**, not relabelled unrestricted because a new client can call it. The authored native settings are retained; seed, width, height, references and the visible edit instruction are the bounded projections here.

The operating protections (source preservation, stale-state checks, budget and no repeated uncertain submission) remain distinct from model content restrictions. See [TOOL-POLICIES.md](TOOL-POLICIES.md).

## Evidence and next gate

The implementation ships with protocol/fault tests, actual loopback HTTP transport tests, real source/preset/approval integration tests, and a complete Handler → Production → Workspace → collect → protected-composition test. Only the neural boundary and hardware preflight are substituted in the latter: it does not establish a GPU result, workstation compatibility or anatomy success.

```console
python -m unittest discover -s tests -p "test_character_edit_bridge*.py" -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

First workstation acceptance: one genuinely successful anatomy correction and one costume change, real returned prompt IDs, pinned native bundle, source/candidate/final comparisons and cleanup time. Then #72 evaluates accepted-edit yield under its own frozen budget. Do not extend to multi-actor scenes or automatic approval merely because these plumbing tests pass. `HUMAN_TODO.md` creative choices remain unchanged.
