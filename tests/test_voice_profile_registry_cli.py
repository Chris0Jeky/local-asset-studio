"""Exercise the public command and persisted transition boundary without synthesis."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import voice_profile as vp
import voice_profile_registry as registry
from test_voice_profile_contract import accepted_ember, profile_by_id

ROOT = Path(__file__).resolve().parents[1]


class RegistryPublicBoundary(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.path = self.root / 'registry.json'

    def command(self, request_id='revision-a'):
        current = registry.inspect_registry(self.path)
        profile = profile_by_id(current, 'ember-brief-v1')
        return {'schema_version': 1, 'request_id': request_id,
                'expected_registry_sha256': current['registry_sha256'],
                'expected_profile_sha256': vp.profile_digest(profile),
                'profile': accepted_ember(profile, vp.profile_digest(profile))}

    def cli(self, *arguments):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/voice_profile_registry_cli.py'),
                                 '--registry', str(self.path), *arguments],
                                capture_output=True, text=True, timeout=10)
        return result.returncode, json.loads(result.stdout)

    def test_cli_inspection_update_and_restart_replay(self):
        code, inspection = self.cli('inspect')
        self.assertEqual(code, 0); self.assertEqual(inspection['result']['receipts'], [])
        self.assertEqual(list(self.root.iterdir()), [])
        command = self.command(); source = self.root / 'command.json'
        source.write_bytes(vp.canonical_bytes(command))
        code, updated = self.cli('update', '--command', str(source))
        self.assertEqual(code, 0)
        before = self.path.read_bytes()
        self.assertEqual(self.cli('update', '--command', str(source)), (0, updated))
        self.assertEqual(self.cli('receipt', command['request_id']), (0, updated))
        self.assertEqual(self.path.read_bytes(), before)
        source.write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
        code, refused = self.cli('update', '--command', str(source))
        self.assertEqual(code, 2); self.assertEqual(refused['status'], 'refused')
        self.assertEqual(self.path.read_bytes(), before)

    def test_cli_stale_command_does_not_mutate_or_claim_success(self):
        first = self.command(); stale = self.command('stale-b')
        registry.update_registry(self.path, first)
        before = self.path.read_bytes(); source = self.root / 'command.json'
        source.write_bytes(vp.canonical_bytes(stale))
        code, refused = self.cli('update', '--command', str(source))
        self.assertEqual(code, 2); self.assertEqual(refused['status'], 'refused')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.cli('receipt', 'stale-b'), (0, {'status': 'ok', 'result': None}))

    def test_predecessor_fields_are_independent_after_first_local_revision(self):
        registry.update_registry(self.path, self.command())
        second = self.command('revision-b'); before = self.path.read_bytes()
        for target in ('expected_profile_sha256', 'supersedes_profile_sha256'):
            wrong = copy.deepcopy(second)
            if target == 'expected_profile_sha256': wrong[target] = '0' * 64
            else: wrong['profile'][target] = '0' * 64
            with self.subTest(target=target), self.assertRaises(vp.VoiceProfileError):
                registry.update_registry(self.path, wrong)
            self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNone(registry.get_receipt(self.path, 'revision-b'))
        registry.update_registry(self.path, second)

    def test_receipt_and_command_chain_tampering_is_not_repaired(self):
        registry.update_registry(self.path, self.command())
        valid = json.loads(self.path.read_bytes())
        for container, field, value in (
                ('receipt', 'previous_profile_sha256', '0' * 64),
                ('receipt', 'previous_registry_sha256', '0' * 64),
                ('receipt', 'request_id', 'different-request'),
                ('receipt', 'sequence', 3),
                ('command', 'expected_registry_sha256', '0' * 64),
                ('command', 'expected_profile_sha256', '0' * 64)):
            changed = copy.deepcopy(valid); changed['transitions'][0][container][field] = value
            raw = vp.canonical_bytes(changed); self.path.write_bytes(raw)
            with self.subTest(container=container, field=field), self.assertRaises(vp.VoiceProfileError):
                registry.inspect_registry(self.path)
            self.assertEqual(self.path.read_bytes(), raw)

    def test_identical_external_replacement_after_publication_is_unconfirmed(self):
        command = self.command(); replace = os.replace
        def changed(source, destination):
            replace(source, destination)
            external = self.root / 'external.json'
            external.write_bytes(self.path.read_bytes()); replace(external, self.path)
        with patch.object(registry.io.os, 'replace', side_effect=changed):
            with self.assertRaises(registry.RegistryUnconfirmed):
                registry.update_registry(self.path, command)
        receipt = registry.get_receipt(self.path, command['request_id'])
        self.assertEqual(registry.update_registry(self.path, command), receipt)


if __name__ == '__main__': unittest.main()
