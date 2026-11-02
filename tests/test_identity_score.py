import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location("identity_score", pathlib.Path(__file__).parents[1] / "scripts" / "identity_score.py")
identity_score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity_score)


class GroupMeans(unittest.TestCase):
    def test_groups_by_capture_and_ignores_the_rest(self):
        scores = {"a/rg1.0_s1.png": 0.2, "a/rg1.0_s2.png": 0.4, "a/rg4.5_s1.png": 0.1, "a/other.png": 0.9}
        self.assertEqual(identity_score.group_means(scores, r"rg([0-9.]+)_"), {
            "1.0": {"n": 2, "mean": 0.3, "min": 0.2, "max": 0.4},
            "4.5": {"n": 1, "mean": 0.1, "min": 0.1, "max": 0.1},
        })


if __name__ == "__main__":
    unittest.main()
