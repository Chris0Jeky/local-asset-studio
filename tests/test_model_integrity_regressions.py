"""Damaged caches, ambiguous pins and backend affinity, using inert local bytes."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_preset_model_readiness as readiness
import test_model_library as library_tests


class FingerprintAndPinTests(unittest.TestCase):
    setUp = readiness.PresetModelReadinessTests.setUp
    studio = readiness.PresetModelReadinessTests.studio
    put = readiness.PresetModelReadinessTests.put
    pin = readiness.PresetModelReadinessTests.pin
    pinned_file = readiness.PresetModelReadinessTests.pinned_file
    cache = readiness.PresetModelReadinessTests.cache
    preflight = readiness.PresetModelReadinessTests.preflight
    health = readiness.PresetModelReadinessTests.health
    requirements = readiness.PresetModelReadinessTests.requirements

    def test_damaged_cache_roots_rehash_before_pin_comparison(self):
        pin, path = self.pinned_file(b'different'); studio = self.studio()
        target = self.root/'.runtime/model-fingerprints.json'
        for raw in (b'\xff', b'[1]', b'"x"', b'42', b'null', b'{broken'):
            with self.subTest(raw=raw):
                target.write_bytes(raw)
                with self.assertRaisesRegex(readiness.server.StudioError, 'does not match its library pin'):
                    self.preflight(studio)
                self.assertEqual(json.loads(target.read_text())[str(path.resolve())]['sha256'],
                                 hashlib.sha256(b'different').hexdigest())
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_damaged_cache_records_rehash_before_pin_comparison(self):
        pin, path = self.pinned_file(b'different'); studio = self.studio()
        target = self.root/'.runtime/model-fingerprints.json'
        valid = self.cache(path, pin['sha256'])
        records = [None, [1], 'x', dict(valid, sha256=None), dict(valid, sha256=''),
                   dict(valid, sha256='not-a-digest'), dict(valid, sha256='G'*64),
                   dict(valid, bytes=float(valid['bytes'])), dict(valid, mtime_ns=float(valid['mtime_ns']))]
        for record in records:
            with self.subTest(record=record):
                target.write_text(json.dumps({str(path.resolve()): record}))
                with self.assertRaisesRegex(readiness.server.StudioError, 'does not match its library pin'):
                    self.preflight(studio)
                self.assertEqual(json.loads(target.read_text())[str(path.resolve())]['sha256'],
                                 hashlib.sha256(b'different').hexdigest())

    def test_invalid_digest_is_not_readiness_evidence_and_read_does_not_hash(self):
        pin, path = self.pinned_file(); studio = self.studio()
        for digest in ('bad', 'G'*64, ['x']):
            with self.subTest(digest=digest):
                self.cache(path, digest)
                with patch.object(readiness.server, 'digest_file', side_effect=AssertionError('read must not hash')):
                    self.assertEqual(self.health(studio)['pin_mismatch'], {})
        (self.root/'.runtime/model-fingerprints.json').write_bytes(b'\xff')
        self.assertEqual(studio.model_fingerprints(), {})

    def test_valid_stat_fresh_cache_is_reused_without_rehashing(self):
        pin, path = self.pinned_file(); studio = self.studio(); self.cache(path, pin['sha256'])
        with patch.object(readiness.server, 'digest_file', side_effect=AssertionError('unexpected rehash')):
            self.assertEqual(self.preflight(studio)['models'][0]['sha256'], pin['sha256'])

    def test_duplicate_pin_conflict_blocks_production_even_when_bytes_match(self):
        pin, path = self.pinned_file(); self.manifest.append(dict(pin, id='duplicate'))
        studio = self.studio()
        row = self.requirements(studio)[pin['file']]
        self.assertIn('Multiple exact-path pins', row['note'])
        with self.assertRaisesRegex(readiness.server.StudioError, 'Multiple exact-path pins'):
            self.preflight(studio)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_case_insensitive_pin_match_enforces_digest_without_renaming_requested_file(self):
        pin, path = self.pinned_file(b'different'); pin['file'] = 'loras/PINNED.safetensors'
        studio = self.studio()
        import model_requirements
        with patch.object(model_requirements, 'path_key', side_effect=lambda value: value.casefold(), create=True):
            row = self.requirements(studio)['loras/pinned.safetensors']
            self.assertEqual(row['asset_id'], pin['id'])
            with self.assertRaisesRegex(readiness.server.StudioError, 'does not match its library pin'):
                self.preflight(studio)

    def test_case_sensitive_paths_remain_distinct(self):
        pin, path = self.pinned_file(); self.manifest.append(dict(pin, id='upper', file='loras/PINNED.safetensors'))
        studio = self.studio()
        import model_requirements
        with patch.object(model_requirements, 'path_key', side_effect=lambda value: value, create=True):
            self.assertEqual(self.preflight(studio)['models'][0]['file'], pin['file'])

    def test_duplicate_case_aliases_are_conflicts_on_case_insensitive_hosts(self):
        pin, path = self.pinned_file(); self.manifest.append(dict(pin, id='upper', file='loras/PINNED.safetensors'))
        studio = self.studio()
        import model_requirements
        with patch.object(model_requirements, 'path_key', side_effect=lambda value: value.casefold(), create=True):
            with self.assertRaisesRegex(readiness.server.StudioError, 'Multiple exact-path pins'):
                self.preflight(studio)

    def test_non_primary_root_does_not_inherit_cached_pin_mismatch(self):
        pin, path = self.pinned_file(b'different'); studio = self.studio()
        from model_requirements import requirements
        other = self.root/'isolated/models'; other_path = self.put(pin['file'], b'other', root=other)
        info = other_path.stat()
        rows = requirements(studio.library, self.preset, self.graph, other, fingerprints={str(other_path):
                            {'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns, 'sha256': 'b'*64}})
        self.assertIsNone(rows[0]['pin_mismatch']); self.assertFalse(rows[0]['installable'])


class BackendAffinityTests(unittest.TestCase):
    setUp = library_tests.ModelLibraryTests.setUp
    tearDown = library_tests.ModelLibraryTests.tearDown

    def write_manifest(self, **changes):
        self.asset.update(changes)
        (self.root/'models/library.json').write_text(json.dumps({'assets': [self.asset]}))

    def test_wrong_backend_refuses_before_any_install_side_effect(self):
        self.write_manifest(backend='qwen21')
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
        with patch.object(library_tests.models, 'urlopen', side_effect=AssertionError('no network')), \
             patch.object(library_tests.models, 'InstallLease', side_effect=AssertionError('no lease')):
            for action in (self.lib.install, self.lib.start_install):
                with self.subTest(action=action.__name__), self.assertRaisesRegex(ValueError, 'qwen21'):
                    action('demo')
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))
        self.assertFalse(self.lib.lock.locked())

    def test_wrong_backend_presence_and_old_receipt_cannot_claim_verified(self):
        with patch.object(library_tests.models, 'urlopen', return_value=library_tests.Reply(self.body)):
            self.lib.install('demo')
        self.write_manifest(backend='qwen21')
        row = self.lib.snapshot()['assets'][0]
        self.assertTrue(row['present']); self.assertFalse(row['installable']); self.assertFalse(row['verified'])
        self.assertIn('qwen21', row['install_note'])
        with self.assertRaisesRegex(ValueError, 'qwen21'): self.lib.install('demo')

    def test_matching_backend_and_legacy_all_remain_installable(self):
        self.write_manifest(backend='qwen21')
        lib = library_tests.models.ModelLibrary(self.root, self.root/'isolated', backend_id='qwen21')
        with patch.object(library_tests.models, 'urlopen', return_value=library_tests.Reply(self.body)):
            lib.install('demo')
        self.assertTrue(lib.snapshot()['assets'][0]['verified'])
        self.write_manifest(backend='all'); self.assertIsNone(self.lib.install_block(self.asset))

    def test_invalid_affinity_is_not_silently_ignored(self):
        for value in (None, [], {}, '', 1, 'ALL', '../qwen21'):
            with self.subTest(value=value):
                self.write_manifest(backend=value)
                with self.assertRaisesRegex(ValueError, 'backend'): self.lib.manifest()

    def test_qwen_pins_declare_isolated_backend(self):
        manifest = json.loads((Path(__file__).resolve().parents[1]/'models/library.json').read_text())
        pins = [asset for asset in manifest['assets'] if asset['id'].startswith('qwen-image-21-')]
        self.assertEqual(len(pins), 6)
        self.assertTrue(all(asset.get('backend') == 'qwen21' for asset in pins))
