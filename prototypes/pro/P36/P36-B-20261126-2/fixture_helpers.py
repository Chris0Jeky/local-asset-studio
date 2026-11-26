"""Tiny synthetic drawings for executable measurement tests, not generated art."""
from __future__ import annotations

import hashlib

from PIL import Image, ImageDraw

REGIONS = {
    "iris": [0.25, 0.25, 0.375, 0.375],
    "hair": [0.25, 0.125, 0.75, 0.1875],
}


def fixture(path, *, iris=(45, 120, 200), hair=(70, 40, 20),
            outfit=(80, 130, 80), expression="neutral", geometry="round", marker=0):
    image = Image.new("RGBA", (128, 128), (235, 235, 235, 255))
    draw = ImageDraw.Draw(image)
    if geometry == "round":
        draw.ellipse((16, 24, 111, 95), fill=(220, 170, 140, 255))
    else:
        draw.polygon([(16, 24), (111, 24), (88, 95), (40, 95)], fill=(220, 170, 140, 255))
    draw.rectangle((32, 16, 95, 23), fill=(*hair, 255))
    draw.rectangle((32, 32, 47, 47), fill=(*iris, 255))
    draw.rectangle((32, 96, 95, 119), fill=(*outfit, 255))
    draw.line((45, 76, 80, 76 if expression == "neutral" else 85), fill=(90, 40, 40, 255), width=2)
    image.putpixel((0, 0), (marker % 256, 0, 0, 255))
    image.save(path, format="PNG")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature(value, media_sha, provenance="fixture_truth"):
    return {"value": value, "provenance": provenance, "media_sha256": media_sha}
