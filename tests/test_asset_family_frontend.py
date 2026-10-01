"""Run pure family/recall UI and public-owner adapter contracts through Node."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
class AssetFamilyFrontendTests(unittest.TestCase):
    def test_recall_identity_seed_and_stale_response_contracts(self):
        result = subprocess.run(['node', 'tests/test_asset_family_ui.cjs'], cwd=ROOT,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_public_create_owner_and_presentation_adapter_contracts(self):
        result = subprocess.run(['node', '--test', 'tests/test_asset_family_adapter.cjs'], cwd=ROOT,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
