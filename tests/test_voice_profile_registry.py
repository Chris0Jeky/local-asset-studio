"""Durable narration revisions are a mutation protocol, not catalogue overlays."""
import copy
import importlib
import importlib.util
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import voice_profile as vp
from test_voice_profile_contract import accepted_ember, profile_by_id


def competing_writer(path, command, barrier, results):
    import voice_profile_registry as registry
    try:
        barrier.wait(timeout=15)
        results.put(('ok', registry.update_registry(Path(path), command)))
    except Exception as exc:
        results.put(('refused', type(exc).__name__))


class RegistryContracts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('voice_profile_registry'),
                             'the owned registry update boundary is missing')
        self.r = importlib.import_module('voice_profile_registry')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name).resolve() / 'registry.json'
        self.catalog = vp.load_catalog()
        self.base = profile_by_id(self.catalog, 'ember-brief-v1')

    def command(self, request_id='update-a', predecessor=None):
        predecessor = self.base if predecessor is None else predecessor
        return {
            'schema_version': 1, 'request_id': request_id,
            'expected_registry_sha256': self.r.inspect_registry(self.path)['registry_sha256'],
            'expected_profile_sha256': vp.profile_digest(predecessor),
            'profile': accepted_ember(predecessor, vp.profile_digest(predecessor)),
        }

    def test_inspect_missing_registry_is_read_only(self):
        first = self.r.inspect_registry(self.path)
        self.assertEqual(first, self.r.inspect_registry(self.path))
        self.assertEqual(first['profiles'], self.catalog['profiles'])
        self.assertEqual(first['receipts'], [])
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_two_successors_and_historical_replay_use_exact_local_predecessor(self):
        first = self.command()
        receipt = self.r.update_registry(self.path, first)
        self.assertEqual(receipt['previous_profile_sha256'], vp.profile_digest(self.base))
        self.assertEqual(receipt['resulting_profile_sha256'], vp.profile_digest(first['profile']))
        second = self.command('update-b', first['profile'])
        self.r.update_registry(self.path, second)
        before = self.path.read_bytes()
        self.assertEqual(self.r.update_registry(self.path, first), receipt)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(profile_by_id(self.r.inspect_registry(self.path), self.base['id']), second['profile'])
        self.assertEqual(len(self.r.inspect_registry(self.path)['receipts']), 2)
        self.assertEqual(first['profile']['revision'], 2)  # caller data is not rewritten

    def test_stale_registry_or_profile_cannot_mutate_or_consume_request_id(self):
        first = self.command()
        stale = self.command('update-b')
        self.r.update_registry(self.path, first)
        before = self.path.read_bytes()
        with self.assertRaises(vp.VoiceProfileError): self.r.update_registry(self.path, stale)
        stale['expected_registry_sha256'] = self.r.inspect_registry(self.path)['registry_sha256']
        with self.assertRaises(vp.VoiceProfileError): self.r.update_registry(self.path, stale)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNone(self.r.get_receipt(self.path, 'update-b'))
        self.r.update_registry(self.path, self.command('update-b', first['profile']))

    def test_request_id_reuse_with_changed_content_is_refused_even_with_fresh_cas(self):
        first = self.command()
        self.r.update_registry(self.path, first)
        changed = self.command(first['request_id'], first['profile'])
        before = self.path.read_bytes()
        with self.assertRaisesRegex(vp.VoiceProfileError, 'request'):
            self.r.update_registry(self.path, changed)
        self.assertEqual(self.path.read_bytes(), before)

    def test_predecessor_and_strictly_increasing_revision_are_independently_checked(self):
        for kind in ('same', 'lower', 'boolean', 'missing-predecessor', 'wrong-predecessor'):
            command = self.command()
            if kind == 'same': command['profile']['revision'] = 1
            if kind == 'lower': command['profile']['revision'] = 0
            if kind == 'boolean': command['profile']['revision'] = True
            if kind == 'missing-predecessor': del command['profile']['supersedes_profile_sha256']
            if kind == 'wrong-predecessor': command['profile']['supersedes_profile_sha256'] = '0' * 64
            with self.subTest(kind=kind), self.assertRaises(vp.VoiceProfileError):
                self.r.update_registry(self.path, command)
            self.assertFalse(self.path.exists())

    def test_read_only_resolver_consumes_v2_without_weakening_producer_admission(self):
        command = self.command()
        self.r.update_registry(self.path, command)
        before = self.path.read_bytes()
        with patch.object(self.r.io, 'writer_lock', side_effect=AssertionError('read locked')):
            binding = vp.resolve_profile(self.base['id'], 'calm-brief', registry_path=self.path)
            self.assertEqual(binding['profile_sha256'], vp.profile_digest(command['profile']))
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaisesRegex(vp.VoiceProfileError, 'unsupported adapter'):
            vp.require_executable(binding)

    def test_legacy_overlay_is_readable_but_never_implicitly_migrated_by_writer(self):
        command = self.command()
        self.path.write_text(json.dumps({'schema_version': 1, 'profiles': [command['profile']]}), encoding='utf-8')
        before = self.path.read_bytes()
        self.assertEqual(vp.load_registry(self.path, self.catalog)['profiles'][1], command['profile'])
        with self.assertRaisesRegex(vp.VoiceProfileError, 'legacy|version'):
            self.r.update_registry(self.path, command)
        self.assertEqual(before, self.path.read_bytes())

    def test_corrupt_receipt_or_rehashed_transition_is_rejected_without_repair(self):
        self.r.update_registry(self.path, self.command())
        valid = self.path.read_bytes()
        for field, value in [('sequence', True), ('resulting_profile_sha256', '0' * 64)]:
            state = json.loads(valid)
            state['transitions'][0]['receipt'][field] = value
            self.path.write_text(json.dumps(state), encoding='utf-8')
            before = self.path.read_bytes()
            with self.subTest(field=field), self.assertRaises(vp.VoiceProfileError):
                self.r.inspect_registry(self.path)
            self.assertEqual(self.path.read_bytes(), before)
        self.path.write_bytes(valid)
        state = json.loads(valid)
        state['transitions'][0]['command']['profile']['revision'] = 1
        self.path.write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaises(vp.VoiceProfileError): self.r.inspect_registry(self.path)

    def test_changed_catalogue_blocks_resolution_and_updates(self):
        command = self.command()
        self.r.update_registry(self.path, command)
        changed = copy.deepcopy(self.catalog)
        changed['profiles'][0]['name'] += ' changed'
        with patch.object(vp, 'load_catalog', return_value=changed):
            with self.assertRaisesRegex(vp.VoiceProfileError, 'catalog'):
                self.r.inspect_registry(self.path)
        with self.assertRaises(vp.VoiceProfileError): vp.load_registry(self.path, changed)

    def test_json_ambiguity_and_unknown_versions_fail_closed(self):
        for raw in (b'{"schema_version":2,"schema_version":2}', b'{"schema_version":NaN}',
                    b'{"schema_version":true}', b'{"schema_version":3}', b'[]', b'\xff',
                    b'[' * 2000 + b']' * 2000):
            with self.subTest(raw=raw[:60]):
                self.path.write_bytes(raw)
                with self.assertRaises(vp.VoiceProfileError): self.r.inspect_registry(self.path)
                self.assertEqual(raw, self.path.read_bytes())

    def test_full_journal_refuses_new_commands_but_retains_exact_replay(self):
        first = self.command()
        with patch.object(self.r, 'MAX_TRANSITIONS', 1):
            receipt = self.r.update_registry(self.path, first)
            second = self.command('update-b', first['profile'])
            before = self.path.read_bytes()
            with self.assertRaisesRegex(vp.VoiceProfileError, 'full'):
                self.r.update_registry(self.path, second)
            self.assertEqual(receipt, self.r.update_registry(self.path, first))
            self.assertEqual(before, self.path.read_bytes())

    def test_byte_capacity_refuses_before_publication(self):
        command = self.command()
        with patch.object(self.r, 'MAX_REGISTRY_BYTES', 200):
            with self.assertRaisesRegex(vp.VoiceProfileError, 'byte'):
                self.r.update_registry(self.path, command)
        self.assertFalse(self.path.exists())

    def test_flush_and_replace_failure_preserve_previous_profile_and_receipts(self):
        first = self.command()
        self.r.update_registry(self.path, first)
        second = self.command('update-b', first['profile'])
        before = self.path.read_bytes()
        for boundary in ('fsync', 'replace'):
            with self.subTest(boundary=boundary):
                with patch.object(self.r.io.os, boundary, side_effect=OSError('injected')):
                    with self.assertRaises(vp.VoiceProfileError): self.r.update_registry(self.path, second)
                self.assertEqual(self.path.read_bytes(), before)
                self.assertIsNone(self.r.get_receipt(self.path, 'update-b'))
        self.r.update_registry(self.path, second)

    def test_lost_acknowledgement_after_replace_replays_original_receipt(self):
        command = self.command()
        replace = self.r.io.os.replace
        def replaced_then_lost(source, destination):
            replace(source, destination)
            raise OSError('replacement committed; acknowledgement lost')
        with patch.object(self.r.io.os, 'replace', side_effect=replaced_then_lost):
            with self.assertRaises(self.r.RegistryUnconfirmed): self.r.update_registry(self.path, command)
        before = self.path.read_bytes()
        receipt = self.r.get_receipt(self.path, command['request_id'])
        self.assertIsNotNone(receipt)
        self.assertEqual(self.r.update_registry(self.path, command), receipt)
        self.assertEqual(self.path.read_bytes(), before)

    def test_two_real_spawned_writers_have_exactly_one_winner(self):
        first, second = self.command('writer-a'), self.command('writer-b')
        ctx = multiprocessing.get_context('spawn')
        barrier, results = ctx.Barrier(3), ctx.Queue()
        children = [ctx.Process(target=competing_writer, args=(str(self.path), c, barrier, results))
                    for c in (first, second)]
        try:
            for child in children: child.start()
            barrier.wait(timeout=15)
            outcomes = [results.get(timeout=15) for _ in children]
            for child in children:
                child.join(timeout=10)
                self.assertEqual(child.exitcode, 0)
            self.assertEqual(sorted(o[0] for o in outcomes), ['ok', 'refused'])
            self.assertEqual(len(self.r.inspect_registry(self.path)['receipts']), 1)
        finally:
            for child in children:
                if child.is_alive(): child.terminate()
                child.join(timeout=5)
            results.close(); results.join_thread()

    def test_read_only_v2_resolver_refuses_symlinked_registry(self):
        command = self.command()
        self.r.update_registry(self.path, command)
        link = self.path.with_name('alias.json')
        try: link.symlink_to(self.path)
        except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
        with self.assertRaises(vp.VoiceProfileError):
            vp.resolve_profile(self.base['id'], 'calm-brief', registry_path=link)

    def test_writer_does_not_promote_experimental_profile_or_other_catalogue_records(self):
        state = self.r.inspect_registry(self.path)
        next_profile = copy.deepcopy(self.base)
        next_profile.update(revision=2, supersedes_profile_sha256=vp.profile_digest(self.base))
        next_profile['name'] = 'Draft revision'
        command = self.command(); command['profile'] = next_profile
        self.r.update_registry(self.path, command)
        now = self.r.inspect_registry(self.path)
        self.assertEqual(now['profiles'][0], state['profiles'][0])
        self.assertEqual(now['profiles'][1]['status'], 'experimental')
        binding = vp.resolve_profile(self.base['id'], 'calm-brief', registry_path=self.path)
        with self.assertRaisesRegex(vp.VoiceProfileError, 'experimental'):
            vp.require_executable(binding)

    def test_duplicate_or_reordered_transitions_cannot_pass_self_consistent_json(self):
        first = self.command(); self.r.update_registry(self.path, first)
        self.r.update_registry(self.path, self.command('update-b', first['profile']))
        valid = json.loads(self.path.read_bytes())
        for transitions in ([valid['transitions'][0]] * 2, list(reversed(valid['transitions']))):
            state = dict(valid, transitions=transitions)
            self.path.write_bytes(vp.canonical_bytes(state))
            with self.assertRaises(vp.VoiceProfileError): self.r.inspect_registry(self.path)

    def test_failed_receipt_serialization_cannot_publish_new_profile(self):
        first = self.command(); self.r.update_registry(self.path, first)
        next_command = self.command('update-b', first['profile'])
        before = self.path.read_bytes(); encode = vp.canonical_bytes
        def refuse_receipt(value):
            if isinstance(value, dict) and value.get('transitions'):
                if value['transitions'][-1]['receipt']['request_id'] == 'update-b':
                    raise vp.VoiceProfileError('receipt encoding failed')
            return encode(value)
        with patch.object(vp, 'canonical_bytes', side_effect=refuse_receipt):
            with self.assertRaisesRegex(vp.VoiceProfileError, 'receipt encoding'):
                self.r.update_registry(self.path, next_command)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNone(self.r.get_receipt(self.path, 'update-b'))

    def test_invalid_commands_send_zero_storage_writes(self):
        for mutate in (lambda c: c.update(schema_version=True), lambda c: c.update(request_id='../x'),
                       lambda c: c.update(extra=True), lambda c: c['profile'].update(name='\ud800'),
                       lambda c: c['profile'].update(status=[])):
            command = self.command(); mutate(command)
            with self.subTest(command=str(command)[:100]):
                with patch.object(self.r.io, 'writer_lock', side_effect=AssertionError('lock before validation')):
                    with self.assertRaises(vp.VoiceProfileError): self.r.update_registry(self.path, command)
                self.assertFalse(self.path.exists())


if __name__ == '__main__': unittest.main()
