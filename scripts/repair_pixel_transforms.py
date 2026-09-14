"""Explicit offline raster transforms; legacy character-edit packets are unchanged.

The kernels consume decoded normalized buffers, not a model request. They prove
sample preservation, not candidate registration, artistic quality or permission.
"""
from __future__ import annotations

from fractions import Fraction
from math import ceil

from PIL import Image, ImageChops, ImageFilter

from scripts.character_edit_pixels import changed_mask
from scripts.repair_proposal import transform

VERSION = 'straight-rgba-bilinear-v1'
MAX_PIXELS = 24_000_000


def require(condition, message):
    if not condition: raise ValueError(message)


def compile_transform(source_size, spec):
    require(type(spec) is dict and set(spec) == {'version', 'box', 'scale', 'padding', 'alignment'},
            'Declare the exact raster transform fields')
    require(spec['version'] == VERSION, 'Unsupported raster transform version')
    # The existing declaration checker owns rational coordinate arithmetic. This
    # call alone performs no raster operation and never makes v0 proposals jobs.
    geometry = transform(source_size, {key: spec[key] for key in ('box', 'scale', 'padding', 'alignment')})
    require(source_size[0] * source_size[1] <= MAX_PIXELS, 'Source exceeds raster pixel limit')
    require(geometry['work_size'][0] * geometry['work_size'][1] <= MAX_PIXELS,
            'Working canvas exceeds raster pixel limit')
    require(Fraction(1, 4) <= Fraction(*spec['scale']) <= 4, 'Supported raster scale is one quarter through four')
    return {**geometry, 'version': VERSION, 'source_size': list(source_size),
            'context_box': list(spec['box']), 'requested_scale': list(spec['scale']),
            'image_filter': 'bilinear-per-straight-RGBA-channel', 'coverage_filter': 'bilinear',
            'blend': 'Pillow-encoded-sample-L-coverage', 'coverage_operations': 'forward-then-inverse; no dilation or feather',
            'protection_projection': 'conservative-square-max-before-nearest',
            'pillow_version': Image.__version__}


def _resize_rgba(image, size):
    # Resizing RGBA as a single Pillow image premultiplies alpha. Separate L
    # channels make the chosen straight-sample policy explicit, including RGB
    # samples hidden under zero alpha. This is not colour-space conversion.
    return Image.merge('RGBA', tuple(channel.resize(size, Image.Resampling.BILINEAR)
                                    for channel in image.split()))


def _validate_inputs(source, write, protect, geometry):
    require(source.mode == 'RGBA' and list(source.size) == geometry['source_size'], 'Expected normalized RGBA source')
    require(not source.info.get('exif') and 'transparency' not in source.info,
            'Normalize orientation and transparency explicitly before raster preparation')
    require(write.mode == protect.mode == 'L' and write.size == protect.size == source.size,
            'Coverage and protection must be same-size grayscale L')
    require(sum(protect.histogram()[1:255]) == 0, 'Protection must be binary')
    _scope(write, protect, geometry)


def _scope(write, protect, geometry):
    support = write.point(lambda value: 255 if value else 0)
    bounds = support.getbbox()
    require(bounds is not None and write.histogram()[0] > 0, 'Local coverage must edit and preserve source pixels')
    x0, y0, x1, y1 = geometry['context_box']
    require(x0 <= bounds[0] < bounds[2] <= x1 and y0 <= bounds[1] < bounds[3] <= y1,
            'Effective write coverage extends beyond context')
    require(ImageChops.multiply(support, protect).getbbox() is None, 'Write coverage overlaps protection')


def _work_protection(protect, box, resized):
    cropped = protect.crop(box)
    if cropped.getbbox() is None: return Image.new('L', resized, 0)
    # A nearest sample is at most half a source/output cell from any source
    # sample in that cell. The extra whole pixel conservatively covers the
    # bilinear footprint and integer rounding; thin protection cannot vanish.
    # This intentionally overprotects, and does not claim minimal support.
    radius = ceil(max(1, cropped.width / resized[0], cropped.height / resized[1])) + 1
    expanded = cropped.filter(ImageFilter.MaxFilter(2 * radius + 1))
    return expanded.resize(resized, Image.Resampling.NEAREST)


def prepare_pixels(source, authored_write, protect, spec):
    geometry = compile_transform(list(source.size), spec)
    _validate_inputs(source, authored_write, protect, geometry)
    box = tuple(geometry['context_box']); resized = tuple(geometry['resized_size'])
    work_size = tuple(geometry['work_size']); left, top, _, _ = geometry['padding_ltrb']
    crop = source.crop(box)
    inner = _resize_rgba(crop, resized)
    context = Image.new('RGBA', work_size, (0, 0, 0, 0)); context.paste(inner, (left, top))
    context.info = source.info.copy()
    work_inner = authored_write.crop(box).resize(resized, Image.Resampling.BILINEAR)
    work_write = Image.new('L', work_size, 0); work_write.paste(work_inner, (left, top))
    effective = Image.new('L', source.size, 0)
    effective.paste(work_inner.resize(crop.size, Image.Resampling.BILINEAR), box[:2])
    _scope(effective, protect, geometry)
    inner_protect = _work_protection(protect, box, resized)
    require(ImageChops.multiply(work_inner.point(lambda value: 255 if value else 0), inner_protect).getbbox() is None,
            'Conservative work protection overlaps sampler coverage; revise scope or scale')
    work_protect = Image.new('L', work_size, 255); work_protect.paste(inner_protect, (left, top))
    return {'geometry': {**geometry, 'resampling_performed': True},
            'images': {'context': context, 'work_write': work_write, 'work_protect': work_protect,
                       'authored_write': authored_write.copy(), 'effective_write': effective,
                       'source_protect': protect.copy()}}


def render_pixels(source, authored_write, protect, spec, candidate):
    prepared = prepare_pixels(source, authored_write, protect, spec)
    geometry, images = prepared['geometry'], prepared['images']
    require(candidate.mode == 'RGBA' and list(candidate.size) == geometry['work_size'],
            'Candidate must have the exact prepared RGBA working canvas')
    require(candidate.info.get('icc_profile') == source.info.get('icc_profile'), 'Candidate/source colour profiles differ')
    require(not candidate.info.get('exif') and 'transparency' not in candidate.info, 'Candidate orientation/alpha is not normalized')
    left, top, _, _ = geometry['padding_ltrb']; width, height = geometry['resized_size']
    inner_box = (left, top, left + width, top + height)
    candidate_inner = candidate.crop(inner_box)
    no_op = candidate_inner.tobytes() == images['context'].crop(inner_box).tobytes()
    result = source.copy(); box = tuple(geometry['context_box'])
    if not no_op:
        # Padding never participates in inverse resampling. The original full
        # source remains the destination; only the recorded final coverage blends.
        mapped = _resize_rgba(candidate_inner, (box[2] - box[0], box[3] - box[1]))
        repaired = Image.composite(mapped, source.crop(box), images['effective_write'].crop(box))
        result.paste(repaired, box[:2])
    delta = changed_mask(source, result)
    locked = images['effective_write'].point(lambda value: 0 if value else 255)
    outside = ImageChops.multiply(delta, locked).histogram()[255]
    protected = ImageChops.multiply(delta, protect).histogram()[255]
    require(outside == 0 and protected == 0, 'Pixel preservation invariant failed')
    return {'result': result, 'delta': delta, 'effective_write': images['effective_write'],
            'geometry': geometry, 'outside_changes': outside, 'protected_changes': protected,
            'no_op': delta.getbbox() is None, 'neural_inference': False, 'semantic_approval': False}
