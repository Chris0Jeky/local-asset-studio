"""Bounded, deterministic review derivatives; original media stays unchanged.

Coordinates are integer basis points in the EXIF-oriented source canvas. Matching
coordinates do not imply semantic registration between independently generated art.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path

MAX_IMAGE_BYTES = 32 * 1024**2
MAX_PIXELS = 16 * 1024**2
MAX_BLANK_PIXELS = 64 * 1024**2
MAX_TOTAL_BYTES = 256 * 1024**2
MAX_CANDIDATES = 16
PREVIEW_EDGE = 1536
FULL_CROP = [0, 0, 10000, 10000]


def text_safe_metrics(data):
    """Detail proxy, never text legibility or art acceptance. EXIF-oriented, alpha on mid-grey.

    Count adjacent luminance differences >=16 within each half at <=512px;
    exclude the centre boundary so a plain two-tone picture has no internal detail.
    """
    if len(data) > MAX_IMAGE_BYTES: raise ValueError('Text-safe source exceeds the 32 MiB image budget')
    image, _ = decode(data)
    try:
        from PIL import Image
        image.thumbnail((512, 512), Image.Resampling.LANCZOS)
        if image.width < 4 or image.height < 2: raise ValueError('Text-safe check needs at least 4 by 2 pixels')
        with Image.new('RGBA', image.size, (128, 128, 128, 255)) as background:
            background.alpha_composite(image)
            with background.convert('L') as grey:
                width, height = grey.size; pixels = grey.tobytes(); densities = []
                for left, right in ((0, width // 2), (width // 2, width)):
                    edges = pairs = 0
                    for y in range(height):
                        for x in range(left, right):
                            value = pixels[y * width + x]
                            if x + 1 < right:
                                pairs += 1; edges += abs(value - pixels[y * width + x + 1]) >= 16
                            if y + 1 < height:
                                pairs += 1; edges += abs(value - pixels[(y + 1) * width + x]) >= 16
                    densities.append(edges / pairs)
        left, right = densities
        return {'method': 'adjacent-luma-v1', 'sample_size': list(image.size), 'threshold': 16,
                'left_edge_density': left, 'right_edge_density': right,
                'left_right_ratio': left / right if right else None,
                'comparison': 'left quieter' if left < right else 'left busier' if left > right else 'equal detail'}
    finally: image.close()


def blank_kind(path):
    """'transparent' or 'uniform' for a still picture with no content, else ''. Advisory only: exact extrema, stills only, never raises."""
    try:
        from PIL import Image
        with Image.open(path) as image:
            if image.width * image.height > MAX_BLANK_PIXELS or getattr(image, 'n_frames', 1) > 1: return ''  # animations may start blank on purpose
            if image.mode in ('P', 'PA', 'RGBa', 'La') or 'transparency' in image.info: image = image.convert('RGBA')
            extrema = image.getextrema(); bands = extrema if isinstance(extrema[0], (tuple, list)) else (extrema,)
            if image.mode in ('RGBA', 'LA') and bands[-1][1] == 0: return 'transparent'
            return 'uniform' if all(low == high for low, high in bands) else ''
    except Exception: return ''


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def checked_bytes(path, expected_hash, expected_size=None):
    """Hash the exact bounded bytes subsequently decoded/copied, not a second read."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError('Review source is missing or exceeds the 32 MiB image budget')
    with path.open('rb') as stream:
        data = stream.read(MAX_IMAGE_BYTES + 1)
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError('Review source is empty or exceeds the image budget')
    if expected_size is not None and len(data) != expected_size:
        raise ValueError('Review source size changed; original evidence was preserved')
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError('Review source hash changed; original evidence was preserved')
    return data


def decode(data):
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data), formats=('PNG', 'JPEG', 'WEBP')) as source:
            if source.width * source.height > MAX_PIXELS:
                raise ValueError('Review source exceeds the 16-megapixel decode budget')
            if getattr(source, 'n_frames', 1) != 1:
                raise ValueError('Review desk accepts still images, not silent first-frame extraction')
            if source.mode not in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA'):
                raise ValueError('Review needs an 8-bit RGB/greyscale image; convert a copy explicitly')
            orientation = source.getexif().get(274, 1)
            original_size = list(source.size)
            # exif_transpose copies the entire source even for a no-op. Keep
            # that intermediate only when an orientation actually needs it.
            if orientation in (2, 3, 4, 5, 6, 7, 8):
                with ImageOps.exif_transpose(source) as oriented:
                    image = oriented.convert('RGBA')
            else:
                image = source.convert('RGBA')
            # No prompts, workflow text, EXIF or producer fields in blind derivatives.
            image.info.clear()
            return image, {'encoded_size': original_size, 'oriented_size': list(image.size),
                           'exif_orientation': orientation,
                           'colour': '8-bit review preview; embedded ICC profiles are not colour-managed'}
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError('Review source could not be decoded within the still-image contract') from exc


def crop_box(value, size):
    if not isinstance(value, list) or len(value) != 4 or any(type(v) is not int for v in value):
        raise ValueError('Crop must contain four integer basis-point edges')
    left, top, right, bottom = value
    if not 0 <= left < right <= 10000 or not 0 <= top < bottom <= 10000:
        raise ValueError('Crop edges must describe a nonempty rectangle within 0–10000')
    width, height = size
    # Floor leading edges and ceil trailing edges, including at least one pixel.
    return (left * width // 10000, top * height // 10000,
            (right * width + 9999) // 10000, (bottom * height + 9999) // 10000)


def write_new(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', compress_level=6)
    return buffer.getvalue()


def make_preview(data, path):
    image, transform = decode(data)
    try:
        from PIL import Image
        image.thumbnail((PREVIEW_EDGE, PREVIEW_EDGE), Image.Resampling.LANCZOS)
        transform['preview_size'] = list(image.size)
        return transform, write_new(path, png_bytes(image))
    finally:image.close()


def render_sheet(candidates, read_source, crop, path, background='dark'):
    """Same normalized crop, no aspect distortion, fixed cells and explicit alpha."""
    from PIL import Image, ImageDraw, ImageOps
    crop_box(crop, (1, 1))
    if background not in ('dark', 'light'):
        raise ValueError('Choose the dark or light alpha-review background')
    if not 1 <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError('Review requires one to sixteen candidates')
    colours = ('#20232b', '#ffffff') if background == 'dark' else ('#f1f2f5', '#161923')
    columns = min(4, len(candidates)); rows = (len(candidates) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * 384, rows * 416), colours[0])
    draw = ImageDraw.Draw(sheet); transforms = []
    try:
        for i, candidate in enumerate(candidates):
            image, decoded = decode(read_source(candidate))
            try:
                box = crop_box(crop, image.size)
                with image.crop(box) as region, ImageOps.contain(region, (360, 368), Image.Resampling.LANCZOS) as thumb:
                    x = i % columns * 384; y = i // columns * 416
                    sheet.paste(thumb, (x + (384-thumb.width)//2, y + (368-thumb.height)//2), thumb)
                    draw.text((x+12, y+382), 'Candidate ' + candidate['alias'], fill=colours[1])
                    transforms.append({'alias': candidate['alias'], 'basis_points': list(crop),
                                       'pixel_box': list(box), 'source_size': decoded['oriented_size'],
                                       'rendered_size': list(thumb.size)})
            finally:image.close()
        receipt = write_new(path, png_bytes(sheet))
        return dict(receipt, transforms=transforms, background=background, canvas=list(sheet.size))
    finally:sheet.close()
