# Addressable figure crops

The first slice of issue #252 turns marked regions of one immutable Workspace image into ordinary child image assets. It is a local file operation. It does not start ComfyUI, submit a prompt, load a model or modify the parent asset.

## Endpoint

```text
POST /api/assets/split-figures
Content-Type: application/json
Origin: http://127.0.0.1:8191
Host: 127.0.0.1:8191
```

```json
{
  "workspace_id": "32-lowercase-hex-characters",
  "request_id": "stable-client-request-id",
  "asset_id": "parent-workspace-asset-id",
  "parent_sha256": "64-lowercase-hex-characters",
  "rectangles": [
    {"x": 500, "y": 800, "width": 3200, "height": 8400}
  ],
  "require_non_overlapping": true
}
```

Rectangle coordinates are integer basis points on the displayed source: `0` is the top/left edge and `10000` is the bottom/right edge. This keeps a retained draft independent of browser CSS pixels and zoom. Width and height must be positive, every rectangle must stay inside the source, and one command may create at most 32 children. Touching edges are allowed. Overlap is rejected when `require_non_overlapping` is true.

## Durable identity and retries

The command uses the existing Workspace identity and asset-command journal:

- `workspace_id` prevents a retained command from applying to a replaced Workspace database.
- `parent_sha256` binds the request to the exact immutable parent bytes.
- `request_id` is idempotent. Replaying the same JSON returns the original receipt and creates no extra assets. Reusing the ID for changed rectangles is rejected.
- The child rows and receipt commit in one SQLite transaction. A missing receipt therefore does not authorize an automatic retry with a new request ID.
- A client that loses the response can inspect the original command with:

```text
GET /api/assets/commands/<request_id>?workspace_id=<workspace_id>
```

## Child assets and provenance

Each crop is encoded as a PNG and published through the existing content-addressed Workspace media store. The resulting records behave like other image assets: they appear in the library, can be collected or reviewed, can be exported, and can enter the existing **Continue with this** flow.

Every child records:

- direct lineage to the selected parent asset;
- the parent content hash;
- the original basis-point rectangle;
- the derived source-pixel rectangle and source dimensions;
- `operation: figure-crop` and `generation_submitted: false`.

The parent file, title, collections, review state and metadata revision are unchanged.

## Safety and resource bounds

The route is available only through the existing same-origin loopback handler composition. Inputs are strict JSON. It accepts still image assets only, rejects trashed or changed parents, limits source bytes to 64 MiB, source dimensions to 40 megapixels, and aggregate crop area to 80 megapixels. Media publication uses no-clobber content-addressed files; database failures leave no child rows or success receipt.

## Remaining issue #252 work

This slice intentionally does not claim the full issue complete. Remaining acceptance includes:

1. an Asset-library rectangle editor with keyboard-accessible ordering, removal and clear undo/review behavior;
2. applying `anime-detail-fix` or another compatible repair route to one child through the existing continuation flow;
3. an owner-reviewed real sheet proving that useful figures can be isolated and repaired without changing the parent.
