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
        self.expected = {name: self.guard.function_hash(self.path, name) for name in ('free_memory', 'get_free_memory')}
        self.status = {'installed': False, 'reason': None, 'others_bytes': None, 'eviction_calls': 0, 'counted_calls': 0}

    def install(self, held=5 * GIB, expected=None):
        return self.guard.install(self.mm, lambda: held, expected=expected or self.expected, status=self.status)

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

    def test_others_reading_is_cached_and_zero_when_unreadable(self):
        clock = iter([0.0, 0.1, 0.2, 5.0]).__next__
        fake = types.SimpleNamespace(read=lambda: {'adapters': {'a': {1: {'dedicated_bytes': 3 * GIB}, 9: {'dedicated_bytes': 2 * GIB}}}},
                                     others_bytes=gpu_memory.others_bytes)
        status = dict(self.status); reading = self.guard.OthersReading(fake, pid=9, clock=clock, status=status)
        self.assertEqual(reading(), 3 * GIB); fake.read = lambda: 1 / 0; self.assertEqual(reading(), 3 * GIB)   # cached
        self.assertEqual(reading(), 3 * GIB); self.assertEqual(reading(), 0); self.assertEqual(status['others_bytes'], 0)

    @unittest.skipUnless(INSTALLED_MM.is_file(), 'no local ComfyUI installation')
    def test_pinned_hashes_match_the_installed_comfyui(self):
        # A ComfyUI update that changes either function turns the guard off at load; this says so before a launch does.
        self.assertEqual({name: self.guard.function_hash(INSTALLED_MM, name) for name in self.guard.EXPECTED}, self.guard.EXPECTED)

    def test_guard_loads_the_studio_gpu_memory_module_by_path(self):
        module = self.guard.load_gpu_memory(ROOT)
        self.assertEqual(module.__name__, 'studio_gpu_memory'); self.assertTrue(callable(module.others_bytes))


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
        self.assertEqual(rows, [{'pid': 2288, 'name': 'dwm.exe', 'dedicated_bytes': 5 * GIB}])
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
