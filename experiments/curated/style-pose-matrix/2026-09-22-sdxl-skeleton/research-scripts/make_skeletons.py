"""Draw the two research skeletons with the Studio's own pose-editor renderers (22 September 2026, #761/#445).

Each figure goes through app/pose_guide.artifact (the validation POST /api/pose/render runs) and
studio_workflow.pose_raster.render_png in both modes: `studio.coco18-openpose-xinsir/v1` (the controlnet_aux drawing
Xinsir's OpenPose ControlNet was trained on) and `studio.coco18-lines/v1` (the thin-line Klein guide), so the renderer
comparison uses identical joints. Run from the repository root; writes the PNGs and skeletons.json next to this folder.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'app'))
import pose_guide  # noqa: E402
from studio_workflow import pose_raster  # noqa: E402

OUT = Path(__file__).resolve().parents[1]
W, H = 832, 1216
# COCO-18 fractions. Action: right arm raised overhead, left hand on the hip, left knee raised, standing on the right leg
# (the figure faces the viewer, so its right side is on the image's left).
ACTION = [(.50, .13), (.50, .21), (.42, .22), (.34, .14), (.36, .04), (.58, .22), (.68, .32), (.58, .42), (.45, .49),
          (.44, .68), (.44, .88), (.55, .49), (.64, .60), (.58, .76), (.48, .115), (.52, .115), (.46, .125), (.54, .125)]
# app/static/pose-editor-core.js BENT: the editor's "Bent forward, looking back" starting figure (right ear unknown).
BENT = [(.23, .31), (.34, .17), (.30, .14), (.27, .27), (.31, .31), (.42, .11), (.55, .05), (.44, .30), (.62, .30),
        (.49, .58), (.20, .84), (.81, .31), (.63, .62), (.68, .85), (.25, .28), (.21, .30), None, (.30, .23)]
MODES = {'openpose': pose_raster.OPENPOSE_RENDERER, 'lines': pose_raster.RENDERER}


def main():
    record = {'canvas': [W, H], 'renderers': {k: {'id': v, 'sha256': pose_raster.renderer_sha256(v)} for k, v in MODES.items()},
              'skeletons': {}}
    for name, points in (('action', ACTION), ('bent', BENT)):
        payload = {'width': W, 'height': H, 'keypoints': [[round(x * W, 2), round(y * H, 2)] if p else None
                                                          for p in points for x, y in [p or (0, 0)]]}
        art = pose_guide.artifact(payload)
        entry = {'keypoints': payload['keypoints'], 'artifact_id': art['id'], 'files': {}}
        for mode, renderer in MODES.items():
            data = pose_raster.render_png(art, renderer=renderer)
            path = OUT / f'skeleton-{name}.{mode}.png'; path.write_bytes(data)
            entry['files'][mode] = {'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        record['skeletons'][name] = entry
    (OUT / 'research-scripts/skeletons.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(record, indent=1))


if __name__ == '__main__':
    main()
