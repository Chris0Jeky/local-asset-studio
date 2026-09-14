"""Reproduce PID reuse *during* one observation, including cached create_time()."""
import io
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from resource_probe import ProcessObservation, ResourceSampler, write_samples
from performance_history import summarize_resource_profile


class ProcessTable:
    """Models psutil's cached per-handle identity with PID-addressed counter reads."""
    def __init__(self):
        self.created = 100; self.cpu = 2; self.rss = 30
        self.after_memory = self.after_cpu = None
        self.lookup_error = None; self.handles = []

    def Process(self, pid):
        if self.lookup_error: raise self.lookup_error
        table = self
        class Handle:
            created = table.created
            def create_time(self): return self.created
            def memory_info(self):
                if table.after_memory: table.after_memory()
                return NS(rss=table.rss, private=50, peak_wset=90)
            def cpu_times(self):
                if table.after_cpu: table.after_cpu()
                return NS(user=table.cpu, system=1)
        handle = Handle(); self.handles.append(handle); return handle


class ProcessIdentityTests(unittest.TestCase):
    def setUp(self):
        self.table = ProcessTable(); self.now = 1
        self.observer = ProcessObservation(12, self.table, lambda: self.now)

    def assert_unknown(self, record):
        for field in ('working_set_bytes', 'private_bytes', 'peak_working_set_bytes',
                      'cpu_seconds', 'cpu_one_core_percent'):
            self.assertIsNone(record[field], field)
        self.assertIsNotNone(record['unknown_reason'])
        self.assertEqual(record['created_at'], 100)
        self.assertNotIn('PRIVATE', json.dumps(record))

    def test_stable_identity_keeps_cpu_deltas(self):
        self.assertEqual(self.observer.read()['working_set_bytes'], 30)
        self.now = 3; self.table.cpu = 5
        self.assertEqual(self.observer.read()['cpu_one_core_percent'], 150)

    def test_reuse_during_memory_read_discards_every_counter_and_retires(self):
        self.observer.read()
        def replace(): self.table.created = 200; self.table.rss = 999
        self.table.after_memory = replace
        self.assert_unknown(self.observer.read())
        self.assertEqual(self.table.handles[-2].create_time(), 100, 'The old handle really caches identity')
        self.table.after_memory = None; self.table.created = 100
        self.assert_unknown(self.observer.read())

    def test_reuse_during_cpu_read_discards_partial_memory_result(self):
        self.table.after_cpu = lambda: setattr(self.table, 'created', 200)
        self.assert_unknown(self.observer.read())

    def test_post_read_lookup_error_keeps_no_counters_or_cpu_baseline(self):
        self.observer.read(); self.now = 2
        self.table.after_cpu = lambda: setattr(self.table, 'lookup_error', PermissionError('PRIVATE'))
        self.assert_unknown(self.observer.read())
        self.table.after_cpu = None; self.table.lookup_error = None
        self.table.cpu = 20; self.now = 3
        record = self.observer.read()
        self.assertEqual(record['working_set_bytes'], 30)
        self.assertIsNone(record['cpu_one_core_percent'], 'Do not bridge an unverified interval')

    def test_invalid_post_read_identity_is_unknown_not_mismatched_ownership(self):
        for invalid in (None, True, float('nan'), float('inf'), -1, '100'):
            with self.subTest(invalid=invalid):
                self.setUp()
                self.table.after_cpu = lambda: setattr(self.table, 'created', invalid)
                self.assert_unknown(self.observer.read())
                self.table.after_cpu = None; self.table.created = 100
                self.assertEqual(self.observer.read()['working_set_bytes'], 30)

    def test_boolean_identity_cannot_match_numeric_identity_before_read(self):
        self.table.created = 1
        observer = ProcessObservation(12, self.table)
        self.table.created = True
        record = observer.read()
        self.assertIsNone(record['working_set_bytes'])
        self.assertIsNotNone(record['unknown_reason'])

    def test_actual_sampler_and_reducer_keep_reused_process_unknown(self):
        table = self.table
        table.virtual_memory = lambda: NS(total=320, available=100)
        sampler = ResourceSampler([12], provider=table, commit_reader=lambda: {})
        table.after_cpu = lambda: setattr(table, 'created', 200)
        stream = io.StringIO()
        write_samples(stream, sampler, samples=1)
        result = summarize_resource_profile(io.BytesIO(stream.getvalue().encode()))
        metric = result['processes'][0]['metrics']['working_set_bytes']
        self.assertEqual(metric['known_samples'], 0)
        self.assertEqual(metric['unknown_samples'], 1)
        self.assertIsNone(metric['sampled_max'])


if __name__ == '__main__': unittest.main()
