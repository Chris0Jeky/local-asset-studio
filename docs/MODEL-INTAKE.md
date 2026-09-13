# Browser model intake: independent copies and recoverable publication

Implementation checkpoint: 13 September 2026. Extends oldest-open workstream #9 and the
now-closed scoped publication issue #140, following merged PRs #142 and #149
(`3acd401e9a3b82152f4f24f8c55cd23e87c10011`). The full #9 provenance, companion-bundle,
authenticated-source and hardware-viability scope remains open; see the [live GitHub reconciliation](reconciliation/2026-09-13-github.md).
Main was inspected at `c26cefcc8f279ca3f7fe365acfabb89071903bbc`; the earlier #2 and #3
live-comparison boundaries remain unchanged. This does not replace ModelLibrary or
complete #9's authenticated source/bundle/hardware work.

## Operator contract

```console
python scripts/intake-downloads.py --dry-run
python scripts/intake-downloads.py --from "C:\AI\reviewed-downloads" --dry-run
python scripts/intake-downloads.py --from "C:\AI\reviewed-downloads"
```

The final command explicitly **copies** recognised candidates. Browser originals are
retained even after success. This deliberately replaces the previous move semantics:
removing a pathname after checking it can remove a newly replaced file, and hard-linking
the original would leave mutable model bytes shared with the browser directory. Cleanup
is a separate owner action after inspecting the destination and its receipt.

Unknown roles are still skipped. `--dest-folder` is an explicit whole-batch override,
not container, model-family or loader certification. Use a directory of reviewed
candidates. `--dry-run` performs metadata inspection only: no copy, lease, receipt,
model directory, network request, node import or generation.

Copies require their full size plus the existing 20 GiB reserve on the destination
volume; free space is checked again while streaming. This costs extra disk space and
I/O compared with a move, but leaves an independent original and a verifiable copy.
No source volume hard-link capability is required: staging and final publication are
both on the destination volume. The destination must support hard links for the
existing no-clobber publisher. Unsupported publication fails visibly with source and
stage retained; there is no destructive rename fallback.

## One shared publication boundary

`app/model_intake.py` uses the existing `ModelLibrary`, `InstallLease`, `file_identity`
and `publish_verified` contracts. It does not download weights, create a GPU queue,
refresh ComfyUI, or alter the pinned installer's source/permission decisions.

```text
header inspection + stat identity
  -> explicit copy action, revalidate identity and observed paths
  -> shared .runtime/downloads/install.lock
  -> persisted intent, unique target-volume .part
  -> bounded streamed copy, source/handle identity checks
  -> rehash staged bytes, persisted prepared receipt
  -> recheck paths/source, existing no-clobber publisher
  -> persisted copied receipt; browser original remains
```

A regular source's identity includes device, inode, size, modification time and the
ctime field from **os.fstat**, consistently obtained through an open descriptor. The
receipt explicitly records `source_identity_api: os.fstat`. Windows/Python 3.12.10 CI
showed that path stat's ctime can be creation time while fstat's is change time; mixing
those APIs falsely rejected an unchanged file. The fix preserves the field and uses
one API, rather than dropping or tolerating changed timestamps. Identity is sampled
around header classification, checked on the copying descriptor, checked after copying
and again before publication. Symlinks and Windows junctions
are rejected before resolving paths away. The checked destination is then canonicalised
to match ModelLibrary, including Windows short-path aliases such as RUNNER~1. Model
names use the existing portable path rules and supported-folder registry. These are observed-path interlocks against
ordinary mistakes and competing writes, not a sandbox against a hostile local process
continually replacing ancestor directories after a check.

The lease serializes cooperating browser-intake and ModelLibrary processes. Old
interrupted lock files are never automatically reaped. The separate HF/Civitai
acquisition scripts are not made lease-aware by this change; do not run them against
the same destination concurrently. No-clobber publication still preserves a competing
destination appearing immediately at the publication call.

## Durable evidence and failure handling

Each copy has an operation journal at
`.runtime/downloads/intake/<operation-id>.json`. This no longer rewrites the acquisition
scripts' shared `receipts.json` list, so intake cannot lose another writer's list entry.
Each journal update uses a uniquely named temporary file, flush + fsync, then replacement
of its own operation record. Prior state and failed temporary writes are retained.
This is tested process-interruption recovery evidence, not a universal sudden-power-loss
or filesystem durability guarantee.

| State | Meaning and next action |
| --- | --- |
| `intent` | Source identity and exact destinations recorded; do not infer a copy exists. |
| `copying` | A partial copy may exist; original is retained. Inspect rather than treating it as installed. |
| `prepared` | Staged bytes were re-read and matched the observed source-stream digest. Publication may or may not have occurred if execution stopped next. |
| `copied` | Publication returned and the final stat identity was recorded. This is not source authentication or runtime compatibility. |
| `needs_inspection` | A caught failure occurred. Keep the source, any stage, target and earlier receipt events; the message and paths identify the attempted operation. |

After interruption, inspect the exact recorded paths, sizes and hashes before any
manual cleanup. A `prepared` journal can coexist with a complete destination when
publication succeeded but the final receipt write failed. Do not repeat the copy or
remove that target: the next intake refuses existing destinations. An abrupt process
exit can retain `install.lock`; confirm the recorded process is no longer performing
work before an explicit operator removes that lock. Resuming a partial copy, adopting
a destination and cleaning up sources are intentionally not automatic operations.

Records retain `verified: false`, `expected_sha256: null`, `runtime_compatible: null`
and `source_cleanup: not-requested`. The digest proves which bytes were observed and
copied; it does not authenticate an author, assert permissions or become a trusted pin.
The existing Models verification badge cannot be satisfied by these browser journals.

## Verification

Local tests use byte-identical actual dependency modules, not a replacement folder
registry: `model_library.py` blob `ce91eddff57af64a9746ca4d968f0d0e722beaa7` and
`download_contracts.py` blob `aa5776ee11a9b218073c0946e5083cef1facaeee`.
The private full checkout was not downloadable in the execution container; these are
focused source tests. Full-repository proof is the PR CI result, reported separately.

On Linux/Python 3.13.5, 50 focused tests ran: 49 passed, one Windows-only junction test
skipped. The 35 new publication cases include a real second-filesystem source, actual
cross-process lease contention, abrupt child-process exit after the prepared receipt,
source replacement/mutation, target appearance, bad staged bytes, disk/copy/receipt
failures, unsupported hard links, preserved shared receipts, symlinks and CLI inertness.
The 15 #142 role tests retain their meaning and now expect independent copies/journals.
A dedicated Python 3.12 Linux/Windows CI lane runs these plus the existing acquisition
helper tests; real Windows results must be read from that run, not inferred locally.

The exact old CLI blob `32c482988c450a487a516eb9a09e20373ee9feb8` was also executed on
synthetic files with a destination inserted immediately before its `shutil.move`:
the competitor was overwritten and the browser source removed. The new fault test
inserts the same competitor at publication and proves both files are preserved.

```console
python -m unittest discover -s tests -p test_model_intake.py -v
python -m unittest discover -s tests -p test_intake_unknown.py -v
python -m unittest discover -s tests -p test_fetch_scripts.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Sources for OS semantics: Python's [move contract](https://docs.python.org/3.12/library/shutil.html#shutil.move)
and [OS file operations](https://docs.python.org/3.12/library/os.html) distinguish rename,
hard-link and flush/fsync behaviour. This implementation reuses the repository's
already-reviewed no-clobber helper instead of assuming `move` is exclusive publication.

No owner's downloads/models were touched, no GPU or native application ran, and no
system configuration changed. HUMAN_TODO choices remain answered and untouched; the
recorded owner-controlled Windows restart is not performed or authorized by this work.

### Windows compatibility checks

The first dedicated Windows run caught an actual stat/fstat ctime mismatch, not a
failed model or weak assertion. Diagnostic run 34731218739 recorded identical device,
inode, size and mtime with ctime values 1789263790055008600 (path) and
1789263790057019300 (descriptor). The source API is now consistently os.fstat. The
[CPython 3.12.10 file-information implementation](https://github.com/python/cpython/blob/v3.12.10/Python/fileutils.c)
reads both CreationTime and ChangeTime; the pre-fix code should not compare the different
public API projections as if they meant the same thing.

At commit `6f4ad2dbc6c76465f8fc07ca96f46e787742ae1c`, all 35 publication tests (one
cross-device skip), three new identity tests and the 15 role tests passed on Windows,
including real junction rejection and the restored-mtime mutation case. The same run
then exposed the legacy helper's required canonical destination: RUNNER~1 must resolve
to the same path ModelLibrary uses. Canonicalisation now happens only **after** lexical
link/junction rejection; the existing path-safety tests remain intact. A fourth identity
test exercises the unresolved tempfile root through actual copying.

Current focused local suite: **54 tests, 53 passed / one Windows-only skip**. Four are
new identity/canonical-path regressions in addition to the 35 publication cases. The
latest hosted run, linked on the PR, is the authority for the final Windows and full
repository results. The earlier failed runs are retained rather than hidden.
