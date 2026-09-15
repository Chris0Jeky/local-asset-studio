"""Erase explicit regions of an existing 8-bit PNG guide without reframing it."""
import hashlib
import io
import re
from PIL import Image, ImageChops, UnidentifiedImageError

MAX_IMAGE_BYTES = 32 * 1024 * 1024
OPERATION = 'studio.depth-erasure/v1'


def _rectangles(boxes, width, height):
    if not isinstance(boxes, list) or len(boxes) > 64:
        raise ValueError('rectangles must be a list of at most 64 pixel-edge boxes')
    result = []
    for box in boxes:
        if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
            raise ValueError('each rectangle must contain four integers: left, top, right, bottom')
        left, top, right, bottom = box
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError('rectangle must be nonempty and inside the unchanged canvas')
        if box in result: raise ValueError('duplicate rectangle')
        result.append(list(box))
    return sorted(result)


def erase_png(data, expected_sha256, rectangles):
    """Return (new PNG bytes, receipt). Black is erased evidence, not neutral depth.

    Coordinates use half-open pixel-edge rectangles; overlap counts only once.
    L/RGB single-frame 8-bit PNG only. This function does not interpret depth,
    estimate anatomy, bind a route or grant permission to edit final artwork.
    """
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_IMAGE_BYTES:
        raise ValueError('source PNG must contain 1 byte to 32 MiB')
    if not isinstance(expected_sha256, str) or re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is None:
        raise ValueError('expected source SHA-256 must be lowercase hexadecimal')
    source_hash = hashlib.sha256(data).hexdigest()
    if source_hash != expected_sha256: raise ValueError('source PNG hash changed')
    try:
        with Image.open(io.BytesIO(data)) as source:
            width, height = source.size
            if width > 8192 or height > 8192 or width * height > 16777216:
                raise ValueError('source canvas exceeds 8192 per dimension or 16 megapixels')
            if source.format != 'PNG' or source.mode not in ('L', 'RGB'):
                raise ValueError('only L/RGB 8-bit PNG guides are supported; no implicit conversion')
            if getattr(source, 'n_frames', 1) != 1 or 'transparency' in source.info:
                raise ValueError('animated or transparent guides are unsupported')
            boxes = _rectangles(rectangles, width, height)
            source.load()
            with source.copy() as result, Image.new('L', source.size, 0) as mask:
                for box in boxes:
                    result.paste(0 if result.mode == 'L' else (0, 0, 0), tuple(box))
                    mask.paste(255, tuple(box))
                with ImageChops.difference(source, result) as diff:
                    bands = diff.split()
                    try:
                        maximum = bands[0].copy()
                        try:
                            for band in bands[1:]:
                                combined = ImageChops.lighter(maximum, band)
                                maximum.close(); maximum = combined
                            with maximum.point([0] + [255] * 255) as changed:
                                changed_count = changed.histogram()[255]
                                with ImageChops.subtract(changed, mask) as outside:
                                    if outside.getbbox() is not None:
                                        raise ValueError('outside-erasure pixel preservation failed')
                        finally: maximum.close()
                    finally:
                        for band in bands: band.close()
                if not boxes:
                    output = data
                else:
                    # Preserve stored pixels, not ancillary metadata/color transforms.
                    result.info.clear()
                    with io.BytesIO() as encoded:
                        result.save(encoded, format='PNG', optimize=False)
                        output = encoded.getvalue()
                receipt = dict(schema=OPERATION, authority='none', role='conditioning_erasure',
                               generation_submitted=False, native_control_qualified=False,
                               neutral_depth_claim=False, source_sha256=source_hash,
                               output_sha256=hashlib.sha256(output).hexdigest(),
                               width=width, height=height, mode=source.mode, rectangles=boxes,
                               erased_pixels=mask.histogram()[255], changed_pixels=changed_count,
                               outside_pixels_equal=True)
                return output, receipt
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('invalid, truncated or oversized PNG guide') from exc
