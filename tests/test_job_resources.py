"""CPU-only synthetic observations: no process discovery, services or generation."""
import copy
from contextlib import nullcontext
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import test_performance_history as fixtures
import job_resources as resources


def sample(index=0):
    value = fixtures.sample(index); value.pop('private_extra')
    return value


def intent(identifier='fixture-job', index=0):
    job = {'id': identifier, 'comfy_url': 'http://127.0.0.1:8188',
           'controls': {'positive': 'PRIVATE_PROMPT'}, 'references': [{'path': 'PRIVATE_INPUT'}]}
    return resources.event_snapshot('intent', job, index=index, graph={'1': {'inputs': {'seed': index}}})


class SyntheticSampler:
    def __init__(self, *_): self.count = 0; self.binding = {'fixture': True}
    def sample(self):
        result = sample(self.count); self.count += 1
        return result


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.managers = []
        self.addCleanup(self.stop_observers)

    def stop_observers(self):
        for manager in self.managers:
            if manager.last: manager.last.stop.set()
            if manager.thread: manager.thread.join(timeout=5)

    def manager(self, **kwargs):
        options = dict(samples=1, interval=1, sampler_factory=SyntheticSampler,
                       source_reader=lambda _: {'fixture': True, 'loaded_code_matches_commit': None})
        options.update(kwargs)
        result = resources.JobResourceObservations(self.root, self.root, NS(profiles={}), **options)
        self.managers.append(result); return result

    def wait_samples(self, manager, count):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            path = manager.last.path
            if path and (path / 'profile.jsonl').is_file():
                raw = (path / 'profile.jsonl').read_bytes()
                if len(raw.splitlines()) >= count + 1: return raw
            if manager.last.done.wait(0.01): self.fail(str(manager.last.result))
        self.fail('Synthetic observer did not write expected samples')

    def finish(self, manager, status='completed'):
        manager.finish(resources.event_snapshot('finish', {'id': manager.last.job_id, 'status': status}))
        self.assertTrue(manager.last.done.wait(5), 'Finalization must finish in the fixture')
        manager.thread.join(timeout=5)
        return manager.last.path

    def test_complete_receipt_and_existing_reducer_share_exact_bytes(self):
        sampler = SyntheticSampler(); manager = self.manager(samples=2, sampler_factory=lambda *_: sampler)
        manager.intent(intent()); self.wait_samples(manager, 2)
        manager.accepted(resources.event_snapshot('accepted', {'id': 'fixture-job'}, index=0, prompt_id='once'))
        directory = self.finish(manager)
        raw = (directory / 'profile.jsonl').read_bytes()
        summary = json.loads((directory / 'summary.json').read_text())
        self.assertEqual(summary, resources.summarize_resource_profile(io.BytesIO(raw)))
        self.assertEqual(summary['source']['receipt_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(summary['sampling']['observed'], 2); self.assertTrue(summary['sampling']['complete'])
        self.assertEqual(sampler.count, 2, 'Waiting for job exit must not refill sampling')
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([event['event'] for event in events], ['intent', 'accepted', 'finish'])
        self.assertEqual(events[1]['prompt_id'], 'once')
        context = json.loads((directory / 'context.json').read_text())
        self.assertIsNone(context['model_content_identity']); self.assertIsNone(context['warmth'])
        self.assertNotIn('PRIVATE', (directory / 'context.json').read_text())
        self.assertTrue(manager.last.result['summary_available'])
        result = json.loads((directory / 'result.json').read_text())
        self.assertEqual(result['job_id'], 'fixture-job')
        self.assertEqual(set(result['artifact_hashes']), {'context.json', 'events.jsonl', 'profile.jsonl', 'summary.json'})
        for name, identity in result['artifact_hashes'].items():
            data = (directory / name).read_bytes()
            self.assertEqual(identity, {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})

    def test_early_finish_retains_partial_receipt_and_unknown_coverage(self):
        def unknown(*_):
            value = sample(); value['comfy'] = {'observed': False, 'unknown_reason': 'Unavailable fixture'}
            return NS(sample=lambda: copy.deepcopy(value), binding={'fixture': True})
        manager = self.manager(samples=3, sampler_factory=unknown)
        manager.intent(intent()); self.wait_samples(manager, 1)
        directory = self.finish(manager, 'uncertain')
        summary = json.loads((directory / 'summary.json').read_text())
        self.assertEqual(summary['sampling']['observed'], 1); self.assertFalse(summary['sampling']['complete'])
        self.assertEqual(summary['comfy']['observed_samples'], 0)
        self.assertEqual(summary['comfy']['unobserved_samples'], 1)
        self.assertEqual(json.loads((directory / 'events.jsonl').read_text().splitlines()[-1])['coordinator_exit_status'], 'uncertain')

    def test_finish_does_not_wait_for_blocked_sampler_or_start_another_thread(self):
        entered, release = threading.Event(), threading.Event()
        def factory(*_):
            def read(): entered.set(); release.wait(5); return sample()
            return NS(sample=read, binding={'fixture': True})
        self.addCleanup(release.set)
        manager = self.manager(sampler_factory=factory); manager.intent(intent())
        self.assertTrue(entered.wait(5)); original = manager.thread
        manager.finish(resources.event_snapshot('finish', {'id': 'fixture-job', 'status': 'completed'}))
        self.assertFalse(manager.last.done.is_set())
        manager.intent(intent('next-job')); self.assertIs(manager.thread, original)
        self.assertEqual(manager.last.job_id, 'fixture-job')
        release.set(); self.assertTrue(manager.last.done.wait(5)); original.join(timeout=5)
        summary = json.loads((manager.last.path / 'summary.json').read_text())
        self.assertEqual(summary['sampling']['observed'], 0, 'A sample crossing coordinator exit is discarded')
        manager.intent(intent('next-job')); self.wait_samples(manager, 1); self.finish(manager)
        self.assertEqual(len(list(manager.base.iterdir())), 2)

    def test_storage_failures_preserve_prior_receipts_and_release_observer(self):
        for stage in ('context', 'raw', 'summary', 'result'):
            with self.subTest(stage=stage):
                manager = self.manager(); original = resources.write_document
                def write(path, value):
                    if path.stem == stage: raise OSError('PRIVATE_DISK_ERROR')
                    return original(path, value)
                raw_failure = patch.object(resources._ProfileWriter, 'write', side_effect=OSError('PRIVATE')) if stage == 'raw' else nullcontext()
                with patch.object(resources, 'write_document', side_effect=write), raw_failure:
                    manager.intent(intent())
                    if stage in ('summary', 'result'): self.wait_samples(manager, 1); self.finish(manager)
                    else: self.assertTrue(manager.last.done.wait(5)); manager.thread.join(timeout=5)
                self.assertIsNone(manager.active)
                self.assertNotIn('PRIVATE', json.dumps(manager.last.result))
                before = {path: path.read_bytes() for path in manager.last.path.iterdir()}
                manager.intent(intent('later')); self.wait_samples(manager, 1); self.finish(manager)
                for path, content in before.items(): self.assertEqual(path.read_bytes(), content)

    def test_partial_raw_write_remains_consumable_and_does_not_get_repaired(self):
        manager = self.manager(samples=3); original = resources._ProfileWriter.write; calls = []
        def write(writer, value):
            calls.append(value)
            if len(calls) == 3: raise OSError('synthetic disk full')
            return original(writer, value)
        with patch.object(resources._ProfileWriter, 'write', write):
            manager.intent(intent()); self.assertTrue(manager.last.done.wait(5)); manager.thread.join(timeout=5)
        raw = (manager.last.path / 'profile.jsonl').read_bytes()
        reduced = resources.summarize_resource_profile(io.BytesIO(raw))
        self.assertEqual(reduced['sampling']['observed'], 1); self.assertFalse(reduced['sampling']['complete'])
        self.assertFalse(manager.last.result['summary_available'])

    def test_retention_has_fixed_exclusive_slots_and_never_deletes(self):
        base = self.root / 'receipts'
        with patch.object(resources, 'MAX_RECEIPTS', 2):
            first = resources.allocate_directory(base); (first / 'retained.txt').write_text('preserve')
            second = resources.allocate_directory(base)
            self.assertNotEqual(first, second)
            with self.assertRaisesRegex(ValueError, 'retention is full'): resources.allocate_directory(base)
        self.assertEqual((first / 'retained.txt').read_text(), 'preserve')
        bad = self.root / 'bad'; bad.mkdir(); (bad / 'unrecognized').mkdir()
        with self.assertRaisesRegex(ValueError, 'unknown entry'): resources.allocate_directory(bad)
        with patch.object(resources, '_plain_directory', return_value=False):
            with self.assertRaisesRegex(ValueError, 'plain directory'): resources.allocate_directory(self.root / 'reparse')

    def test_byte_event_and_wall_limits_are_finite(self):
        stream = io.BytesIO(); writer = resources._ProfileWriter(stream, lambda: None)
        with patch.object(resources, 'MAX_RAW_BYTES', 3):
            writer.write('{}\n')
            with self.assertRaises(ValueError): writer.write('{}\n')
        self.assertEqual(stream.getvalue(), b'{}\n')
        with self.assertRaises(ValueError): resources.JobResourceObservations._copy({'value': 'x' * resources.MAX_EVENT_BYTES})
        manager = self.manager()
        with patch.object(resources, 'MAX_WINDOW_SECONDS', 0):
            manager.intent(intent()); self.assertTrue(manager.last.done.wait(5)); manager.thread.join(timeout=5)
        self.assertEqual(manager.last.result['stop_reason'], 'TimeoutError')
        window = resources._Window(intent())
        for _ in range(resources.MAX_EVENTS + 10): manager._append(window, intent())
        self.assertEqual(window.events.qsize(), resources.MAX_EVENTS); self.assertTrue(window.stop.is_set())

    def test_disabled_invalid_config_and_failed_thread_start_do_not_start_observations(self):
        studio = NS(config={}, root=self.root, experiments=self.root, backends=NS())
        with patch.object(resources, 'JobResourceObservations') as create:
            self.assertIsNone(resources.from_config(studio)); create.assert_not_called()
        for options in ({'resource_observation_samples': True}, {'resource_observation_samples': 121},
                        {'resource_observation_interval_seconds': float('nan')}, {'resource_observation_interval_seconds': 0}):
            studio.config = dict(observe_job_resources=True, **options)
            self.assertIsNone(resources.from_config(studio))
        def broken(**_): return NS(start=lambda: (_ for _ in ()).throw(OSError('thread unavailable')))
        manager = self.manager(thread_factory=broken)
        with self.assertRaises(OSError): manager.intent(intent())
        self.assertIsNone(manager.active); self.assertTrue(manager.last.done.is_set())
        self.assertFalse(manager.base.exists())


class EpochTests(unittest.TestCase):
    def backends(self):
        self.epoch = [20, 123.5]; self.command = ['synthetic-python', 'main.py']
        self.calls = []
        def process(_):
            self.calls.append('identity')
            return NS(pid=self.epoch[0], create_time=lambda: self.epoch[1], cmdline=lambda: list(self.command))
        return NS(profiles={'primary': {'url': 'http://127.0.0.1:8188', 'id': 'primary'}}, process=process)

    def sampler(self, backends, fetch):
        def factory(**kwargs): self.arguments = kwargs; return NS(sample=lambda: None)
        return resources.BoundRuntimeSampler(backends, 'http://127.0.0.1:8188', sampler_factory=factory, fetcher=fetch, studio_pid=10)

    def test_listener_replacement_pid_reuse_and_argv_change_are_never_rebound(self):
        for change in ('pid', 'created', 'argv'):
            with self.subTest(change=change):
                backends = self.backends(); reads = []
                sampler = self.sampler(backends, lambda _: reads.append('GET') or ({'versions': {}, 'devices': []}, 20))
                sampler._fetch('http://127.0.0.1:8188')
                if change == 'pid': self.epoch[0] += 1
                if change == 'created': self.epoch[1] += 1
                if change == 'argv': self.command.append('--changed')
                with self.assertRaises(resources.EpochUnavailable): sampler._fetch('http://127.0.0.1:8188')
                self.epoch[:] = [20, 123.5]; self.command[:] = ['synthetic-python', 'main.py']
                with self.assertRaises(resources.EpochUnavailable): sampler._fetch('http://127.0.0.1:8188')
                self.assertEqual(reads, ['GET']); self.assertTrue(sampler.binding['lost'])

    def test_same_version_replacement_during_get_discards_reply(self):
        backends = self.backends()
        def fetch(_): self.epoch[1] += 1; return {'versions': {'comfyui_version': 'same'}, 'devices': []}, 10
        sampler = self.sampler(backends, fetch)
        with self.assertRaises(resources.EpochUnavailable): sampler._fetch('http://127.0.0.1:8188')
        self.assertEqual(len(self.calls), 3); self.assertIsNone(sampler.binding['last_bracket_at'])

    def test_missing_initial_epoch_does_not_attach_later_or_fetch(self):
        backends = self.backends(); saved = backends.process; backends.process = lambda _: None
        reads = []; sampler = self.sampler(backends, lambda _: reads.append('GET'))
        backends.process = saved
        with self.assertRaises(resources.EpochUnavailable): sampler._fetch('http://127.0.0.1:8188')
        self.assertEqual(reads, []); self.assertEqual(self.arguments['pids'], [10])
        self.assertIsNone(sampler.binding['epoch'])

    def test_process_counter_attachment_cannot_bind_a_reused_pid(self):
        backends = self.backends(); reads = []
        process = NS(pid=20, created=999, unavailable=None)
        sampler = resources.BoundRuntimeSampler(backends, 'http://127.0.0.1:8188',
                    sampler_factory=lambda **_: NS(processes=[process]), studio_pid=10,
                    fetcher=lambda _: reads.append('GET'))
        with self.assertRaises(resources.EpochUnavailable): sampler._fetch('http://127.0.0.1:8188')
        self.assertEqual(reads, []); self.assertIsNotNone(process.unavailable)
        self.assertTrue(sampler.binding['lost'])

    def test_version_and_device_layout_drift_do_not_poison_summary_with_mixed_epochs(self):
        for field in ('versions', 'devices'):
            with self.subTest(field=field):
                data = {'versions': {'comfyui_version': 'first'}, 'devices': [{'index': 0}]}
                backends = self.backends(); sampler = self.sampler(backends, lambda _: (copy.deepcopy(data), 10))
                sampler._fetch('http://127.0.0.1:8188')
                data[field] = {'comfyui_version': 'second'} if field == 'versions' else []
                with self.assertRaises(resources.EpochUnavailable): sampler._fetch('http://127.0.0.1:8188')
                self.assertTrue(sampler.binding['lost'])


if __name__ == '__main__': unittest.main()
