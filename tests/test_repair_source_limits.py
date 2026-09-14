"""Regression for aggregate packet limits at the read-only verification seam."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import repair_source as source


class RepairSourceLimitTests(unittest.TestCase):
    def test_verification_uses_the_same_aggregate_artifact_bound_as_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); original = root / 'input.png'; packet = root / 'packet'
            with Image.new('RGB', (3, 2), (50, 90, 110)) as image:
                image.save(original)
            source.capture(original, packet)
            total = (packet / 'source.png').stat().st_size + (packet / 'normalized.png').stat().st_size
            with patch.object(source, 'MAX_OUTPUT_BYTES', total - 1):
                with self.assertRaises(ValueError):
                    source.verify(packet)


if __name__ == '__main__': unittest.main()
