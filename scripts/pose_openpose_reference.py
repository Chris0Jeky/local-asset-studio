"""Re-render pose guides with the installed comfyui_controlnet_aux drawing code and compare with pose_raster.

Run with ComfyUI's embedded Python (it has cv2 and numpy); nothing is submitted to ComfyUI and torch is not imported:
the `draw_bodypose` function is read from the pinned util.py by source and executed on its own.

    C:/AI/ComfyUI_windows_portable/python_embeded/python.exe scripts/pose_openpose_reference.py \
        --aux C:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/comfyui_controlnet_aux --out tests/fixtures/pose-openpose

It writes one `<case>.aux.png` per case (the controlnet_aux drawing, xinsr_stick_scaling=True), `cases.json` (the
keypoints) and `report.json` (pixel agreement with studio.coco18-openpose-xinsir/v1, the ellipse2Poly replica check
and the cv2.circle radius-4 dot rows), and exits non-zero when agreement falls below --min-agreement.
"""
import argparse
import ast
import hashlib
import io
import json
import math
import random
import sys
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from studio_workflow import pose_artifact, pose_raster  # noqa: E402

STANDING = [(.50, .12), (.50, .19), (.42, .20), (.39, .31), (.37, .42), (.58, .20), (.61, .31), (.63, .42), (.45, .47),
            (.44, .66), (.44, .86), (.55, .47), (.56, .66), (.56, .86), (.475, .108), (.525, .108), (.45, .12), (.55, .12)]
# app/static/pose-editor-core.js BENT: the bent-forward research figure (right ear unknown).
BENT = [(.23, .31), (.34, .17), (.30, .14), (.27, .27), (.31, .31), (.42, .11), (.55, .05), (.44, .30), (.62, .30),
        (.49, .58), (.20, .84), (.81, .31), (.63, .62), (.68, .85), (.25, .28), (.21, .30), None, (.30, .23)]
CASES = (('standing-832x1216', STANDING, 832, 1216), ('bent-832x1216', BENT, 832, 1216),
         ('standing-1024x1536', STANDING, 1024, 1536), ('bent-448x448', BENT, 448, 448))


def load_draw_bodypose(util_path):
    """Execute the installed draw_bodypose by source, so its heavy module imports (torch) are never loaded."""
    source = util_path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'draw_bodypose')
    module = ast.Module(body=[node], type_ignores=[])
    Keypoint = namedtuple('Keypoint', 'x y score id', defaults=(1.0, -1))
    scope = {'np': np, 'cv2': cv2, 'math': math, 'List': list, 'Keypoint': Keypoint}
    exec(compile(module, str(util_path), 'exec'), scope)  # noqa: S102 - pinned local file, hash checked by the caller
    return scope['draw_bodypose'], Keypoint


def artifact(points, width, height):
    """The same manual artifact the Studio's POST /api/pose/render builds."""
    blank = pose_artifact.canonical({'version': 1.3, 'canvas_width': width, 'canvas_height': height,
                                     'people': [{'pose_keypoints_2d': [0] * 54}]})
    empty = pose_artifact.import_openpose(blank, width=width, height=height, coordinate_space='pixels')
    edits = {name: [round(p[0] * width, 2), round(p[1] * height, 2)] for name, p in zip(pose_artifact.JOINTS, points) if p}
    return pose_artifact.validate(pose_artifact.revise(empty, empty['id'], edits))


def aux_render(draw_bodypose, Keypoint, art):
    exported = pose_artifact.export_openpose(art)
    width, height = exported['canvas_width'], exported['canvas_height']
    triples = exported['people'][0]['pose_keypoints_2d']
    keypoints = [Keypoint(triples[i] / width, triples[i + 1] / height) if triples[i + 2] else None for i in range(0, 54, 3)]
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    return draw_bodypose(canvas, keypoints, xinsr_stick_scaling=True)


def ellipse_check(samples=4000, seed=445):
    rng = random.Random(seed); mismatches = 0
    for _ in range(samples):
        cx, cy, a, b, angle = rng.randint(0, 2000), rng.randint(0, 2000), rng.randint(0, 900), rng.randint(1, 30), rng.randint(-180, 180)
        expected = [tuple(int(v) for v in p) for p in cv2.ellipse2Poly((cx, cy), (a, b), angle, 0, 360, 1)]
        if expected != pose_raster._ellipse_polygon(cx, cy, a, b, angle): mismatches += 1
    return {'samples': samples, 'seed': seed, 'mismatches': mismatches}


def dot_rows():
    canvas = np.zeros((21, 21), dtype=np.uint8)
    cv2.circle(canvas, (10, 10), pose_raster.OPENPOSE_JOINT_RADIUS, 255, thickness=-1)
    rows = []
    for y in range(21):
        xs = np.nonzero(canvas[y])[0]
        if len(xs): rows.append(int(10 - xs.min()))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--aux', type=Path, required=True, help='the comfyui_controlnet_aux folder beside ComfyUI')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--min-agreement', type=float, default=.999)
    args = parser.parse_args()
    util_path = args.aux / pose_raster.OPENPOSE_REFERENCE['file']
    digest = hashlib.sha256(util_path.read_bytes()).hexdigest()
    if digest != pose_raster.OPENPOSE_REFERENCE['file_sha256']:
        raise SystemExit('controlnet_aux util.py is not the pinned file: ' + digest)
    draw_bodypose, Keypoint = load_draw_bodypose(util_path)
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'reference': pose_raster.OPENPOSE_REFERENCE, 'aux_util_sha256': digest, 'cv2': cv2.__version__,
              'numpy': np.__version__, 'renderer_id': pose_raster.OPENPOSE_RENDERER,
              'ellipse2poly_replica': ellipse_check(), 'cv2_circle_r4_rows': dot_rows(),
              'studio_dot_rows': list(pose_raster._OPENPOSE_DOT), 'cases': []}
    cases = {}
    worst = 1.0
    for name, points, width, height in CASES:
        art = artifact(points, width, height)
        cases[name] = {'width': width, 'height': height, 'artifact': art}
        aux = aux_render(draw_bodypose, Keypoint, art)
        Image.fromarray(aux).save(args.out / (name + '.aux.png'), optimize=True)
        with Image.open(io.BytesIO(pose_raster.render_png(art, renderer=pose_raster.OPENPOSE_RENDERER))) as image:
            ours = np.asarray(image.convert('RGB'))
        differs = np.any(aux != ours, axis=2)
        drawn = np.any(aux != 0, axis=2) | np.any(ours != 0, axis=2)
        agreement = 1 - differs.sum() / differs.size
        worst = min(worst, agreement)
        # A difference is an outline pixel when the aux drawing changes colour inside its 3x3 neighbourhood.
        padded = np.pad(aux, ((1, 1), (1, 1), (0, 0)), mode='edge'); boundary = np.zeros(differs.shape, bool)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                shifted = padded[1 + dy:1 + dy + height, 1 + dx:1 + dx + width]
                boundary |= np.any(shifted != aux, axis=2)
        interior = int((differs & ~boundary).sum())
        if interior: worst = 0.0
        colours = lambda a: sorted({tuple(int(v) for v in p) for p in a.reshape(-1, 3)})  # noqa: E731
        report['cases'].append({'case': name, 'canvas': [width, height],
                                'stick_half_width': pose_raster.OPENPOSE_STICK * pose_raster.openpose_stick_scale(width, height),
                                'pixels_differing': int(differs.sum()), 'drawn_pixels': int(drawn.sum()),
                                'agreement_all_pixels': round(float(agreement), 6),
                                'agreement_drawn_pixels': round(float(1 - differs.sum() / max(1, drawn.sum())), 6),
                                'differing_pixels_off_outlines': interior,
                                'same_colour_set': colours(aux) == colours(ours),
                                'aux_png_sha256': hashlib.sha256((args.out / (name + '.aux.png')).read_bytes()).hexdigest()})
    (args.out / 'cases.json').write_text(json.dumps(cases, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    (args.out / 'report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, indent=1))
    if report['ellipse2poly_replica']['mismatches'] or report['cv2_circle_r4_rows'] != report['studio_dot_rows'] or worst < args.min_agreement:
        raise SystemExit('the Studio OpenPose renderer does not reproduce the installed controlnet_aux drawing')


if __name__ == '__main__':
    main()
