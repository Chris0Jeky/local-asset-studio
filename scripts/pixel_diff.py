"""Exact RGBA difference masks with bounded, deterministically closed scratch.

Inputs and the required output L mask remain full-size. Only conversion/difference
scratch is tiled; hidden RGB under zero alpha is intentionally significant.
"""
from __future__ import annotations
from contextlib import closing
from PIL import Image, ImageChops

_TILE_EDGE = 512
_CHANGED = [0] + [255] * 255


def _tile_mask(a: Image.Image, b: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    with closing(a.crop(box)) as left, closing(b.crop(box)) as right:
        with closing(left.convert('RGBA')) as left_rgba, closing(right.convert('RGBA')) as right_rgba:
            with closing(ImageChops.difference(left_rgba, right_rgba)) as difference:
                maximum = difference.getchannel(0)
                try:
                    for channel in (1, 2, 3):
                        with closing(difference.getchannel(channel)) as band:
                            newer = ImageChops.lighter(maximum, band)
                        maximum.close(); maximum = newer
                    return maximum.point(_CHANGED)
                finally: maximum.close()


def changed_mask(a: Image.Image, b: Image.Image) -> Image.Image:
    """Return 255 iff any converted RGBA channel differs; never mutate inputs."""
    if a.size != b.size: raise ValueError('Cannot compare differing dimensions')
    result = Image.new('L', a.size, 0)
    try:
        for y in range(0, a.height, _TILE_EDGE):
            for x in range(0, a.width, _TILE_EDGE):
                box = (x, y, min(x + _TILE_EDGE, a.width), min(y + _TILE_EDGE, a.height))
                with closing(_tile_mask(a, b, box)) as tile:
                    result.paste(tile, (x, y))
        return result
    except BaseException:
        result.close(); raise
