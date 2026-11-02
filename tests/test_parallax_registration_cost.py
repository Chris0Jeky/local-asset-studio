"""Exact scoring and work bounds for the parallax registration search; no runtime or GPU."""
import math
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import parallax


def histogram_cost(patch_image, other, x, y, patch_sum):
    """The pre-optimization scorer, retained as an independent exact oracle."""
    window = other.crop((x, y, x + patch_image.width, y + patch_image.height))
    return sum(ImageStat.Stat(ImageChops.difference(patch_image, window)).sum) / (patch_sum + sum(ImageStat.Stat(window).sum) + 1)


def histogram_search(patch_image, other, x, y, centre, radius):
    costs = {}; patch_sum = sum(ImageStat.Stat(patch_image).sum)
    for dy in range(centre[1] - radius, centre[1] + radius + 1):
        for dx in range(centre[0] - radius, centre[0] + radius + 1):
            if 0 <= x + dx and 0 <= y + dy and x + dx + patch_image.width <= other.width and y + dy + patch_image.height <= other.height:
                costs[(dx, dy)] = histogram_cost(patch_image, other, x + dx, y + dy, patch_sum)
    return (min(costs, key=costs.get), costs) if costs else (None, costs)


def noise(size, seed):
    return Image.frombytes("L", size, random.Random(seed).randbytes(size[0] * size[1]))


class RegistrationCostTests(unittest.TestCase):
    def assert_search_equal(self, patch_image, other, x, y, centre, radius):
        before = (patch_image.tobytes(), other.tobytes())
        expected = histogram_search(patch_image, other, x, y, centre, radius)
        actual = parallax._search(patch_image, other, x, y, centre, radius)
        self.assertEqual(actual[0], expected[0])
        self.assertEqual(list(actual[1].items()), list(expected[1].items()), "candidate order and every exact score must survive")
        self.assertEqual((patch_image.tobytes(), other.tobytes()), before, "search must leave both input images unchanged")
        return actual

    def test_registration_edge_maps_are_eight_bit_single_channel(self):
        for mode in ("L", "RGB", "RGBA"):
            with self.subTest(mode=mode):
                image = noise((32, 24), 1910).convert(mode)
                self.assertEqual(parallax.edge_map(image).mode, "L")

    def test_costs_match_for_empty_full_all_levels_and_random_edges(self):
        ramp = Image.frombytes("L", (16, 16), bytes(range(256)))
        pictures = [Image.new("L", (16, 16), value) for value in (0, 1, 255)] + [ramp, noise((16, 16), 1882)]
        for first in pictures:
            for second in pictures:
                with self.subTest(first=first.getextrema(), second=second.getextrema()):
                    mass = sum(ImageStat.Stat(first).sum)
                    self.assertEqual(parallax._cost(first, second, 0, 0, mass), histogram_cost(first, second, 0, 0, mass))

    def test_equal_scores_keep_the_first_candidate_in_original_order(self):
        for value in (0, 255):
            with self.subTest(value=value):
                best, costs = self.assert_search_equal(Image.new("L", (4, 4), value), Image.new("L", (16, 16), value), 6, 6, (0, 0), 2)
                self.assertEqual(best, (-2, -2)); self.assertEqual(len(costs), 25)
                self.assertEqual(set(costs.values()), {0.0})

    def test_clipped_and_empty_searches_keep_their_candidates(self):
        other = noise((20, 18), 1219); patch_image = other.crop((0, 0, 8, 6))
        for x, y, centre, radius in [(0, 0, (0, 0), 3), (12, 12, (1, -1), 3), (-2, 4, (0, 0), 3), (0, 0, (-20, -20), 2)]:
            with self.subTest(x=x, y=y, centre=centre): self.assert_search_equal(patch_image, other, x, y, centre, radius)
        self.assertEqual(parallax._search(patch_image, other, 0, 0, (-20, -20), 2), (None, {}))

    def test_full_coarse_and_fine_windows_keep_exact_scores(self):
        for side, radius, centre in [(parallax.REGISTRATION["patch_px"] // 4, math.ceil(parallax.REGISTRATION["max_shift_px"] / 4), (0, 0)),
                                     (parallax.REGISTRATION["patch_px"], 3, (4, -4))]:
            with self.subTest(side=side, radius=radius):
                other = noise((144, 144), side); patch_image = other.crop((40, 40, 40 + side, 40 + side))
                _, costs = self.assert_search_equal(patch_image, other, 40, 40, centre, radius)
                self.assertEqual(len(costs), (2 * radius + 1) ** 2)

    def test_search_does_not_rebuild_histograms_for_every_candidate(self):
        other = noise((64, 64), 1910); patch_image = other.crop((24, 24, 40, 40))
        histogram = Image.Image.histogram; calls = []

        def counted(image, *args, **kwargs):
            calls.append(image.size)
            return histogram(image, *args, **kwargs)

        with patch.object(Image.Image, "histogram", counted):
            best, costs = parallax._search(patch_image, other, 24, 24, (0, 0), 9)
        self.assertEqual(best, (0, 0)); self.assertEqual(len(costs), 361)
        self.assertLessEqual(len(calls), 1, "361 scores must not allocate two weighted histograms each")


if __name__ == "__main__": unittest.main()
