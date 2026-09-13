# Backend schema capture and offline replay

This extends `scripts/validate-live.py`; there is still one schema parser and one
`game_asset_pipeline.graph_check` implementation. It does not start Studio,
import ComfyUI/custom-node Python, load models, switch backends or submit prompts.
A capture requests `/object_info` exactly once from an explicitly named numeric
loopback URL, with proxies and redirects disabled and no automatic retry.

## Why this remains separate from issue #97 acceptance

At the inspected main `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3`, PR #156 had
already corrected the union/dynamic/socketless checks and made all catalog rows
the default. The owner's [13 September 20:48 UTC report](https://github.com/Chris0Jeky/local-asset-studio/issues/97#issuecomment-5656050331)
recorded 59 of 60 primary-backend graphs passing; AniFox's missing loader entry
failed. HiDream's two and H3's four graphs still lacked matching installed-schema
validation. The actual schema/receipts remain on the workstation, not in Git.

This change makes that evidence reproducible and backend-labelled. It does not
turn reduced fixtures into an installed schema, repair a missing model or fill
those remaining six checks. Do not retry the parked AniFox transfer or failed Wan
animation to prove a schema-capture feature.

## Commands for the configured workstation

Create a local evidence directory first. Capture only an already-listening,
explicitly selected backend; the command never launches one for you:

```console
mkdir .runtime/schema-evidence
python scripts/validate-live.py --backend primary --comfy-url http://127.0.0.1:8188 --capture-schema .runtime/schema-evidence/primary-20260913.json --json
python scripts/validate-live.py --schema-snapshot .runtime/schema-evidence/primary-20260913.json --json
```

For a configured custom primary port, use its actual URL. HiDream and H3 capture
commands use their explicitly inspected ports (normally 8192 and 8194) and
`--backend hidream` or `--backend h3`. Capture them only when an operator has
separately made those runtimes available; do not combine this command with an
implicit switch, installation or generation. Save the checkout's `git rev-parse
HEAD` alongside the capture when handing evidence to another agent.

`--schema-snapshot` performs no network access. Its recorded backend is selected
automatically; an explicit different `--backend` is rejected. Capture/replay
cannot be combined with `--preset` or `--collection` to disguise a subset as
complete backend coverage. Existing `--object-info` raw-file inspection and
unfiltered live validation remain available with their original one-schema
scope; they are not retroactively authenticated or relabelled.

Exit status is **0** for all selected graphs passing, **1** for a complete report
containing failed graph checks, and **2** for an input, integrity, stale-evidence,
transport or publication error. A status-1 capture is useful evidence and is
retained, including missing/unparseable graphs with a null graph hash. It is not
a failed download to retry automatically.

## Snapshot format and trust

Version 1 contains the exact response bytes as base64, their SHA-256, capture
UTC timestamp and endpoint, declared backend ID, full-catalog canonical digest,
and each selected preset's path/backend/canonical graph digest. The original
per-preset report is historical context. An envelope digest detects accidental
changes; **a person who can rewrite the file can also recalculate that digest**.
Neither digest nor backend label authenticates a process, creator or licence.
`backend_identity_verified` and `inference_verified` remain false.

Replay reruns the shared checker against the captured schema and current
repository graphs. It does not trust stored success counts. It requires the
same canonical catalog and exact selected graph coverage/content; changes are
reported as stale, not a current pass. JSON formatting changes alone do not
alter canonical catalog/graph identities. The schema digest, unlike those
canonical digests, identifies the exact original HTTP bytes. Retain the recorded
checkout to replay historical evidence; capture again explicitly to validate a
changed catalog. No file paths from a capture are used as execution instructions.

A corpus is one independently captured file per backend. There is no combined
"all installed backends passed" badge from a single primary snapshot. Different
backend captures are separate observations, not an atomic workstation snapshot.
Node/schema compatibility also does not establish native custom validation,
model identity/availability beyond enumerated evidence, memory fit, execution,
art acceptance or rights.

## Bounds and publication

The existing 32 MiB raw schema, 4 MiB catalog/per-graph input and 2,048-preset
limits remain. Capture input/output is bounded to 64 MiB. Both JSON layers reject
duplicate keys and non-finite values; replay verifies raw schema and envelope
digests before checking graphs.

The destination's parent must exist. Existing files, directories and symlinks
are refused before the GET. Publication writes a uniquely owned sibling staging
file, flushes/fsyncs it, reads it back, and hard-links it into place without
replacing a concurrent writer. Filesystems without same-directory hard-link
support fail explicitly; there is no unsafe replacement fallback. A failure
retains its staging path for inspection. A completed file is never overwritten.
This is file flush/no-clobber evidence, not a universal power-loss or directory
metadata durability guarantee.

Schema captures may contain private local model names. Keep them in `.runtime/`
or another external evidence folder. This PR commits only synthetic fixtures
and code; it does not upload any workstation schema or model inventory.

## Verification

```console
python -m unittest discover -s tests -p test_schema_capture.py -v
python -m unittest discover -s tests -p test_validate_live.py -v
python -m unittest discover -s tests -p test_graph_validation.py -v
python -m unittest discover -s tests -p test_graph_catalog_validation.py -v
python scripts/validate-repo.py
```

The original 22 capture tests exercise exact one-GET bytes, offline subprocess replay,
retained failed/missing graphs, stale catalog/graph bindings, relabelling/subset
refusal, malformed/oversized input, rehashed-but-inconsistent manifests,
non-authoritative historical results, symlinks, write failure and two real
concurrent publishers. The existing 15 validator tests still pass. The initial
17-case feature suite produced 11 expected failures before implementation; the
remaining guard cases already failed closed through unknown-argument handling.
The existing Linux/Windows graph-validation workflow runs the new suite.

Primary references: [ComfyUI route contract](https://docs.comfy.org/development/comfyui-server/comms_routes)
and [Python filesystem operations](https://docs.python.org/3/library/os.html#os.fsync).
The distinction between `/object_info` inspection and `/prompt` submission is
why this collector deliberately does not use native prompt validation as a probe.

## Review follow-up: complete version-1 metadata

Replay also requires an actual UTC capture timestamp and numeric-loopback
`object_info` source, a complete typed historical report, matching duplicate
backend/schema/binding identities, static-only verification fields, and consistent
coverage and historical row counts. Rehashing an incomplete manifest does not
make it valid. This is structural integrity, not authentication. A coherent
historical failure is still revalidated rather than used as the current verdict.

Six additional test methods exercise missing, mistyped and contradictory metadata
while verifying no network call or snapshot modification. Their negative cases
failed before this correction; all 28 capture methods pass afterwards. The
original historical-count test now uses a coherent historical failed row, not
internally impossible counts, to prove that replay recomputes the current result.
