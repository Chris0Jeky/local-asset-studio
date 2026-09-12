# Runtime switching and pinned-install safety

Implementation slice for **#2 and #9**, based on main
`93b1f847b29cc6e5da488eacf297556453e94116`. Read this beside
[PRODUCTION-WORKSPACE.md](PRODUCTION-WORKSPACE.md), [HIDREAM.md](HIDREAM.md), and
[H3-WINDOWS.md](H3-WINDOWS.md). It extends the existing managers and UI routes;
it adds no generation queue, model manager, automatic install or page-load inference.

## Why these issues first

#2 already has explicit switches and actual HiDream concept/restyle evidence.
#3's remaining comparisons require the real workstation and artistic review.
#9 already has curated pins, browser-download reuse and resumable installs. This
pass addresses destructive edge cases in those foundations rather than repeating
those implementations. Neither broad issue is closed by these changes.

The old switch accepted `{}` as an empty queue, ignored inaccessible listeners,
and could discover a foreign target only after stopping the working backend. Its
startup-error handler also terminated the newly launched process without checking
whether direct ComfyUI work had arrived. The old downloader checked `exists()` and
then renamed its partial file; a competing destination created between these
operations could be overwritten on POSIX. Legacy verification receipts could
follow a same-sized replacement or a different backend root.

## Module boundaries

| Module | Responsibility |
|---|---|
| `app/backend_contracts.py` | Pure URL, queue and file-presence contracts; no Torch imports, mutations or HTTP |
| `app/backends.py` | Existing Studio-owned switch operation, persisted intent, process inspection and explicit launch |
| `app/download_contracts.py` | Portable paths, byte-range validation, file-identity receipts, no-clobber publication, installer owner token |
| `app/model_library.py` | Existing catalog, inventory, installer and progress state; no parallel discovery service |

### Backend transition contract

1. Validate the chosen launcher and required baseline files. Hold the existing
   Studio gate; refuse local queued/running/uncertain generation or production work.
2. Inspect any retained failed/interrupted startup PID before creating another
   operation. A still-loading process without a verified listener blocks a retry.
3. Observe **both** `queue_running` and `queue_pending` lists at every configured
   endpoint. Missing/wrong-type fields, timeouts, HTTP errors, invalid JSON and
   inaccessible ownership are unknown, never idle. Only connection-refused plus
   no observed listener qualifies as offline.
4. Persist intent before starting the worker. The worker repeats the checks and
   inspects every listener before stopping any current backend. An unrelated,
   wildcard, ambiguous or permission-blocked listener is preserved.
5. Require the configured interpreter and actual executed entry script, not a
   later `.py` argument. Check exact primary listen/port options, isolated root
   arguments, and PID plus creation time across the preflight/stop boundary.
6. Recheck each queue immediately before stopping its matched idle process. Do
   not clear queues, interrupt jobs or use a global kill operation.
7. Launch only the selected profile when absent. Require a healthy, idle endpoint;
   a newly launched endpoint must belong to the recorded child PID. Reusing an
   existing process needs health too. Persist completion and release the gate.

Managed endpoints are explicit `http://127.0.0.1:<port>` URLs. The primary launcher
now honors its configured port. Profiles must use distinct ports. Observation
ignores ambient HTTP proxies, refuses redirects and bounds response bodies to
1 MiB. ComfyUI's HTTP APIs are observations, not a cross-client transaction.

If a new runtime times out or fails readiness while its child is alive, retain it
and record `preserved_pid`, logs and recovery instructions. **Do not automatically
terminate it or restart another model family.** A second explicit switch checks
that retained process first. A disk/worker-start failure releases the in-memory
switch gate; interrupted switches never restart merely because Studio starts.

### Readiness is deliberately narrow

`BackendManager.snapshot()` retains its existing fields and adds `readiness` with
named requirements, exact paths, missing entries and a scope. H3 checks its
isolated loader and the five documented preview components: diffusion, encoder,
video VAE, audio VAE and eight-step adapter. Empty files do not count. HiDream
checks its launcher and Transformers overlay; preset-specific model validation
remains in the existing execution path.

`hash_verified` and `runtime_compatible` in this inexpensive presence report are
`null`. They are not inferred from filenames, startup or a successful HTTP reply.
`installed` means these declared files are present; `online` means the endpoint
answers the health shape. The switch success message explicitly says inference
was not checked. Existing native-loader failures, HiDream warnings, AMD-specific
execution evidence, source provenance and licence decisions are unchanged.

### Installer transaction and publication

```
validate immutable request snapshot
  -> acquire per-process gate + cross-process owner-token lease
  -> persist queued state -> explicit worker
  -> existing-file verification OR browser reuse OR bounded transfer
  -> stable SHA-256 + size verification
  -> atomic create-if-absent publication
  -> path/file-identity-bound installed receipt
  -> release only our lease and gate
```

The lease is acquired before writing `queued`, preventing another Studio/CLI
instance from overwriting the active install's receipt. It records version,
random owner token, PID, asset ID and start time. Release checks the owner token;
replaced/corrupt locks are preserved, never silently reaped. The worker uses the
exact catalog entry reserved at start, even if the manifest changes meanwhile.

Transfers require identity encoding and an exact remaining `Content-Range`
(start, end and total) for resume. When provided, Content-Length must match.
Unexpected statuses and headers are rejected before appending; reads and copies
remain chunk-bounded. Space is checked initially and before each chunk against
existing 20 GiB headroom. Complete partials can be verified/published without
network access; empty partials can resume. Failure receipts retain the measured
partial byte count, or `null` when a path cannot be safely inspected.

Every model transfer now owns its redirect handler. The initial URL must be an
HTTPS/443 URL without user-info on `huggingface.co`, `civitai.com` or
`civitai.red`; every redirect is checked before its target is opened, stays in
the same provider family and the chain stops after five hops. Each accepted host
must resolve only to globally routable, non-multicast addresses. A cross-host hop retains only
`User-Agent`, identity encoding and `Range`, so credentials, cookies, custom Host
values and future caller-specific headers cannot travel to a storage host.

The allow-list is deliberately concrete. Hugging Face hosts are the exact Hub,
LFS, transfer and regional CDN names published in
`https://huggingface.co/.well-known/meta.json` on 12 September 2026. Civitai
supports its two source domains, `b2.civitai.com`, its named
`civitai-modelfiles-b2` Backblaze endpoints, and delivery-worker buckets in its
fixed Cloudflare R2 account. Arbitrary `*.hf.co`, `*.backblazeb2.com` and
`*.cloudflarestorage.com` names are not trusted. Provider endpoint changes need
an explicit code and test update rather than silently broadening transfer reach.
Address validation precedes the standard HTTPS open, but the OS resolver runs
again during connection setup; this reduces accidental/redirect SSRF reach and
is not DNS pinning against a resolver that changes answers between those steps.
Policy refusal preserves existing `.part` bytes and records their measured count
through the existing failed-install receipt path.

SHA-256 verification compares file metadata before and after hashing. Publication
uses a same-filesystem hard link followed by removal of the staging name: an
existing destination causes an atomic failure rather than replacement. There is
**no POSIX rename fallback**. Unsupported hard-link filesystems retain the verified
partial and require explicit recovery. Cross-volume browser sources use a verified
copy staged in the target filesystem before publication. Original browser files
are never deleted. Reused browser hard links share data; later mutation invalidates
the receipt rather than providing immutable storage.

Paths are portable relative paths: traversal, alternate streams, reserved Windows
names, trailing-dot/space components and ambiguous separators are rejected. Model
or partial symlink/junction components and shared partial hard links are refused.
This is protection against accidental/cooperative races, not a filesystem sandbox
against a privileged local process replacing path components adversarially.

Receipt version 2 binds SHA-256 to the absolute destination and device/inode/size/
mtime/ctime observations. Old or changed receipts become
`explicit-reverification-required`; **they do not trigger a download or rehash on
page load**. Explicit Install verifies an existing matching file without network.
These metadata checks are a cheap freshness cache, not an immutable store or a
new hash on every inventory read.

`/api/library` reports one more `verification` state and two extra fields per asset:

- `pin-only-manual-verification` — the file is present but the installer will never
  touch it, so no receipt can ever mark it verified. Re-hash it outside Studio.
- `installable` (bool) and `install_note` (string or null) — false with a reason when
  the pin is not a `.safetensors` weight, or when it has no curated source URL and its
  file is missing. Both refusals happen before any lease, receipt or `.part` exists, so
  a blocked pin leaves no download state behind. An unsourced pin whose file *is*
  present stays installable: explicit Install verifies it in place without network. Deliberately forged metadata, coarse filesystem
timestamps and unsupported filesystem identity semantics remain limitations.

A failure to write an error receipt must not mask the original exception or leave
the worker gate held. Interrupted/corrupt lock files still require inspection;
there is no unsafe automatic stale-lock cleanup. File contents and receipts are
flushed before publication, but this is not a full power-loss transaction with
directory fsync guarantees on every filesystem. A crash between link and unlink
can leave both names: verify them explicitly rather than starting a blind retry.

## Verification

Run in a development/test environment, **not** the shared ComfyUI Python runtime:

```console
python -m pip install -r tests/requirements-runtime.txt
python -m unittest discover -s tests -p test_backend_safety.py -v
python -m unittest discover -s tests -p test_model_install_safety.py -v
python -m unittest discover -s tests -p test_model_library.py -v
```

This pass ran 64 focused tests on Linux/Python 3.13.5/psutil 7.2.2: 31 backend
fault tests, 28 installer fault tests and five unchanged installer regression
tests. The endpoint test uses a real ephemeral loopback HTTP server. Process
termination/startup tests mock the OS boundary; transfer tests use inert bytes
and simulated HTTP responses. There is no model download, GPU inference or real
ComfyUI shutdown in this evidence.

The existing Ubuntu full-suite/catalog workflow is unchanged except for the
pinned test-only psutil dependency. A path-filtered Windows/Python 3.12 job runs
the focused tests, without duplicating another Ubuntu lane. Windows symlink tests
may explicitly skip when the runner lacks symlink privileges. Hosted results
must be read from the PR; declaring a workflow is not evidence that it passed.
The chat checkout was partial, so the full repository suite and catalog validator
were not claimed locally.

The redirect-policy pass on 12 September 2026 ran 42 focused model-library,
transfer-safety and redirect tests: 41 passed and the Windows directory-symlink
privilege case skipped. The dependency-equipped full suite then ran 482 tests:
473 passed and nine native/symlink cases skipped. Repository validation passed
59 graphs/bindings, 62 pinned assets and 693 tracked paths. Redirect fixtures use
a real ephemeral loopback HTTP server reached through a test-only logical-HTTPS
transport; production policy still refuses loopback addresses. No external model
bytes, credentials or generation jobs were used.

| Fault group | Assertions |
|---|---|
| Queue and HTTP | Missing lists, busy queues, refusal vs timeout, body cap, redirects, no worker launch on unknown state |
| Process safety | Foreign/ambiguous/inaccessible listeners, executed script, changed PID birth time, late manual work, failed startup, retained child and exact readiness ownership |
| Files and receipts | Racing destination, unsupported publication, root changes, same-size/mtime replacement, shared browser mutation, stable hashing, no page-load rehash |
| Transfer and recovery | Exact range, truncated/excess bytes, empty/complete partial, low space, cross-volume copy, two-instance reservation, thread/receipt failure, owner-token preservation |
| Redirect transport | Allowed Hugging Face/Civitai CDN hops, cross-host header stripping, downgrade/credentials/ports/host/address refusal before contact, loops and five-hop bound, partial/receipt preservation |

## Workstation acceptance and remaining work

After review/merge, run the normal existing full checks. With direct ComfyUI
clients idle, explicitly switch Main -> HiDream -> Main and inspect operation/log
records. Verify that an active direct ComfyUI queue and an uncertain Studio job
both refuse switching without altering jobs. Test missing-component diagnostics
in a disposable fixture/configuration, not by deleting working model files.
Exercise interrupted/resumed downloads and cross-volume reuse with small approved
fixtures before a large model. Inspect a retained-startup failure deliberately;
never terminate an unverified PID or remove a lock while its worker may be alive.

For a stale installer lock, first read its PID/asset/token, inspect the actual
process and current transfer, and confirm no installer remains. Preserve the lock
as an incident record before removing it explicitly. Preserve `.part` bytes;
inspect/hash a complete staged file before publishing or moving it. Re-run explicit
Install to verify a pre-existing destination. A failed hash is not permission to
overwrite or delete that destination.

#2 still needs the controlled higher-step same-seed comparison and warning review.
#3's Qwen/character/editor comparisons still require the user's live applications
and creative acceptance. #9's broader authenticated source intake, lineage/terms
metadata and hardware/runtime evidence remain separate work. #10/#22's full
accepted character-pack demonstration is not claimed. `HUMAN_TODO.md` stays
unchanged: subjective art choices were not inferred or checked off.

## Primary references

Reviewed 12 September 2026; implementation also follows the exact in-repo launcher
and H3 file contracts cited above.

- [ComfyUI routes](https://docs.comfy.org/development/comfyui-server/comms_routes):
  queue/history/prompt observation and submission interfaces.
- [Python os.rename](https://docs.python.org/3/library/os.html#os.rename) and
  [os.link](https://docs.python.org/3/library/os.html#os.link): platform differences
  in replacement and hard-link publication.
- [RFC 9110, Content-Range](https://www.rfc-editor.org/rfc/rfc9110.html#section-14.4):
  response range semantics; this installer intentionally accepts only the exact
  pinned remainder rather than all valid HTTP multipart/subrange behaviors.
- [psutil 7.2.2](https://pypi.org/project/psutil/7.2.2/): process/listener inspection,
  exceptions and the test dependency used for this pass.
