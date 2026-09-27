"""Thread-safe decompression-bomb refusal (#1061): no process-wide warnings state."""
from contextlib import contextmanager
from PIL import Image

@contextmanager
def open_bounded(source):
    """Image.open(source), refused with DecompressionBombError before any decode when width*height exceeds Image.MAX_IMAGE_PIXELS."""
    image = Image.open(source)
    try:
        limit = Image.MAX_IMAGE_PIXELS
        if limit is not None and image.width * image.height > limit:
            raise Image.DecompressionBombError(f"Image size ({image.width * image.height} pixels) exceeds limit of {limit} pixels")
        yield image
    finally:
        image.close()
