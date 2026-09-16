"""Experimental COCO-18 guide raster; not an upstream ControlNet renderer clone."""
import io
from PIL import Image, ImageDraw
from .pose_artifact import export_openpose

RENDERER = 'studio.coco18-lines/v1'
COLORS = ((255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
          (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
          (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
          (255, 0, 255), (255, 0, 170), (255, 0, 85))
LIMBS = ((1, 2), (2, 3), (3, 4), (1, 5), (5, 6), (6, 7), (1, 8), (8, 9),
         (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17))


def render_png(artifact, threshold=.3):
    data = export_openpose(artifact, threshold)
    width, height = data['canvas_width'], data['canvas_height']
    triples = data['people'][0]['pose_keypoints_2d']
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
