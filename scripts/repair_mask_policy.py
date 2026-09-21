"""Bounded, opt-in source mask operations and exact candidate-context checks.

This owns no compositor, registration estimator, packet store or execution path.
"""
from contextlib import closing
from PIL import Image, ImageChops, ImageFilter
from scripts.pixel_diff import changed_mask

VERSION = 'straight-rgba-bilinear-v2'


def compile_policy(value, source_size, max_pixels):
    if type(value) is not dict or set(value) != {'dilate_px', 'feather_px'}:
        raise ValueError('Declare exact coverage policy fields')
    for key, limit in (('dilate_px', 8), ('feather_px', 16)):
        if type(value[key]) is not int or not 0 <= value[key] <= limit:
            raise ValueError(f'{key} must be an integer in 0..{limit}')
    radius = value['dilate_px'] + value['feather_px']
    if (source_size[0] + 2*radius) * (source_size[1] + 2*radius) > max_pixels:
        raise ValueError('Mask processing scratch exceeds raster pixel limit')
    return {**value, 'space': 'normalized-source-pixels', 'boundary': 'zero-extension',
            'dilation': 'square-maximum', 'feather': 'separable-box-nearest-integer-per-pass',
            'order': ['dilate', 'feather', 'forward-bilinear', 'inverse-bilinear'],
            'candidate_context': 'exact-unwritten-RGBA-including-padding'}


def process_coverage(mask, policy):
    dilation, feather = policy['dilate_px'], policy['feather_px']
    radius = dilation + feather
    if radius == 0: return mask.copy()
    # A finite halo prevents Pillow's edge extension from extending the authored
    # mask. Expansion beyond the declared context is checked by the caller AFTER
    # this operation, never silently clipped at the context boundary.
    current = Image.new('L', (mask.width + 2*radius, mask.height + 2*radius), 0)
    try:
        current.paste(mask, (radius, radius))
        for filter_ in (ImageFilter.MaxFilter(2*dilation+1) if dilation else None,
                        ImageFilter.BoxBlur(feather) if feather else None):
            if filter_ is not None:
                newer = current.filter(filter_)
                current.close(); current = newer
        return current.crop((radius, radius, radius+mask.width, radius+mask.height))
    finally: current.close()


def interior_anchor_count(work_write, geometry):
    left, top, _, _ = geometry['padding_ltrb']; width, height = geometry['resized_size']
    with closing(work_write.crop((left, top, left+width, top+height))) as inner:
        count = inner.histogram()[0]
    if count == 0:
        raise ValueError('Strict context policy needs an unwritten interior anchor; enlarge context')
    return count


def verify_context(context, candidate, work_write, geometry):
    anchors = interior_anchor_count(work_write, geometry)
    with closing(changed_mask(context, candidate)) as delta:
        with closing(work_write.point([255] + [0]*255)) as locked:
            with closing(ImageChops.multiply(delta, locked)) as changed:
                count = changed.histogram()[255]
    if count:
        raise ValueError('Candidate changed unwritten context or padding; reject rather than auto-align')
    return {'interior_anchor_pixels': anchors, 'changed_anchor_pixels': count,
            'channels': 'all-straight-RGBA-including-hidden-RGB',
            'padding_checked': True, 'interior_registration_proven': False}
