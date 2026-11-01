"""The Studio colour lock node (runtime-patches/comfy-extensions/studio_color_lock). Needs Torch, so it skips where there is none."""
import importlib.util, unittest
from pathlib import Path
try: import torch
except ImportError: torch = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(torch is None, 'Torch is not installed')
class ColorLock(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('studio_color_lock_under_test', ROOT / 'runtime-patches/comfy-extensions/studio_color_lock/__init__.py')
        self.node = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.node)

    def test_identical_pictures_come_back_unchanged(self):
        image = torch.rand(1, 32, 48, 3)
        self.assertLess((self.node.color_lock(image, image, 1.0, 0.0) - image).abs().max().item(), 1e-3)

    def test_a_small_wrong_colour_area_takes_the_source_colour_and_keeps_its_lightness(self):
        source = torch.full((1, 32, 32, 3), 0.5); repaint = source.clone()
        source[:, 12:20, 12:20] = torch.tensor([0.6, 0.3, 0.8])  # violet eye
        repaint[:, 12:20, 12:20] = torch.tensor([0.2, 0.5, 0.8])  # blue eye
        out = self.node.color_lock(repaint, source, 1.0, 0.0)
        wanted = self.node.luma_chroma(source)[1:]; got = self.node.luma_chroma(out)[1:]
        for a, b in zip(wanted, got): self.assertLess((a - b).abs().max().item(), 1e-2)
        self.assertLess((self.node.luma_chroma(out)[0] - self.node.luma_chroma(repaint)[0]).abs().max().item(), 1e-2)

    def test_strength_zero_keeps_the_repaint(self):
        a, b = torch.rand(1, 16, 16, 3), torch.rand(1, 16, 16, 3)
        self.assertLess((self.node.color_lock(a, b, 0.0, 2.0) - a).abs().max().item(), 1e-3)

    def test_a_reference_of_another_size_is_resized(self):
        self.assertEqual(self.node.color_lock(torch.rand(1, 40, 24, 3), torch.rand(1, 20, 12, 3)).shape, (1, 40, 24, 3))

    def test_blur_keeps_the_size_and_a_flat_picture(self):
        flat = torch.full((1, 10, 14), 0.25)
        self.assertLess((self.node.blur(flat, 2.0) - flat).abs().max().item(), 1e-5)
        self.assertEqual(self.node.blur(flat, 2.0).shape, flat.shape)


if __name__ == '__main__': unittest.main()
