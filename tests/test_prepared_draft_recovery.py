"""Real prepared plans survive SQLite -> browser normalization -> server preflight.

Uses generated inert pictures and stopped fixture workers, never an engine or model.
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import test_tiles as tile_fixture
import test_parallax as parallax_fixture

ROOT = Path(__file__).resolve().parents[1]


def round_trip(studio, payload):
    recipe = dict(copy.deepcopy(payload), preset=payload['preset_id'], batch=payload['batch_count'])
    saved = studio.assets.save_setup({'name': 'Prepared route regression', 'recipe': recipe})
    stored = next(row['recipe'] for row in studio.assets.setups() if row['id'] == saved['id'])
    script = "const U=require('./app/static/studio-core.js');let s='';process.stdin.on('data',b=>s+=b);process.stdin.on('end',()=>{const d=U.normalizeDraft(JSON.parse(s));if(!d)throw Error('invalid draft');console.log(JSON.stringify(d.recipe));});"
    result = subprocess.run([shutil.which('node'), '-e', script], cwd=ROOT, input=json.dumps({'version': 1, 'updatedAt': 1, 'recipe': stored}), text=True, capture_output=True, timeout=15, check=True)
    restored = json.loads(result.stdout)
    return dict(restored, preset_id=restored['preset'], batch_count=restored['batch'])


@unittest.skipUnless(shutil.which('node'), 'Node is required for the actual browser normalizer')
class TileRecoveryTests(unittest.TestCase):
    setUp = tile_fixture.RouteTests.setUp
    studio = tile_fixture.RouteTests.studio
    source = tile_fixture.RouteTests.source
    payload = tile_fixture.RouteTests.payload

    def test_real_tile_plan_survives_storage_and_still_rejects_changed_bytes(self):
        studio = self.studio()
        prepared = tile_fixture.tiles.prepare(studio, {'asset_id': self.source(studio)['id']})
        before = set(studio.jobs)
        restored = round_trip(studio, self.payload(prepared))
        self.assertEqual(restored['tile'], prepared['plan'])
        studio.prepare(restored)
        (studio.experiments / 'uploads' / prepared['file']).write_bytes(tile_fixture.png(tile_fixture.Image.new('RGBA', (256, 256))))
        with self.assertRaisesRegex(ValueError, 'changed or is missing'):
            studio.prepare(restored)
        self.assertEqual(set(studio.jobs), before)
        self.assertEqual(studio.requests, [])


@unittest.skipUnless(shutil.which('node'), 'Node is required for the actual browser normalizer')
class ParallaxRecoveryTests(unittest.TestCase):
    setUp = parallax_fixture.RouteTests.setUp
    studio = parallax_fixture.RouteTests.studio
    source = parallax_fixture.RouteTests.source
    prepared = parallax_fixture.RouteTests.prepared
    payload = parallax_fixture.RouteTests.payload

    def test_both_stages_survive_storage_without_weakening_plan_identity(self):
        studio = self.studio()
        prepared = self.prepared(studio)
        before = set(studio.jobs)
        for stage in ('plate', 'isolate'):
            with self.subTest(stage=stage):
                body = self.payload(prepared)
                body['parallax'] = dict(body['parallax'], stage=stage)
                restored = round_trip(studio, body)
                self.assertEqual(restored['parallax'], body['parallax'])
                studio.prepare(restored)
                restored['parallax']['objects'] = 'a different foreground'
                with self.assertRaisesRegex(ValueError, 'altered'):
                    studio.prepare(restored)
        self.assertEqual(set(studio.jobs), before)
        self.assertEqual(studio.requests, [])


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend regressions')
class PreparedFrontendTests(unittest.TestCase):
    def test_saved_application_and_envelope_contracts(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/prepared_draft_recovery.cjs')], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('prepared-draft checks passed', result.stdout)
