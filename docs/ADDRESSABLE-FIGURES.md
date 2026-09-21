# Addressable figure crops

Issue #252 turns marked regions of one immutable Workspace image into ordinary child image assets. It is a local file operation. It does not start ComfyUI, submit a prompt, load a model or modify the parent asset.

## Asset-library editor

Open an active image in **Workspace**, then choose **Split figures**. The editor supports both pointer drawing and exact keyboard entry in integer basis points. Rectangles stay in the numbered list order used for child assets; each row can move earlier or later, be removed, or be restored with **Undo last change**. **Clear rectangles** is also undoable.

The review line states the child count, ordering and non-generating boundary before submission. Non-overlap is required by default and can be relaxed explicitly for artwork whose figures cross panel boundaries. A submitted command is frozen under one request ID. If its response is uncertain, the editor locks geometry and offers only **Check split status** or **Retry exact split**, preventing a new request from accidentally duplicating children.

After a confirmed receipt, the new child buttons open ordinary Workspace assets. Their generation, repair and artistic review remain separate actions.

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

Rectangle coordinates are integer basis points on the displayed source: `0` is the top/left edge and `10000` is the bottom/right edge. This keeps a retained request independent of browser CSS pixels and zoom. Width and height must be positive, every rectangle must stay inside the source, and one command may create at most 32 children. Touching edges are allowed. Overlap is rejected when `require_non_overlapping` is true.

Each normalized edge is projected once to the nearest source-pixel boundary. Adjacent basis-point rectangles therefore share one raster boundary instead of receiving the same pixel. A rectangle that becomes empty at the source resolution is refused rather than expanded into a neighbouring figure.

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

The route is available only through the existing same-origin loopback handler composition. Inputs are strict JSON. It accepts single-frame PNG, JPEG and WebP assets only; ambient Pillow decoders for formats such as BMP or TIFF do not widen that contract. It rejects trashed or changed parents, limits source bytes to 64 MiB, source dimensions to 40 megapixels, and aggregate crop area to 80 megapixels. Media publication uses no-clobber content-addressed files; database failures leave no child rows or success receipt.

## Remaining issue #252 work

The repository now contains the crop/lineage primitive and Asset-library rectangle editor. The remaining acceptance is runtime evidence rather than another speculative code path:

1. split one owner-reviewed real multi-figure sheet;
2. route one resulting child through `anime-detail-fix` or another compatible repair recipe;
3. retain the parent/child hashes, prompt ID and reviewed outcome in `experiments/curated/`.
