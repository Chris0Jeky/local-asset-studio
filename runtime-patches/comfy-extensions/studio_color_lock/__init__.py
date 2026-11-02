"""Studio colour lock: keep a repaint's lightness and take its colour from the source picture.

A depth and line-art repaint locks geometry, not colour, so eyes and clothes change colour from seed to seed. Naming the
colour in the prompt did not hold it (1 November 2026, 9 renders, face chroma error 5 to 9). Lightness carries the detail
and the two chroma channels carry the colour, so swapping chroma per pixel keeps the new finish and the old colours
(error about 2). Global colour-match nodes cannot do this: they match image-wide statistics, so a small eye stays wrong.

Loaded with the VRAM guard through `--extra-model-paths-config`; no file inside the ComfyUI installation is edited.
Only sound when both pictures line up, so use it after a geometry-locked repaint, not on a free generation.
"""
import torch
import torch.nn.functional as F


def luma_chroma(rgb):
    y = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    return y, (rgb[..., 2] - y) * 0.564, (rgb[..., 0] - y) * 0.713


def blur(x, radius):
    """Gaussian blur of a BHW tensor, which hides sub-pixel disagreement between the two pictures' edges."""
    if radius <= 0: return x
    half = max(1, int(radius * 3))
    grid = torch.arange(-half, half + 1, dtype=x.dtype, device=x.device)
    kernel = torch.exp(-grid ** 2 / (2 * radius ** 2))
    kernel = (kernel / kernel.sum())[None, None]
    x = F.pad(x[:, None], (half, half, half, half), mode='replicate')
    return F.conv2d(F.conv2d(x, kernel[..., None, :]), kernel[..., None]).squeeze(1)


def color_lock(image, reference, strength=1.0, radius=2.0):
    if reference.shape[1:3] != image.shape[1:3]:
        reference = F.interpolate(reference.movedim(-1, 1), size=image.shape[1:3], mode='bicubic', antialias=True).movedim(1, -1).clamp(0, 1)
    if reference.shape[0] != image.shape[0]: reference = reference[:1].expand(image.shape[0], -1, -1, -1)
    y, cb, cr = luma_chroma(image[..., :3])
    _, ref_cb, ref_cr = luma_chroma(reference[..., :3].to(image.device, image.dtype))
    cb = torch.lerp(cb, blur(ref_cb, radius), strength)
    cr = torch.lerp(cr, blur(ref_cr, radius), strength)
    return torch.stack((y + cr / 0.713, y - (0.299 * cr / 0.713 + 0.114 * cb / 0.564) / 0.587, y + cb / 0.564), -1).clamp(0, 1)


class StudioColorLock:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "reference": ("IMAGE",),
                             "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                             "radius": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 32.0, "step": 0.5})}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "lock"
    CATEGORY = "image/postprocessing"

    def lock(self, image, reference, strength, radius):
        return (color_lock(image, reference, strength, radius),)


NODE_CLASS_MAPPINGS = {"StudioColorLock": StudioColorLock}
NODE_DISPLAY_NAME_MAPPINGS = {"StudioColorLock": "Studio Colour Lock"}
