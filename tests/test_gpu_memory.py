"""GPU process-memory parsing, the launch reserve and the spill verdict; the live PDH read runs only on Windows."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
import gpu_memory

MIB = 2 ** 20
GIB = 1024 * MIB
DGPU = 'pid_{}_luid_0x00000000_0x000102FB_phys_0'
IGPU = 'pid_{}_luid_0x00000000_0x000165B8_phys_0'
DGPU_ADAPTER = '0x00000000_0x000102fb_0'
IGPU_ADAPTER = '0x00000000_0x000165b8_0'
DWM_ANOMALY = int(65.9 * GIB)


def reading(dedicated, shared=None):
    return {'adapters': gpu_memory.parse(dedicated, shared or {}), 'unknown_reason': None}


def reading_with_totals(dedicated, totals, shared=None):
    return {'adapters': gpu_memory.parse(dedicated, shared or {}), 'adapter_totals': totals, 'unknown_reason': None}


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

    def test_parse_adapter_totals_keys_match_process_adapters(self):
        totals = gpu_memory.parse_adapter_totals({'luid_0x00000000_0x000102FB_phys_0': 4 * GIB, 'garbage': 9,
                                                  '0x00000000_0x000165B8_phys_0': 512 * MIB,
                                                  'luid_0x00000000_0x000165B8_phys_0': -1})
        self.assertEqual(totals, {DGPU_ADAPTER: 4 * GIB, IGPU_ADAPTER: 512 * MIB})

    def test_impossible_process_counter_is_excluded_from_launch_reserve(self):
        # Issue #983: dwm reported 65.9 GiB against a single-digit-GiB adapter figure; the reserve used to
        # treat that sum as a confident measurement and pin itself at the 6 GiB cap.
        sample = reading_with_totals({DGPU.format(2304): DWM_ANOMALY, DGPU.format(30868): 812 * MIB}, {DGPU_ADAPTER: 4 * GIB})
        result = gpu_memory.launch_reserve_gib(sample)
        self.assertEqual((result['basis'], result['excluded_pids'], result['adapter_total_bytes']),
                         ('reconciled', [2304], 4 * GIB))
        self.assertEqual(result['others_bytes'], 4 * GIB)
        self.assertEqual(result['reserve_gib'], 4.7)

    def test_impossible_process_counter_is_excluded_from_others_bytes(self):
        sample = reading_with_totals({DGPU.format(40): 2 * GIB, DGPU.format(2304): DWM_ANOMALY, DGPU.format(30868): 812 * MIB},
                                     {DGPU_ADAPTER: 4 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 2 * GIB)

    def test_plausible_counters_stay_measured(self):
        sample = reading_with_totals({DGPU.format(2304): 2282 * MIB, DGPU.format(30868): 811 * MIB}, {DGPU_ADAPTER: 4 * GIB})
        measured = gpu_memory.launch_reserve_gib(sample)
        self.assertEqual((measured['reserve_gib'], measured['basis'], measured['excluded_pids']), (3.8, 'measured', []))
        self.assertEqual(measured['adapter_total_bytes'], 4 * GIB)
        self.assertEqual(gpu_memory.others_bytes(sample, 30868), 2282 * MIB)

    def test_missing_or_unmatched_adapter_totals_are_unknown_in_new_readings(self):
        inflated = {DGPU.format(2304): DWM_ANOMALY, DGPU.format(30868): 812 * MIB}
        unavailable = reading_with_totals(inflated, None)
        fallback = gpu_memory.launch_reserve_gib(unavailable)
        self.assertEqual((fallback['basis'], fallback['reserve_gib']), ('fallback', gpu_memory.FALLBACK_GIB))
        self.assertIsNone(gpu_memory.others_bytes(unavailable, 30868))
        unmatched = gpu_memory.launch_reserve_gib(reading_with_totals(inflated, {IGPU_ADAPTER: 512 * MIB}))
        self.assertEqual((unmatched['basis'], unmatched['others_bytes']), ('fallback', None))
        self.assertIsNone(unmatched['adapter_total_bytes'])
        # Older injected readings without the new field keep their old contract.
        legacy = gpu_memory.launch_reserve_gib(reading({DGPU.format(1): 812 * MIB}))
        self.assertEqual((legacy['basis'], legacy['others_bytes']), ('measured', 812 * MIB))

    def test_zero_adapter_counter_does_not_certify_nonzero_process_use(self):
        sample = reading_with_totals({DGPU.format(2304): 812 * MIB}, {DGPU_ADAPTER: 0})
        self.assertEqual(gpu_memory.launch_reserve_gib(sample)['basis'], 'fallback')
        self.assertIsNone(gpu_memory.others_bytes(sample, 2304))

    def test_impossible_own_process_counter_cannot_subtract_from_adapter(self):
        sample = reading_with_totals({DGPU.format(40): DWM_ANOMALY, DGPU.format(2304): 812 * MIB},
                                     {DGPU_ADAPTER: 4 * GIB})
        self.assertIsNone(gpu_memory.others_bytes(sample, 40))

    def test_impossible_own_usage_retains_credible_other_processes(self):
        # Follow-up to issue #983: own 4.8 GiB exceeds the 4 GiB adapter total (process sum 5.5 GiB
        # is past the 5.4 GiB reconciliation limit), so subtracting it hid the measured 0.7 GiB
        # external holder behind an others reading of zero.
        sample = reading_with_totals({DGPU.format(40): int(4.8 * GIB), DGPU.format(2304): int(0.7 * GIB)},
                                     {DGPU_ADAPTER: 4 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), int(0.7 * GIB))
        # A runaway counter alongside the impossible own reading stays excluded.
        crowded = reading_with_totals({DGPU.format(40): int(4.8 * GIB), DGPU.format(2304): int(0.7 * GIB),
                                       DGPU.format(500): DWM_ANOMALY}, {DGPU_ADAPTER: 4 * GIB})
        self.assertEqual(gpu_memory.others_bytes(crowded, 40), int(0.7 * GIB))

    def test_others_still_count_before_comfy_process_counter_appears(self):
        sample = reading_with_totals({DGPU.format(2304): 2 * GIB}, {DGPU_ADAPTER: 3 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 2 * GIB)

    def test_reconciliation_applies_per_adapter(self):
        sample = reading_with_totals({DGPU.format(40): 2 * GIB, DGPU.format(2304): 1 * GIB,
                                      IGPU.format(11): DWM_ANOMALY, IGPU.format(12): 100 * MIB},
                                     {DGPU_ADAPTER: 5 * GIB, IGPU_ADAPTER: 512 * MIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 1 * GIB)
        self.assertEqual(gpu_memory.others_bytes(sample, 12), 512 * MIB - 100 * MIB)

    def test_launch_adapter_selection_ignores_anomaly_on_another_adapter(self):
        sample = reading_with_totals({DGPU.format(40): 2 * GIB, IGPU.format(11): DWM_ANOMALY},
                                     {DGPU_ADAPTER: 3 * GIB, IGPU_ADAPTER: 512 * MIB})
        result = gpu_memory.launch_reserve_gib(sample)
        self.assertEqual((result['adapter'], result['basis'], result['others_bytes']),
                         (DGPU_ADAPTER, 'measured', 2 * GIB))

    def test_partial_adapter_totals_do_not_redirect_launch_to_igpu(self):
        sample = reading_with_totals({DGPU.format(40): 12 * GIB, IGPU.format(11): 300 * MIB},
                                     {IGPU_ADAPTER: 300 * MIB})
        result = gpu_memory.launch_reserve_gib(sample)
        self.assertEqual((result['basis'], result['adapter'], result['others_bytes']), ('fallback', None, None))

    def test_collective_overshoot_is_capped_at_the_adapter_figure(self):
        sample = reading_with_totals({DGPU.format(7): 3 * GIB, DGPU.format(8): 3 * GIB}, {DGPU_ADAPTER: 4 * GIB})
        result = gpu_memory.launch_reserve_gib(sample)
        self.assertEqual((result['excluded_pids'], result['others_bytes'], result['basis']), ([], 4 * GIB, 'reconciled'))
        self.assertEqual(result['reserve_gib'], 4.7)

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
        self.assertEqual(set(result), {'adapters', 'adapter_totals', 'unknown_reason', 'adapter_unknown_reason'})
        if result['adapters'] is not None:
            for processes in result['adapters'].values():
                for usage in processes.values():
                    self.assertGreaterEqual(usage['dedicated_bytes'], 0);self.assertGreaterEqual(usage['shared_bytes'], 0)
        reserve = gpu_memory.launch_reserve_gib(result)
        self.assertTrue(gpu_memory.FLOOR_GIB <= reserve['reserve_gib'] <= gpu_memory.CAP_GIB)


if __name__ == '__main__':
    unittest.main()
