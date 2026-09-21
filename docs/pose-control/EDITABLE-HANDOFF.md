# Editable pose handoff

`POST /api/pose/render` produces two deliberately different artifacts:

1. a rendered RGB skeleton PNG that can occupy the pose image slot of a registered recipe;
2. the exact editable `studio.pose-artifact/v1` document from which that PNG was rendered.

The PNG is a model input. The JSON is the correction record. Keeping only the PNG loses unknown joints, manual-vs-estimated provenance, the parent identity and future editability.

## Receipt

The existing render receipt keeps its image fields and now includes:

```json
{
  "artifact_id": "<64 lowercase hex>",
  "artifact": {
    "id": "<same artifact_id>",
    "schema": "studio.pose-artifact/v1",
    "file": "<artifact_id>.pose.json",
    "sha256": "<hash of exact stored JSON bytes>",
    "bytes": 4096,
    "url": "/api/pose/artifacts/<artifact_id>",
    "authority": "none",
    "review": "unreviewed"
  },
  "generation_submitted": false
}
```

`artifact.id` is the pose document's semantic content identity. `artifact.sha256` binds the exact canonical file bytes, including the final newline. They are intentionally separate checks.

## Storage and retrieval

Editable documents live under the configured experiments root:

```text
experiments/pose-artifacts/<artifact-id>.pose.json
```

Publication is exclusive and content addressed:

- validate the complete artifact first;
- write canonical bytes to a private temporary file;
- flush and link the temporary file into its final name without overwriting;
- when the name already exists, require its bytes, schema and embedded identity to match exactly;
- remove the temporary file in every outcome;
- only then upload the rendered PNG and return the paired receipt.

A later PNG upload failure can leave a harmless deduplicated JSON document, but it cannot return a false paired receipt. A changed, noncanonical, oversized, symlinked or identity-mismatched artifact blocks another upload.

`GET /api/pose/artifacts/<artifact-id>` is available only through the existing loopback Host guard. The handler rereads and validates the complete bounded document before returning `application/json`; it does not trust the filename alone.

## Authority boundary

The sidecar remains:

- `authority: none`;
- `review: unreviewed`;
- non-executable;
- independent of route qualification;
- independent of model, node and runtime availability;
- unable to reserve allowance, create a job or submit generation.

The endpoint does not infer anatomy quality, artistic success, consent, source ownership or route compatibility.

## Deliberate remaining work

This slice makes the exact editable artifact durable and headless-agent retrievable. It does **not** yet:

- reopen the sidecar automatically in the browser editor;
- preserve a sequence of competing Workspace revisions;
- merge simultaneous browser or agent edits;
- import detector keypoints with a confidence overlay;
- qualify any neural pose route;
- garbage-collect artifacts no longer referenced by uploads or saved work.

Those remain separate #444 and #445 slices so the storage contract can be reviewed without coupling it to UI history, collaboration or execution.
