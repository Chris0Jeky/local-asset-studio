"""Causal editor regressions and the real HTTP/Python-to-JavaScript boundary."""
import json
import shutil
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path
import test_asset_metadata_http as fixture

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for editor contracts')
class ConflictEnvelopeContracts(unittest.TestCase):
    def test_editor_contracts(self):
        result = subprocess.run([shutil.which('node'), '--test', str(ROOT / 'tests/asset_conflict_envelope.cjs')],
                                capture_output=True, text=True, encoding='utf-8', timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for cross-runtime contracts')
class RealConflictEnvelope(unittest.TestCase):
    setUp = fixture.AssetMetadataHTTP.setUp
    tearDown = fixture.AssetMetadataHTTP.tearDown
    request = fixture.AssetMetadataHTTP.request
    command = fixture.AssetMetadataHTTP.command

    def project(self, status, data, command):
        script = """const {setup}=require('./tests/asset_detail_contracts.cjs');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8')),s=setup();
console.log(s.run('JSON.stringify(assetRevisionConflict('+JSON.stringify({status:input.status,data:input.data})+','+JSON.stringify(input.command)+'))'));
"""
        result = subprocess.run([shutil.which('node'), '-e', script], cwd=ROOT,
                                input=json.dumps(dict(status=status, data=data, command=command)),
                                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_actual_conflict_matches_request_scope_and_unicode_metadata(self):
        scope = self.store.snapshot()['workspace_id']
        winner = self.command(workspace_id=scope)
        winner.update(title='界' * 200, notes='😀' * 8000)
        status, _, _ = self.request('POST', '/api/assets/update', winner)
        self.assertEqual(status, 200)
        stale = self.command(workspace_id=scope)
        status, data, _ = self.request('POST', '/api/assets/update', stale)
        self.assertEqual(status, 409)
        result = self.project(status, data, stale)
        self.assertEqual(result['current'], data['current'])
        self.assertEqual(result['request_id'], stale['request_id'])
        self.assertEqual(result['conflict_ids'], [self.asset])
        self.assertIsNone(self.project(status, dict(data, request_id=winner['request_id']), stale))
        # The committed command replays its receipt before current revision checks.
        status, replay, _ = self.request('POST', '/api/assets/update', winner)
        self.assertEqual((status, replay['status']), (200, 'applied'))
        self.assertEqual(self.store.get(self.asset)['metadata_revision'], 1)

    def test_long_registered_title_keeps_conflict_comparison(self):
        # An AV project name may reach 1,000 characters; register() copies it past the 200-character edit limit.
        source = Path(self.temp.name) / 'image.png'
        asset = self.store.register({'id': 'av', 'preset_name': '界' * 1000, 'outputs': [{'filename': 'image.png'}]}, 0, source)
        self.assertEqual(self.store.get(asset)['title'], '界' * 1000 + ' · 1')
        scope = self.store.snapshot()['workspace_id']
        winner, stale = (dict(self.command(workspace_id=scope), ids=[asset], expected_revisions={asset: 0}) for _ in range(2))
        self.assertEqual(self.request('POST', '/api/assets/update', winner)[0], 200)
        status, data, _ = self.request('POST', '/api/assets/update', stale)
        self.assertEqual(status, 409)
        self.assertEqual(self.project(status, data, stale)['current'], data['current'])
        excessive = self.store.register({'id': 'huge', 'preset_name': 'x' * 5000, 'outputs': [{'filename': 'image.png'}]}, 0, source)
        title = self.store.get(excessive)['title']
        self.assertEqual((len(title), title[-4:]), (1024, ' · 1'))
        current = dict(data['current'][0], title='x' * 1025)
        self.assertIsNone(self.project(status, dict(data, current=[current]), stale))

    def test_actual_missing_target_cannot_become_rebase_authority(self):
        command = self.command(workspace_id=self.store.snapshot()['workspace_id'])
        with self.store.connection() as db:
            db.execute('DELETE FROM assets WHERE id=?', (self.asset,))
        status, data, _ = self.request('POST', '/api/assets/update', command)
        self.assertEqual(status, 409)
        self.assertEqual(data['missing_ids'], [self.asset])
        self.assertIsNone(self.project(status, data, command))

    def test_projection_uses_utf8_under_a_legacy_default_codec(self):
        scope = self.store.snapshot()['workspace_id']
        command = self.command(workspace_id=scope)
        current = dict(self.store.metadata(self.asset, scope), metadata_revision=1,
                       title='界', notes='😀')
        data = dict(code='asset_revision_conflict', workspace_id=scope,
                    request_id=command['request_id'], conflict_ids=[self.asset],
                    missing_ids=[], current=[current])
        # Inject the Windows default without changing Node's actual UTF-8 bytes.
        with patch('subprocess._text_encoding', return_value='cp1252'):
            result = self.project(409, data, command)
        self.assertEqual(result['current'], [current])
