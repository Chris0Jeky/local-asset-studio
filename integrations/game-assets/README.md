# Application adapter implementation order

These are integration contracts, not live installed adapters. The tested functions are the offline planner, graph factory/checker, PNG atlas and OpenRaster writer.

1. **Reference image adapter:** bind uploaded filenames to Qwen graph slots 4/16/17 and description to encoder 6; preserve conditioning in encoder 7. Validate the installed schema and integrate with the existing Studio submission/history behavior. Add visual-node workflows separately.
2. **Krita adapter:** begin with opening the supplied ORA fixture and checking layer names/composite; save a native KRA. Add a narrow versioned plugin or reviewed bridge for named-layer/mask/animation operations and canvas readback. Test unsaved-document recovery, not just the happy path.
3. **Blender adapter:** reuse Lanternkeeper, then standardize scene/rig/render/export manifests. A proxy camera/rig should produce exact pose/depth/normal inputs for generative stages. Save before mutation and return structured scene facts with renders.
4. **Godot sprite adapter:** import atlas texture first, create one SpriteFrames animation per clip, use AtlasTexture regions, preserve loop policy and convert milliseconds to relative durations. Apply common anchor via the AnimatedSprite2D node rather than independently trimming frames. The example durations 120/80/120/160ms must produce a 480ms cycle at playing speed 1.
5. **3D engine adapter:** run an installed pinned Khronos glTF validator, import the file and exercise named clips/materials. Retargeting, root motion and collision remain engine-specific. Unity/Unreal adapters follow their own installed-version APIs; do not copy Godot assumptions.

Recommended wire format for future adapters:

```json
{
  "schema_version": 1,
  "operation": "inspect_document",
  "job_id": "asset-job-001",
  "inputs": {"document_path": "approved/source.kra"},
  "output_contract": {"report": "reports/layers.json", "preview": "reports/canvas.png"}
}
```

The trusted adapter must validate operation IDs, root-relative paths and input types, and reject unknown operations. It should return a stable operation ID before long work and save results atomically. It must not evaluate arbitrary text fields as Python or shell code. Receipt integrity and reviewer authentication are different concerns.

Sources and caveats for community Krita/Blender/OpenToonz bridges are in `research/game-assets/sources.json`. No matching runtime plugin was found through this chat's app directory search; those local adapters have not been installed or exercised here.
