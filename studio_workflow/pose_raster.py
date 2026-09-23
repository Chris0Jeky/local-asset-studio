"""COCO-18 guide rasters.

`studio.coco18-lines/v1` is the thin-line guide the FLUX.2 Klein skeleton recipe was proved with; it is not an
upstream ControlNet renderer clone and its bytes must not change. `studio.coco18-openpose-xinsir/v1` redraws the same
joints the way comfyui_controlnet_aux draws a body for Xinsir's SDXL OpenPose ControlNet (#445 item 3): limb order and
per-limb colours at 60 %, filled ellipse limbs whose width scales with the canvas, radius-4 joint dots drawn last.
"""
import hashlib
import io
import json
import math
import struct
import zlib

import PIL
from PIL import Image, ImageDraw

from .pose_artifact import export_openpose

RENDERER = 'studio.coco18-lines/v1'
RENDERER_IMPLEMENTATION = 'studio.coco18-lines.py/v1'
OPENPOSE_RENDERER = 'studio.coco18-openpose-xinsir/v1'
OPENPOSE_IMPLEMENTATION = 'studio.coco18-openpose-xinsir.py/v1'
RENDERERS = (RENDERER, OPENPOSE_RENDERER)
# The drawing this mode reproduces, pinned to the copy installed beside ComfyUI on 22 September 2026 (the package has no
# own Git checkout there; pyproject.toml reads 1.1.5). scripts/pose_openpose_reference.py re-renders with that exact file.
OPENPOSE_REFERENCE = {
    'package': 'comfyui_controlnet_aux', 'version': '1.1.5',
    'file': 'src/custom_controlnet_aux/open_pose/util.py',
    'file_sha256': '763d2680ca67e13bd373153e65cfb098a168be4da5d3118c6f9ffe16c94ac89a',
    'function': 'draw_bodypose', 'xinsr_stick_scaling': True,
}
PNG_ENCODER_CONTRACT = 'pillow-png-optimize-false-default-compression/v1'
COLORS = ((255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
          (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
          (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
          (255, 0, 255), (255, 0, 170), (255, 0, 85))
LIMBS = ((1, 2), (2, 3), (3, 4), (1, 5), (5, 6), (6, 7), (1, 8), (8, 9),
         (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17))
# controlnet_aux limbSeq, 0-based: the same seventeen pairs in its drawing order; limb i takes COLORS[i] at 60 %.
OPENPOSE_LIMBS = ((1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9),
                  (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17))
OPENPOSE_STICK = 4          # half-width before Xinsir scaling
OPENPOSE_JOINT_RADIUS = 4   # joint dots are not scaled
# cv2.circle(radius 4, filled) as row half-widths for dy = -4..4, read off OpenCV 5.0.0 by the reference script.
_OPENPOSE_DOT = (0, 2, 3, 3, 4, 3, 3, 2, 0)
# OpenCV's SinTable: sin(degrees) to seven decimals, held as float32. ellipse2Poly reads cos as SinTable[450 - angle].
_SIN_TABLE = tuple(struct.unpack('<f', struct.pack('<f', round(math.sin(math.radians(i)), 7)))[0] for i in range(451))


def _check_renderer(renderer):
    if renderer not in RENDERERS: raise ValueError('unsupported pose guide renderer')
    return renderer


def renderer_identity(renderer=RENDERER):
    """Return the exact local implementation/encoder identity behind PNG bytes."""
    if _check_renderer(renderer) == RENDERER:
        return {
            'schema': 'studio.pose-raster-renderer-identity/v1',
            'renderer_id': RENDERER,
            'implementation': RENDERER_IMPLEMENTATION,
            'png_encoder_contract': PNG_ENCODER_CONTRACT,
            'pillow_version': PIL.__version__,
            'zlib_compile_version': zlib.ZLIB_VERSION,
            'zlib_runtime_version': zlib.ZLIB_RUNTIME_VERSION,
        }
    return {
        'schema': 'studio.pose-raster-renderer-identity/v1',
        'renderer_id': OPENPOSE_RENDERER,
        'implementation': OPENPOSE_IMPLEMENTATION,
        'reference': dict(OPENPOSE_REFERENCE),
        'png_encoder_contract': PNG_ENCODER_CONTRACT,
        'pillow_version': PIL.__version__,
        'zlib_compile_version': zlib.ZLIB_VERSION,
        'zlib_runtime_version': zlib.ZLIB_RUNTIME_VERSION,
    }


def renderer_sha256(renderer=RENDERER):
    """Pin the renderer implementation and libraries, not only its logical name."""
    encoded = json.dumps(
        renderer_identity(renderer), sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


def openpose_stick_scale(width, height):
    """controlnet_aux xinsr_stick_scaling: 1 below 500 px on the long side, else 2 + long_side // 1000, at most 7."""
    longest = max(width, height)
    return 1 if longest < 500 else min(2 + longest // 1000, 7)


def _ellipse_polygon(cx, cy, a, b, angle):
    """cv2.ellipse2Poly((cx, cy), (a, b), angle, 0, 360, 1) on integer input, reproduced exactly."""
    while angle < 0: angle += 360
    while angle > 360: angle -= 360
    cos_a, sin_a = _SIN_TABLE[450 - angle], _SIN_TABLE[angle]
    points = []
    for step in range(361):
        x, y = a * _SIN_TABLE[450 - step], b * _SIN_TABLE[step]
        point = (round(cx + x * cos_a - y * sin_a), round(cy + x * sin_a + y * cos_a))
        if not points or points[-1] != point: points.append(point)
    return points if len(points) > 1 else [(cx, cy), (cx, cy)]


def _draw_openpose(image, triples, width, height):
    # Keypoints travel normalised in controlnet_aux (x / W, then x * W again); the same float steps keep ints identical.
    points = [(triples[i] / width, triples[i + 1] / height) if triples[i + 2] else None for i in range(0, 54, 3)]
    draw = ImageDraw.Draw(image); half = OPENPOSE_STICK * openpose_stick_scale(width, height)
    for index, (start, end) in enumerate(OPENPOSE_LIMBS):
        if points[start] is None or points[end] is None: continue
        ys = (points[start][0] * float(width), points[end][0] * float(width))
        xs = (points[start][1] * float(height), points[end][1] * float(height))
        length = ((xs[0] - xs[1]) ** 2 + (ys[0] - ys[1]) ** 2) ** 0.5
        angle = math.degrees(math.atan2(xs[0] - xs[1], ys[0] - ys[1]))
        polygon = _ellipse_polygon(int((ys[0] + ys[1]) / 2), int((xs[0] + xs[1]) / 2), int(length / 2), half, int(angle))
        draw.polygon(polygon, fill=tuple(int(float(c) * 0.6) for c in COLORS[index]))
    for index, point in enumerate(points):
        if point is None: continue
        x, y = int(point[0] * width), int(point[1] * height)
        for dy, reach in enumerate(_OPENPOSE_DOT, start=-OPENPOSE_JOINT_RADIUS):
            draw.line(((x - reach, y + dy), (x + reach, y + dy)), fill=COLORS[index])


def render_png(artifact, threshold=.3, renderer=RENDERER):
    data = export_openpose(artifact, threshold)
    width, height = data['canvas_width'], data['canvas_height']
    triples = data['people'][0]['pose_keypoints_2d']
    if _check_renderer(renderer) == OPENPOSE_RENDERER:
        image = Image.new('RGB', (width, height), (0, 0, 0))
        try:
            _draw_openpose(image, triples, width, height)
            with io.BytesIO() as output:
                image.save(output, format='PNG', optimize=False)
                return output.getvalue()
        finally:
            image.close()
    # Pixel-edge positions at width/height are clamped only during rasterization.
    points = [(min(width - 1, int(triples[i])), min(height - 1, int(triples[i + 1])))
              if triples[i + 2] else None for i in range(0, 54, 3)]
    image = Image.new('RGB', (width, height), (0, 0, 0))
    try:
        draw = ImageDraw.Draw(image); stroke = max(1, min(width, height) // 128)
        for start, end in LIMBS:
            if points[start] is not None and points[end] is not None:
                draw.line((points[start], points[end]), fill=COLORS[end], width=stroke)
        for index, point in enumerate(points):
            if point is not None:
                x, y = point
                draw.ellipse((x - stroke, y - stroke, x + stroke, y + stroke), fill=COLORS[index])
        with io.BytesIO() as output:
            image.save(output, format='PNG', optimize=False)
            return output.getvalue()
    finally:
        image.close()
