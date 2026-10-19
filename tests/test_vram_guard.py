"""The Studio VRAM guard loaded into ComfyUI (runtime-patches/comfy-extensions/studio_vram_guard)."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import backends
import gpu_memory

GIB = 1024 ** 3
INSTALLED_MM = Path('C:/AI/ComfyUI_windows_portable/ComfyUI/comfy/model_management.py')
MM_SOURCE = '''
def get_free_memory(dev=None, torch_free_too=False):
    return (FREE, FREE // 4) if torch_free_too else FREE

def free_memory(memory_required, device, keep_loaded=[]):
    SEEN.append(get_free_memory(device)); SEEN.append(get_free_memory(device, torch_free_too=True)); SEEN.append(get_free_memory(CPU))
    return SEEN
'''

def load_guard():
    with patch.dict(os.environ, {'STUDIO_VRAM_GUARD_IMPORT_ONLY': '1'}):
        spec = importlib.util.spec_from_file_location('studio_vram_guard_under_test', ROOT / 'runtime-patches/comfy-extensions/studio_vram_guard/__init__.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class VramGuardTest(unittest.TestCase):
    def setUp(self):
        self.guard = load_guard(); self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'model_management.py'; self.path.write_text(MM_SOURCE, encoding='utf-8')
        self.mm = types.ModuleType('fake_model_management'); self.mm.__file__ = str(self.path)
        exec(compile(MM_SOURCE, str(self.path), 'exec'), self.mm.__dict__); self.mm.FREE = 12 * GIB; self.mm.SEEN = []; self.mm.CPU = types.SimpleNamespace(type='cpu')
        self.mm.get_total_memory = lambda dev=None: 16 * GIB
        self.mm.get_torch_device = lambda: types.SimpleNamespace(type='cuda', index=0)
        self.expected = {name: self.guard.function_hash(self.path, name) for name in ('free_memory', 'get_free_memory')}
        self.status = {'installed': False, 'reason': None, 'others_bytes': None, 'eviction_calls': 0, 'counted_calls': 0}

    def install(self, held=5 * GIB, expected=None):
        return self.guard.install(self.mm, lambda **kwargs: held, expected=expected or self.expected, status=self.status)

    def test_evictions_count_other_processes_but_load_decisions_do_not(self):
        self.assertTrue(self.install()['installed'])
        # Outside free_memory (ComfyUI's full/partial load decision) the figure is unchanged ...
        self.assertEqual(self.mm.get_free_memory(), 12 * GIB)
        # ... inside it, what other processes hold is subtracted from the total (not from torch's own cache), cpu untouched.
        self.assertEqual(self.mm.free_memory(9 * GIB, 'cuda:0'), [7 * GIB, (7 * GIB, 3 * GIB), 12 * GIB])
        self.assertEqual(self.mm.get_free_memory(), 12 * GIB)
        self.assertEqual((self.status['eviction_calls'], self.status['counted_calls']), (1, 2))

    def test_the_figure_is_clamped_at_zero_and_untouched_when_nothing_else_is_held(self):
        self.install(held=20 * GIB); self.assertEqual(self.mm.free_memory(1, 'cuda:0'), [0, (0, 3 * GIB), 12 * GIB])
        self.setUp(); self.install(held=0)
        self.assertEqual(self.mm.free_memory(1, 'cuda:0'), [12 * GIB, (12 * GIB, 3 * GIB), 12 * GIB]); self.assertEqual(self.status['counted_calls'], 0)

    def test_changed_comfyui_leaves_the_guard_off_and_says_why(self):
        original_free, original_get = self.mm.free_memory, self.mm.get_free_memory
        status = self.install(expected=dict(self.expected, free_memory='0' * 64))
        self.assertFalse(status['installed']); self.assertIn('free_memory', status['reason'])
        self.assertIs(self.mm.free_memory, original_free); self.assertIs(self.mm.get_free_memory, original_get)
        missing = types.ModuleType('missing'); missing.__file__ = str(Path(self.tmp.name) / 'absent.py')
        status = self.guard.install(missing, lambda: 0, expected=self.expected, status=dict(self.status))
        self.assertFalse(status['installed']); self.assertIn('not installed', status['reason'])

    def test_an_exception_inside_an_eviction_resets_the_scope(self):
        self.install(); self.mm.SEEN = None
        with self.assertRaises(AttributeError): self.mm.free_memory(1, 'cuda:0')
        self.assertEqual(self.mm.get_free_memory(), 12 * GIB)

    def test_install_is_idempotent(self):
        self.install(); first = self.mm.free_memory; self.install(); self.assertIs(self.mm.free_memory, first)
        second = dict(self.status, installed=False)                     # a second import has its own STATUS
        self.guard.install(self.mm, lambda: 0, expected=self.expected, status=second)
        self.assertIs(self.mm.free_memory, first); self.assertTrue(second['installed'])

    def test_others_reading_is_cached_then_unknown_with_a_declared_fallback(self):
        clock = iter([0.0, 0.1, 0.2, 5.0]).__next__
        fake = types.SimpleNamespace(read=lambda: {'adapters': {'a': {1: {'dedicated_bytes': 3 * GIB}, 9: {'dedicated_bytes': 2 * GIB}}}},
                                     others_bytes=gpu_memory.others_bytes, others_for_admission=gpu_memory.others_for_admission,
                                     anomalies=gpu_memory.anomalies)
        status = dict(self.status); reading = self.guard.OthersReading(fake, pid=9, clock=clock, status=status)
        self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 3 * GIB)
        fake.read = lambda: 1 / 0
        self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 3 * GIB)   # cached
        self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 3 * GIB)
        self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 4 * GIB)
        self.assertIsNone(status['others_bytes']); self.assertEqual(status['adjustment_basis'], 'fallback')
        self.assertIn('ZeroDivisionError', status['unknown_reason'])

    def test_anomalous_process_counter_uses_adapter_total_for_eviction(self):
        adapter = '0x00000000_0x000102fb_0'
        sample = {'adapters': {adapter: {10: {'dedicated_bytes': 2 * GIB},
                                        2288: {'dedicated_bytes': 66 * GIB},
                                        77: {'dedicated_bytes': GIB}}},
                  'adapter_totals': {adapter: 4 * GIB}}
        fake = types.SimpleNamespace(read=lambda: sample, others_bytes=gpu_memory.others_bytes,
                                     others_for_admission=gpu_memory.others_for_admission, anomalies=gpu_memory.anomalies)
        others = self.guard.OthersReading(fake, pid=10, status=self.status)
        self.assertTrue(self.guard.install(self.mm, others, expected=self.expected, status=self.status)['installed'])
        self.assertEqual(self.mm.free_memory(9 * GIB, 'cuda:0'), [10 * GIB, (10 * GIB, 3 * GIB), 12 * GIB])
        self.assertEqual(self.status['others_bytes'], 2 * GIB)
        self.assertEqual(self.status['reading_basis'], 'reconciled')
        self.assertEqual(self.status['counter_anomalies'][0]['pid'], 2288)

    def test_missing_own_process_counter_still_counts_external_use(self):
        adapter = '0x00000000_0x000102fb_0'
        sample = {'adapters': {adapter: {2288: {'dedicated_bytes': 2 * GIB}}},
                  'adapter_totals': {adapter: 3 * GIB}}
        fake = types.SimpleNamespace(read=lambda: sample, others_bytes=gpu_memory.others_bytes,
                                     others_for_admission=gpu_memory.others_for_admission, anomalies=gpu_memory.anomalies)
        others = self.guard.OthersReading(fake, pid=10, status=self.status)
        self.assertTrue(self.guard.install(self.mm, others, expected=self.expected, status=self.status)['installed'])
        # Adapter-preferred since the owner decision on #983: the whole 3 GiB adapter figure while pid 10 has no counter.
        self.assertEqual(self.mm.free_memory(9 * GIB, 'cuda:0'), [9 * GIB, (9 * GIB, 3 * GIB), 12 * GIB])
        self.assertEqual(self.status['others_bytes'], 3 * GIB)

    def test_initial_unknown_never_certifies_zero_external_usage(self):
        for sample in ({'adapters': None, 'unknown_reason': 'PDH unavailable'},
                       {'adapters': {'a': {10: {'dedicated_bytes': GIB}}}, 'adapter_totals': None}):
            with self.subTest(sample=sample), patch.object(gpu_memory, 'read', return_value=sample):
                status = dict(self.status)
                reading = self.guard.OthersReading(gpu_memory, pid=10, status=status)
                self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 4 * GIB)
                self.assertIsNone(status['others_bytes']); self.assertEqual(status['reading_basis'], 'unknown')
                self.assertEqual(status['adjustment_basis'], 'fallback'); self.assertTrue(status['unknown_reason'])

    def test_initial_unknown_adjusts_evictions_without_changing_load_decisions(self):
        with patch.object(gpu_memory, 'read', return_value={'adapters': None, 'unknown_reason': 'PDH unavailable'}):
            others = self.guard.OthersReading(gpu_memory, pid=10, status=self.status)
            self.guard.install(self.mm, others, expected=self.expected, status=self.status)
            self.assertEqual(self.mm.free_memory(9 * GIB, 'cuda:0'), [8 * GIB, (8 * GIB, 3 * GIB), 12 * GIB])
            self.assertEqual(self.mm.get_free_memory(), 12 * GIB)
            self.assertIsNone(self.status['others_bytes'])

    def test_unknown_after_known_zero_uses_fallback_not_the_old_zero(self):
        sample = {'adapters': {'a': {10: {'dedicated_bytes': GIB}}}, 'adapter_totals': {'a': GIB}}
        with patch.object(gpu_memory, 'read', side_effect=[sample, {'adapters': None}]):
            reading = self.guard.OthersReading(gpu_memory, pid=10, clock=iter([0.0, 0.6]).__next__, status=self.status)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 0)
            self.assertEqual(self.status['reading_basis'], 'measured')
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 4 * GIB)
            self.assertIsNone(self.status['others_bytes']); self.assertEqual(self.status['adjustment_basis'], 'fallback')

    def test_last_known_bound_expires_without_refreshing_its_age_on_failures(self):
        sample = {'adapters': {'a': {10: {'dedicated_bytes': GIB}, 20: {'dedicated_bytes': 8 * GIB}}},
                  'adapter_totals': {'a': 9 * GIB}}
        with patch.object(gpu_memory, 'read', side_effect=[sample, OSError('PDH unavailable'), OSError('still unavailable')]):
            reading = self.guard.OthersReading(gpu_memory, pid=10, clock=iter([0.0, 0.6, 2.1]).__next__, status=self.status)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 8 * GIB)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 8 * GIB)
            self.assertIsNone(self.status['others_bytes']); self.assertEqual(self.status['adjustment_basis'], 'last_known')
            self.assertEqual(self.status['last_known_age_seconds'], 0.6)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 4 * GIB)
            self.assertEqual(self.status['adjustment_basis'], 'fallback')
            self.assertEqual(self.status['last_known_age_seconds'], 2.1)

    def test_last_known_age_limit_applies_even_while_an_unknown_sample_is_cached(self):
        sample = {'adapters': {'a': {10: {'dedicated_bytes': GIB}, 20: {'dedicated_bytes': 8 * GIB}}},
                  'adapter_totals': {'a': 9 * GIB}}
        with patch.object(gpu_memory, 'read', side_effect=[sample, {'adapters': None}]):
            reading = self.guard.OthersReading(gpu_memory, pid=10, clock=iter([0.0, 1.9, 2.1]).__next__, status=self.status)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 8 * GIB)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 8 * GIB)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 4 * GIB)
            self.assertIsNone(self.status['others_bytes']); self.assertEqual(self.status['adjustment_basis'], 'fallback')

    def test_a_fresh_known_zero_clears_the_unknown_fallback(self):
        sample = {'adapters': {'a': {10: {'dedicated_bytes': GIB}}}, 'adapter_totals': {'a': GIB}}
        with patch.object(gpu_memory, 'read', side_effect=[{'adapters': None}, sample]):
            reading = self.guard.OthersReading(gpu_memory, pid=10, clock=iter([0.0, 0.6]).__next__, status=self.status)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 4 * GIB)
            self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 0)
            self.assertEqual(self.status['others_bytes'], 0); self.assertEqual(self.status['reading_basis'], 'measured')
            self.assertIsNone(self.status['unknown_reason']); self.assertEqual(self.status['adjustment_basis'], 'measured')

    def test_device_capacity_or_clock_change_discards_the_cached_and_last_known_values(self):
        sample = {'adapters': {'a': {10: {'dedicated_bytes': GIB}, 20: {'dedicated_bytes': 8 * GIB}}},
                  'adapter_totals': {'a': 9 * GIB}}
        for device, capacity, clock in [('cuda:1', 16 * GIB, [10.0, 10.1]),
                                        ('cuda:0', 12 * GIB, [10.0, 10.1]),
                                        ('cuda:0', 16 * GIB, [10.0, 9.0])]:
            with self.subTest(device=device, capacity=capacity, clock=clock), patch.object(gpu_memory, 'read', side_effect=[sample, OSError('unavailable')]):
                status = dict(self.status)
                reading = self.guard.OthersReading(gpu_memory, pid=10, clock=iter(clock).__next__, status=status)
                self.assertEqual(reading(capacity_bytes=16 * GIB, device='cuda:0'), 8 * GIB)
                self.assertEqual(reading(capacity_bytes=capacity, device=device), 4 * GIB)
                self.assertIsNone(status['others_bytes']); self.assertEqual(status['adjustment_basis'], 'fallback')
                self.assertIsNone(status['last_known_age_seconds'])

    def test_unusable_capacity_is_unknown_and_valid_small_capacity_caps_the_fallback(self):
        with patch.object(gpu_memory, 'read', return_value={'adapters': None}):
            for capacity in (None, True, 0, 0.5, -1, float('nan'), float('inf'), '16 GiB'):
                with self.subTest(capacity=capacity):
                    status = dict(self.status); reading = self.guard.OthersReading(gpu_memory, pid=10, status=status)
                    self.assertEqual(reading(capacity_bytes=capacity, device='cuda:0'), 4 * GIB)
                    self.assertIsNone(status['others_bytes']); self.assertIsNone(status['capacity_bytes'])
                    self.assertIn('capacity', status['unknown_reason'])
            reading = self.guard.OthersReading(gpu_memory, pid=10, status=self.status)
            self.assertEqual(reading(capacity_bytes=2 * GIB, device='cuda:0'), 2 * GIB)

    def test_impossible_capacity_sources_use_an_unknown_fallback_during_eviction(self):
        sample = {'adapters': {'a': {10: {'dedicated_bytes': 17 * GIB}}}, 'adapter_totals': {'a': 20 * GIB}}
        with patch.object(gpu_memory, 'read', return_value=sample):
            others = self.guard.OthersReading(gpu_memory, pid=10, status=self.status)
            self.guard.install(self.mm, others, expected=self.expected, status=self.status)
            self.assertEqual(self.mm.free_memory(9 * GIB, 'cuda:0'), [8 * GIB, (8 * GIB, 3 * GIB), 12 * GIB])
            self.assertEqual(self.mm.get_free_memory(), 12 * GIB)
            self.assertIsNone(self.status['others_bytes']); self.assertEqual(self.status['unknown_reason'], gpu_memory.CAPACITY_REASON)

    def test_overflowing_integer_capacity_remains_unknown(self):
        reading = self.guard.OthersReading(gpu_memory, pid=10, status=self.status)
        try: adjustment = reading(capacity_bytes=10 ** 1000, device='cuda:0')
        except OverflowError: self.fail('A malformed capacity escaped the guard instead of remaining unknown')
        self.assertEqual(adjustment, 4 * GIB); self.assertIsNone(self.status['others_bytes'])
        self.assertIsNone(self.status['capacity_bytes']); self.assertIn('capacity', self.status['unknown_reason'])

    def test_capacity_query_failure_stays_unknown_and_cpu_or_mps_bypass_the_guard(self):
        self.mm.get_total_memory = lambda dev=None: 1 / 0
        with patch.object(gpu_memory, 'read', return_value={'adapters': {'a': {10: {'dedicated_bytes': GIB}}}, 'adapter_totals': {'a': GIB}}):
            others = self.guard.OthersReading(gpu_memory, pid=10, status=self.status)
            self.guard.install(self.mm, others, expected=self.expected, status=self.status)
            self.assertEqual(self.mm.free_memory(9 * GIB, 'cuda:0'), [8 * GIB, (8 * GIB, 3 * GIB), 12 * GIB])
            self.assertIsNone(self.status['others_bytes']); self.assertIn('capacity', self.status['unknown_reason'])
            self.mm.SEEN = []; self.mm.get_torch_device = lambda: self.mm.CPU
            self.assertEqual(self.mm.free_memory(1, None), [12 * GIB, (12 * GIB, 3 * GIB), 12 * GIB])
            self.mm.SEEN = []
            self.assertEqual(self.mm.free_memory(1, types.SimpleNamespace(type='mps')), [12 * GIB, (12 * GIB, 3 * GIB), 12 * GIB])

    def test_bare_cuda_resolves_the_current_device_before_reusing_the_cache(self):
        sample = {'adapters': {'a': {10: {'dedicated_bytes': GIB}, 20: {'dedicated_bytes': 8 * GIB}}},
                  'adapter_totals': {'a': 9 * GIB}}
        with patch.object(gpu_memory, 'read', side_effect=[sample, {'adapters': None}]):
            others = self.guard.OthersReading(gpu_memory, pid=10, clock=lambda: 0.0, status=self.status)
            self.guard.install(self.mm, others, expected=self.expected, status=self.status)
            self.mm.get_torch_device = lambda: 'cuda:0'
            self.assertEqual(self.mm.free_memory(1, 'cuda'), [4 * GIB, (4 * GIB, 3 * GIB), 12 * GIB])
            self.mm.SEEN = []; self.mm.get_torch_device = lambda: 'cuda:1'
            self.assertEqual(self.mm.free_memory(1, 'cuda'), [8 * GIB, (8 * GIB, 3 * GIB), 12 * GIB])
            self.assertIsNone(self.status['others_bytes']); self.assertEqual(self.status['device'], 'cuda:1')

    def test_device_identity_query_failure_is_explicitly_unknown(self):
        self.mm.get_torch_device = lambda: 1 / 0
        others = self.guard.OthersReading(gpu_memory, pid=10, status=self.status)
        self.guard.install(self.mm, others, expected=self.expected, status=self.status)
        self.assertEqual(self.mm.free_memory(1, None), [8 * GIB, (8 * GIB, 3 * GIB), 12 * GIB])
        self.assertIsNone(self.status['others_bytes']); self.assertIsNone(self.status['device'])
        self.assertIn('device identity', self.status['unknown_reason'])

    def test_restored_capacity_takes_a_fresh_reading_and_clears_the_unknown_status(self):
        busy = {'adapters': {'a': {10: {'dedicated_bytes': GIB}, 20: {'dedicated_bytes': 8 * GIB}}},
                'adapter_totals': {'a': 9 * GIB}}
        quiet = {'adapters': {'a': {10: {'dedicated_bytes': GIB}}}, 'adapter_totals': {'a': GIB}}
        with patch.object(gpu_memory, 'read', side_effect=[busy, quiet]):
            others = self.guard.OthersReading(gpu_memory, pid=10, clock=lambda: 0.0, status=self.status)
            self.guard.install(self.mm, others, expected=self.expected, status=self.status)
            self.assertEqual(self.mm.free_memory(1, 'cuda:0'), [4 * GIB, (4 * GIB, 3 * GIB), 12 * GIB])
            self.mm.SEEN = []; self.mm.get_total_memory = lambda dev=None: 1 / 0
            self.assertEqual(self.mm.free_memory(1, 'cuda:0'), [8 * GIB, (8 * GIB, 3 * GIB), 12 * GIB])
            self.assertIsNone(self.status['others_bytes']); self.assertIsNone(self.status['capacity_bytes'])
            self.mm.SEEN = []; self.mm.get_total_memory = lambda dev=None: 16 * GIB
            self.assertEqual(self.mm.free_memory(1, 'cuda:0'), [12 * GIB, (12 * GIB, 3 * GIB), 12 * GIB])
            self.assertEqual(self.status['others_bytes'], 0); self.assertEqual(self.status['capacity_bytes'], 16 * GIB)
            self.assertIsNone(self.status['unknown_reason']); self.assertEqual(self.status['reading_basis'], 'measured')

    @unittest.skipUnless(INSTALLED_MM.is_file(), 'no local ComfyUI installation')
    def test_pinned_hashes_match_the_installed_comfyui(self):
        # A ComfyUI update that changes either function turns the guard off at load; this says so before a launch does.
        self.assertEqual({name: self.guard.function_hash(INSTALLED_MM, name) for name in self.guard.EXPECTED}, self.guard.EXPECTED)

    def test_guard_loads_the_studio_gpu_memory_module_by_path(self):
        module = self.guard.load_gpu_memory(ROOT)
        self.assertEqual(module.__name__, 'studio_gpu_memory'); self.assertTrue(callable(module.others_bytes))


class GuardReportTest(unittest.TestCase):
    def test_report_round_trip_and_stale_or_missing_reports(self):
        import json
        from server import Studio
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            fake = types.SimpleNamespace(root=Path(tmp), gpu_memory_reading=lambda: {'pid': 4242})
            self.assertIsNone(Studio.vram_guard_status(fake)['installed'])                         # nothing written yet
            guard.write_report({'installed': True, 'reason': None}, repo=tmp, pid=4242)
            self.assertEqual(Studio.vram_guard_status(fake), {'installed': True, 'reason': None, 'pid': 4242})
            guard.write_report({'installed': False, 'reason': 'ComfyUI changed free_memory'}, repo=tmp, pid=4242)
            self.assertEqual(Studio.vram_guard_status(fake)['reason'], 'ComfyUI changed free_memory')
            fake.gpu_memory_reading = lambda: {'pid': 5151}                                     # a later ComfyUI, launched without it
            self.assertIn('earlier ComfyUI process', Studio.vram_guard_status(fake)['reason'])
            (Path(tmp) / '.runtime/vram-guard.json').write_text('[', encoding='utf-8')
            self.assertIsNone(Studio.vram_guard_status(fake)['installed'])


class GpuMemoryHoldersTest(unittest.TestCase):
    READING = {'adapters': {'0x0_0x1_0': {10: {'dedicated_bytes': 6 * GIB, 'shared_bytes': 0}, 2288: {'dedicated_bytes': 5 * GIB, 'shared_bytes': 0},
                                         77: {'dedicated_bytes': GIB, 'shared_bytes': 0}},
                           '0x0_0x2_0': {5: {'dedicated_bytes': 64 * 2 ** 20, 'shared_bytes': 0}}}}

    def test_others_bytes_counts_every_other_process_on_the_same_adapter(self):
        self.assertEqual(gpu_memory.others_bytes(self.READING, 10), 6 * GIB)
        self.assertIsNone(gpu_memory.others_bytes({'adapters': None}, 10))

    def test_holders_are_ranked_largest_first_and_exclude_the_process(self):
        with patch('psutil.Process', side_effect=lambda pid: types.SimpleNamespace(name=lambda: {2288: 'dwm.exe'}.get(pid, 'x.exe'))):
            rows = gpu_memory.holders(self.READING, 10, top=1)
        self.assertEqual(rows, [{'pid': 2288, 'name': 'dwm.exe', 'dedicated_bytes': 5 * GIB, 'plausible': None}])  # no adapter figure (#983)
        self.assertEqual(gpu_memory.holders(None, 10), [])


class PrimaryLaunchCarriesTheGuardTest(unittest.TestCase):
    def test_guard_paths_flag_is_on_by_default_and_off_when_configured(self):
        target = {'python': 'py', 'entry': 'main.py', 'port': 8188, 'reserve_vram': 0.6, 'vram_guard': True}
        argv = backends.BackendManager.primary_argv(target)
        self.assertEqual(argv[argv.index('--extra-model-paths-config') + 1], str(backends.VRAM_GUARD_PATHS))
        self.assertTrue(backends.VRAM_GUARD_PATHS.is_file())
        self.assertNotIn('--extra-model-paths-config', backends.BackendManager.primary_argv(dict(target, vram_guard=False)))
        text = backends.VRAM_GUARD_PATHS.read_text(encoding='utf-8')
        self.assertIn('custom_nodes: .', text); self.assertTrue((backends.VRAM_GUARD_PATHS.parent / 'studio_vram_guard/__init__.py').is_file())


if __name__ == '__main__':
    unittest.main()
