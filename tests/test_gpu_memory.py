"""GPU process-memory parsing, the launch reserve and the spill verdict; the live PDH read runs only on Windows."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
import gpu_memory

MIB = 2 ** 20
DGPU = 'pid_{}_luid_0x00000000_0x000102FB_phys_0'
IGPU = 'pid_{}_luid_0x00000000_0x000165B8_phys_0'


def reading(dedicated, shared=None):
    return {'adapters': gpu_memory.parse(dedicated, shared or {}), 'unknown_reason': None}


class GpuMemoryTests(unittest.TestCase):
    def test_parse_folds_instances_per_adapter_and_process(self):
        adapters = gpu_memory.parse({DGPU.format(2304): 2282 * MIB, IGPU.format(2304): 8 * MIB, 'garbage': 5, DGPU.format(7): -1},
                                    {DGPU.format(2304): 54 * MIB})
        self.assertEqual(set(adapters), {'0x00000000_0x000102fb_0', '0x00000000_0x000165b8_0'})
        self.assertEqual(adapters['0x00000000_0x000102fb_0'][2304], {'dedicated_bytes': 2282 * MIB, 'shared_bytes': 54 * MIB})
        self.assertNotIn(7, adapters['0x00000000_0x000102fb_0'])

    def test_discrete_adapter_is_the_one_holding_most_dedicated_memory_or_the_process_own(self):
        adapters = gpu_memory.parse({DGPU.format(2304): 2282 * MIB, IGPU.format(11): 300 * MIB, IGPU.format(99): 10 * MIB}, {})
        self.assertEqual(gpu_memory.select_adapter(adapters), '0x00000000_0x000102fb_0')
        self.assertEqual(gpu_memory.select_adapter(adapters, pid=99), '0x00000000_0x000165b8_0')
        self.assertIsNone(gpu_memory.select_adapter({}))

    def test_launch_reserve_covers_other_processes_plus_margin_within_bounds(self):
        # 23 September 2026: dwm 2,282 MiB + the rest 811 MiB -> 3.02 GiB + 0.7 margin -> 3.8 (rounded up to 0.1).
        measured = gpu_memory.launch_reserve_gib(reading({DGPU.format(2304): 2282 * MIB, DGPU.format(30868): 811 * MIB}))
        self.assertEqual((measured['reserve_gib'], measured['basis']), (3.8, 'measured'))
        self.assertEqual(gpu_memory.launch_reserve_gib(reading({DGPU.format(1): 0}))['reserve_gib'], 0.7)
        self.assertEqual(gpu_memory.launch_reserve_gib(reading({DGPU.format(1): 40 * 1024 * MIB}))['reserve_gib'], gpu_memory.CAP_GIB)
        excluded = gpu_memory.launch_reserve_gib(reading({DGPU.format(2304): 2282 * MIB, DGPU.format(5): 9000 * MIB}), exclude_pids=[5])
        self.assertEqual(excluded['reserve_gib'], 3.0)

    def test_unreadable_counters_fall_back_to_the_measured_default(self):
        for value in ({'adapters': None, 'unknown_reason': 'nope'}, {}, None):
            with self.subTest(value=value):
                with patch.object(gpu_memory, 'read', return_value=value or {'adapters': None, 'unknown_reason': 'x'}):
                    result = gpu_memory.launch_reserve_gib(value)
                self.assertEqual((result['reserve_gib'], result['basis']), (gpu_memory.FALLBACK_GIB, 'fallback'))

    def test_spill_is_reported_from_the_process_shared_usage(self):
        sample = reading({DGPU.format(40): 15881 * MIB, DGPU.format(2304): 2306 * MIB}, {DGPU.format(40): 1537 * MIB})
        self.assertTrue(gpu_memory.spill(40, sample)['spilled'])
        quiet = reading({DGPU.format(40): 10658 * MIB}, {DGPU.format(40): 78 * MIB})
        self.assertFalse(gpu_memory.spill(40, quiet)['spilled'])
        for pid, value in ((None, sample), (41, sample), (40, {'adapters': None, 'unknown_reason': 'x'})):
            with self.subTest(pid=pid):self.assertIsNone(gpu_memory.spill(pid, value)['spilled'])

    @unittest.skipUnless(os.name == 'nt', 'Windows GPU performance counters only')
    def test_live_read_never_raises_and_reports_consistent_shapes(self):
        result = gpu_memory.read()
        self.assertEqual(set(result), {'adapters', 'unknown_reason'})
        if result['adapters'] is not None:
            for processes in result['adapters'].values():
                for usage in processes.values():
                    self.assertGreaterEqual(usage['dedicated_bytes'], 0);self.assertGreaterEqual(usage['shared_bytes'], 0)
        reserve = gpu_memory.launch_reserve_gib(result)
        self.assertTrue(gpu_memory.FLOOR_GIB <= reserve['reserve_gib'] <= gpu_memory.CAP_GIB)


if __name__ == '__main__':
    unittest.main()
