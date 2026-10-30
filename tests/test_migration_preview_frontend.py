"""Execute the Library's read-only migration preview contracts (#1678) against the shipped Workspace script."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
class MigrationPreviewFrontendTests(unittest.TestCase):
    def test_library_migration_preview_contracts(self):
        result = subprocess.run([shutil.which('node'), '--test', 'tests/migration_preview_frontend.cjs'],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
