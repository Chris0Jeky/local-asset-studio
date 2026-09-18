"""Standalone baseline extraction for the bounded-comparison red test."""
from PIL import Image, ImageChops


def changed_mask(a, b):
    if a.size != b.size: raise ValueError('Cannot compare differing dimensions')
    diff = ImageChops.difference(a.convert('RGBA'), b.convert('RGBA'))
    maximum = Image.new('L', a.size, 0)
    for channel in diff.split(): maximum = ImageChops.lighter(maximum, channel)
    return maximum.point(lambda x: 255 if x else 0)
