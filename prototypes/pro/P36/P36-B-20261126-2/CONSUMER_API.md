# P36 offline handoff verifier

`handoff_verifier.py` verifies bundles emitted by the current run's `admission.export_verified_bundle`. It reads local evidence and produces a hashed report. It performs no source writes, network calls, generation, dispatch, cleanup, engine import or native promotion.

```python
verify_handoff(
    bundle,
    *, experiments=None, ledger_path=None,
    require_current=False, allow_synthetic=False, expected_pack_id=None,
)
```

## What a pass means

An offline pass means copied bytes, supported schemas, the complete selected family, semantic declarations, captured authority declarations and completion metadata are internally consistent. The report always states `native_import_allowed=false`, `native_import_performed=false`, `owner_authenticated=false`, `acceptance_inferred=false`, `production_promoted=false`, `perceptual_identity_verified=false`, and `generation_submitted=false`.

Synthetic bundles require `allow_synthetic=True`. This permits test integrity checks only. A synthetic family cannot become production or native evidence through this option. A production family still passes the original production-specific receipt/media checks and the semantic fixture-provenance veto.

The returned schema is `las.p36-handoff-verification/1`. `passed` summarizes the requested checks; `integrity_verified` separately records successful local integrity checking. A late destination change clears it; a source-only acceptance withdrawal can retain the successful local integrity fact while refusing the current check. `current_authority_checked` and `current_authority_matches` state whether an explicit live comparison occurred and matched. `report_sha256` hashes the report before that field is added. Input fingerprints, copied artifact count and byte total are retained. Malformed or unsupported evidence becomes a structured failed report.

Hashes are not signatures. A fully coherent edit to descriptive metadata and its manifest projection can pass offline verification after recomputing the unkeyed hashes. A passing test explicitly demonstrates this boundary while owner authentication and import authority remain false. The verifier cannot discover unrecorded history or authenticate annotations, human judgments, licence declarations, or the source of an entirely fabricated but consistent bundle.

## Checks

- Require `READY.json` and every bound input sidecar. Read bounded JSON with duplicate-key rejection and stable reads; reject links and unsafe paths.
- Require supported draft schemas, strict boolean claims and exact generated fields. Reconstruct the complete admission report rather than accepting its stored `passed` flag.
- Preserve the exact bound concept, family heads, artifact IDs, hashes, complete licence/provenance facts, annotation inventory and semantic policy. Freshly run the prior family/numeric gates and the semantic scorer against copied media.
- Check captured card/canon, asset, acceptance, job and ledger declarations against the explicit binding. A copied acceptance row from another asset fails even after all outer hashes are recomputed. The captured asset ID must equal the shipped Workspace derivation for its job ID and output index. Captured ledger rows must share a source scope and contain no unresolved attempt.
- Rebuild the guarded manifest from the copied store, family and character metadata, then require exact manifest equality after the exporter-added sidecar/admission fields. Validate pack v1 through the guarded builder and check every recursively named `file` value is a declared file key, including open UE metadata.
- Stream each declared file with 1 MiB buffers, at most its declared size plus one byte. Bounds are 384 files, 8 GiB per file and 64 GiB per bundle. Reuse the prior bounded image/pixel verification and existing format-envelope checks; no geometry, skeleton, materials or native compatibility is decoded or qualified.
- Compare the canonical hashes of all bound sidecars and reconstruct `READY`. `PARTIAL.json` and `READY.pending.json` are optional retained markers; if present they must match expected content, and pending bytes must equal READY bytes. An unrelated `FAILED.json` is never used as authority.
- Compare contained-file stat observations before and after checks, including after an optional live capture. These detect ordinary concurrent changes without claiming an atomic transaction.

## Current authority option

`require_current=True` requires both caller-supplied `experiments` and `ledger_path`. The verifier never obtains these paths from the bundle. Supplying either path without the flag is refused as ambiguous.

The explicit paths must match the original admission's source-root and ledger-path fingerprints. It freshly calls the current Studio admission API using those roots and the copied asset store, and requires the complete source capture to match the retained admission. A copied bundle naturally has a different binary asset-root path: comparison projects **only** `input_fingerprints.asset_root_sha256` back to its opaque retained value before resealing. Family, binding, concept, policies, annotations, live authority, ledger scope/evidence and all other fingerprints must match exactly.

Ledger observations are source-root bound. Offline verification checks their internal identities and scope declarations; it cannot reobserve their original job state. The live option uses the original explicit source context and revalidates resolved as well as unresolved attempts through the current ledger API. A second empty ledger at another path cannot substitute merely because its rows look the same.

If an acceptance is withdrawn after export, offline integrity can still pass because it has no current database observation. The live option refuses. Neither outcome grants native authority: a future staged consumer must rehash the actual bytes and revalidate current authority at its own mutation boundary, then separately implement native checks, transactional promotion and rollback.

## CLI

```sh
python prototypes/pro/P36/P36-B-20261126-2/handoff_verifier.py verify \
  --bundle "$BUNDLE" --allow-synthetic

python prototypes/pro/P36/P36-B-20261126-2/handoff_verifier.py verify \
  --bundle "$BUNDLE" --allow-synthetic --require-current \
  --experiments "$EXPERIMENTS" --ledger "$LEDGER"
```

Optional `--expected-pack-id` constrains the character ID. JSON goes to stdout; exit status is 0 on pass and 2 on refusal. The CLI creates no report file automatically.

## Observed challenge outcomes

The focused suite uses one actual exporter-produced bundle over real SQLite Workspace/job files and synthetic swatch/triangle media, copied independently for each mutation. It contains **32 passing test methods, zero skips**, with captured execution taking **12.855 seconds**. Across those methods, **34/34 authored refusal cases were refused**, alongside six control methods. These are authored software cases, not a perceptual accuracy benchmark or production asset review.

| Challenge | Observed result |
| --- | --- |
| Synthetic bundle without explicit test permission | 1/1 refused. |
| Missing explicit current context | 3/3 argument combinations refused. |
| Wrong ledger path despite another empty ledger | 1/1 refused. |
| Acceptance withdrawn after export | Offline integrity passed; 1/1 requested live check refused. |
| Changed copied bytes; rehashed metadata mismatch; rehashed semantic policy change; one semantic side swap | 4/4 cases refused. |
| Copied acceptance row; invented perceptual/owner claims; extra admission claim | 3/3 rehashed cases refused. |
| Changed captured output index with unchanged asset ID | 1/1 rehashed case refused. |
| READY schema, integer substituted for boolean, direct-import claim, native-execution claim | 4/4 cases refused. |
| Promoted/joined manifest; removed provenance; resealed reused-content licence conflict; synthetic-to-production relabel | 4/4 cases refused. |
| Missing READY or missing binding | 2/2 cases refused. |
| Duplicate JSON keys; linked sidecar; linked asset; traversal path | 4/4 cases refused. |
| Wrong expected character ID; changed pending marker; changed partial marker | 3/3 cases refused. |
| Non-string nested file reference; retained attempts with mixed source roots | 2/2 cases refused after concrete red regressions. |
| Destination changed during the live check | 1/1 refused, with `integrity_verified=false`. |

Valid controls include unchanged offline verification, unchanged explicit live verification, rehashing unchanged evidence, unrelated retained failure notes, the CLI, and the explicit coherent-descriptive-edit/authentication limit. Initial absent-module tests failed before implementation. Later, two newly exposed consistency cases failed before their fixes while both rehash controls passed. Independent review found the changed-output-index association, reproduced before the fix. A final reporting regression proved that late destination changes must clear the integrity flag; source-only withdrawal retains that flag while refusing live authority. The aggregate reproducible proof reruns these cases; observed environment and command results are recorded in `VERIFICATION.md`.

The implementation intentionally stays within this prototype run. It is an offline admission adapter candidate, not a modification to the inspected Lumenfold native importer.
