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

    def test_holders_flag_counters_the_adapter_figure_rules_out(self):
        # Issue #983: dwm at 65.85 GiB on a 16 GiB card must not top peak evidence as if it were real.
        own = 40
        sample = reading_with_totals({DGPU.format(own): 8 * GIB, DGPU.format(2288): int(65.85 * GIB), DGPU.format(3000): 2 * GIB},
                                     {DGPU_ADAPTER: 16 * GIB})
        with patch('psutil.Process', side_effect=OSError('no real processes in tests')):
            rows = gpu_memory.holders(sample, own)
        self.assertEqual([(row['pid'], row['plausible']) for row in rows], [(3000, True), (2288, False)])
        self.assertEqual([row['dedicated_bytes'] for row in rows], [2 * GIB, int(65.85 * GIB)])
        # Without an adapter figure there is nothing to rule a counter out by: raw order, unknown plausibility.
        legacy = reading({DGPU.format(own): 8 * GIB, DGPU.format(2288): int(65.85 * GIB), DGPU.format(3000): 2 * GIB})
        with patch('psutil.Process', side_effect=OSError('no real processes in tests')):
            plain = gpu_memory.holders(legacy, own)
        self.assertEqual([row['pid'] for row in plain], [2288, 3000])
        self.assertTrue(all(row['plausible'] is None for row in plain))

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
        # Another per-process reading above the whole adapter is not a credible holder even if it
        # falls inside the looser aggregate sampling margin.
        impossible_other = reading_with_totals({DGPU.format(40): int(4.8 * GIB), DGPU.format(2304): 5 * GIB},
                                               {DGPU_ADAPTER: 4 * GIB})
        self.assertIsNone(gpu_memory.others_bytes(impossible_other, 40))
        mixed = reading_with_totals({DGPU.format(40): int(4.8 * GIB), DGPU.format(2304): int(0.7 * GIB),
                                     DGPU.format(500): 5 * GIB}, {DGPU_ADAPTER: 4 * GIB})
        self.assertEqual(gpu_memory.others_bytes(mixed, 40), int(0.7 * GIB))

    def test_others_still_count_before_comfy_process_counter_appears(self):
        sample = reading_with_totals({DGPU.format(2304): 2 * GIB}, {DGPU_ADAPTER: 3 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 2 * GIB)

    def test_zero_byte_own_instance_on_another_adapter_does_not_pick_it(self):
        sample = reading_with_totals({IGPU.format(40): 0, IGPU.format(11): 300 * MIB, DGPU.format(2304): 11 * GIB},
                                     {DGPU_ADAPTER: 11 * GIB, IGPU_ADAPTER: 300 * MIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 11 * GIB)
        self.assertEqual(gpu_memory.others_for_admission(sample, 40), (11 * GIB, None))

    def test_zero_byte_own_instance_falls_back_in_legacy_readings(self):
        sample = reading({IGPU.format(40): 0, IGPU.format(11): 300 * MIB, DGPU.format(2304): 11 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 11 * GIB)

    def test_nonzero_own_instance_still_selects_its_adapter(self):
        sample = reading_with_totals({IGPU.format(40): 2 * GIB, IGPU.format(11): 300 * MIB, DGPU.format(2304): 11 * GIB},
                                     {IGPU_ADAPTER: 2 * GIB + 300 * MIB, DGPU_ADAPTER: 11 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 300 * MIB)

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

    def test_admission_stays_measured_for_a_matching_sample(self):
        sample = reading_with_totals({DGPU.format(2304): 2282 * MIB, DGPU.format(30868): 811 * MIB}, {DGPU_ADAPTER: 4 * GIB})
        self.assertEqual(gpu_memory.others_for_admission(sample, 30868), (2282 * MIB, None))

    def test_admission_is_unknown_when_process_counters_disagree(self):
        # 4 GiB adapter, owned 2 GiB, dwm at 66 GiB: the guard keeps the conservative
        # reconciled bound, but admission must not treat it as a measured fact.
        sample = reading_with_totals({DGPU.format(40): 2 * GIB, DGPU.format(2304): 66 * GIB}, {DGPU_ADAPTER: 4 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 2 * GIB)
        external, reason = gpu_memory.others_for_admission(sample, 40)
        self.assertIsNone(external)
        self.assertIn('disagree', reason)
        # A collective overshoot with no single excluded pid is likewise not measured.
        crowded = reading_with_totals({DGPU.format(7): 3 * GIB, DGPU.format(8): 3 * GIB}, {DGPU_ADAPTER: 4 * GIB})
        external, reason = gpu_memory.others_for_admission(crowded, 7)
        self.assertIsNone(external)
        self.assertIn('disagree', reason)

    def test_admission_is_unknown_without_a_matching_adapter(self):
        inflated = {DGPU.format(2304): DWM_ANOMALY, DGPU.format(30868): 812 * MIB}
        external, reason = gpu_memory.others_for_admission(reading_with_totals(inflated, None), 30868)
        self.assertIsNone(external)
        self.assertIsNotNone(reason)
        unmatched = reading_with_totals(inflated, {IGPU_ADAPTER: 512 * MIB})
        external, reason = gpu_memory.others_for_admission(unmatched, 30868)
        self.assertIsNone(external)
        self.assertIsNotNone(reason)
        # Older injected readings without the new field keep their old contract.
        legacy = reading({DGPU.format(1): 812 * MIB})
        self.assertEqual(gpu_memory.others_for_admission(legacy, 2), (812 * MIB, None))

    def test_adapter_figure_is_preferred_for_others_when_counters_agree(self):
        # Owner decision on #983 (27 Sep 2026): others = adapter dedicated usage minus ComfyUI's own. Own 8 GiB and
        # dwm 2 GiB on an 11 GiB adapter leave 1 GiB no process counter attributes; it is still not free.
        sample = reading_with_totals({DGPU.format(40): 8 * GIB, DGPU.format(2304): 2 * GIB}, {DGPU_ADAPTER: 11 * GIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 3 * GIB)
        self.assertEqual(gpu_memory.others_for_admission(sample, 40), (3 * GIB, None))
        launch = gpu_memory.launch_reserve_gib(sample)
        self.assertEqual((launch['others_bytes'], launch['basis'], launch['reserve_gib']), (11 * GIB, 'measured', gpu_memory.CAP_GIB))
        # An adapter figure below the attributed sum (sampling skew inside the headroom) never lowers a measured figure.
        skewed = reading_with_totals({DGPU.format(40): 3 * GIB, DGPU.format(2304): 2 * GIB}, {DGPU_ADAPTER: int(4.5 * GIB)})
        self.assertEqual(gpu_memory.others_bytes(skewed, 40), 2 * GIB)
        self.assertEqual(gpu_memory.others_for_admission(skewed, 40), (2 * GIB, None))

    def test_launch_reserve_subtracts_lagging_stopped_pids_from_the_adapter_figure(self):
        # A just-stopped ComfyUI (pid 5) can still show 9000 MiB; the adapter figure includes it while it lags.
        lagging = reading_with_totals({DGPU.format(2304): 2282 * MIB, DGPU.format(5): 9000 * MIB}, {DGPU_ADAPTER: (2282 + 9000 + 1024) * MIB})
        result = gpu_memory.launch_reserve_gib(lagging, exclude_pids=[5])
        self.assertEqual((result['others_bytes'], result['basis'], result['excluded_pids']), ((2282 + 1024) * MIB, 'measured', []))
        self.assertEqual(result['reserve_gib'], 4.0)
        # If the adapter has already released it but the process counter lags, the attributed sum still stands.
        released = reading_with_totals({DGPU.format(2304): 2282 * MIB, DGPU.format(5): 9000 * MIB}, {DGPU_ADAPTER: (2282 + 1024) * MIB})
        self.assertEqual(gpu_memory.launch_reserve_gib(released, exclude_pids=[5])['others_bytes'], 2282 * MIB)

    def test_zero_byte_own_igpu_entry_with_a_runaway_dgpu_counter_uses_the_adapter_total(self):
        # #1194 review LOW (recorded on #983).
        sample = reading_with_totals({IGPU.format(40): 0, IGPU.format(11): 300 * MIB, DGPU.format(2304): DWM_ANOMALY},
                                     {DGPU_ADAPTER: 14 * GIB, IGPU_ADAPTER: 300 * MIB})
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 14 * GIB)
        self.assertEqual(gpu_memory.others_for_admission(sample, 40), (None, 'GPU adapter and process counters disagree'))

    def test_process_values_are_bounded_by_the_adapter_figure(self):
        # 4.5 GiB against a 4 GiB adapter is inside the sampling headroom, so not an anomaly, but no process holds
        # more than the adapter reports in use.
        sample = reading_with_totals({DGPU.format(2304): int(4.5 * GIB), DGPU.format(40): 0}, {DGPU_ADAPTER: 4 * GIB})
        self.assertEqual(gpu_memory.launch_reserve_gib(sample)['others_bytes'], 4 * GIB)
        self.assertEqual(gpu_memory.others_bytes(sample, 40), 4 * GIB)
        with_anomaly = reading_with_totals({DGPU.format(40): GIB, DGPU.format(2304): int(4.5 * GIB), DGPU.format(9): DWM_ANOMALY},
                                           {DGPU_ADAPTER: 4 * GIB})
        with patch('psutil.Process', side_effect=OSError('no real processes in tests')):
            rows = gpu_memory.holders(with_anomaly, 40)
        # The counted row is bounded; the impossible one keeps its raw value as evidence.
        self.assertEqual([(row['pid'], row['dedicated_bytes'], row['plausible']) for row in rows],
                         [(2304, 4 * GIB, True), (9, DWM_ANOMALY, False)])

    def test_capacity_turns_an_impossible_total_less_result_into_unknown(self):
        legacy = reading({DGPU.format(40): 8 * GIB, DGPU.format(2304): DWM_ANOMALY})
        self.assertEqual(gpu_memory.others_bytes(legacy, 40), DWM_ANOMALY)          # no capacity: the old contract
        self.assertIsNone(gpu_memory.others_bytes(legacy, 40, capacity_bytes=16 * GIB))
        external, reason = gpu_memory.others_for_admission(legacy, 40, capacity_bytes=16 * GIB)
        self.assertIsNone(external); self.assertIn('capacity', reason)
        plausible = reading({DGPU.format(40): 8 * GIB, DGPU.format(2304): 2 * GIB})
        self.assertEqual(gpu_memory.others_bytes(plausible, 40, capacity_bytes=16 * GIB), 2 * GIB)
        self.assertEqual(gpu_memory.others_for_admission(plausible, 40, capacity_bytes=16 * GIB), (2 * GIB, None))
        agreeing = reading_with_totals({DGPU.format(40): 8 * GIB, DGPU.format(2304): 2 * GIB}, {DGPU_ADAPTER: 11 * GIB})
        self.assertEqual(gpu_memory.others_for_admission(agreeing, 40, capacity_bytes=16 * GIB), (3 * GIB, None))

    def test_anomalies_are_bounded_evidence_rows(self):
        sample = reading_with_totals({DGPU.format(40): 2 * GIB, DGPU.format(2304): DWM_ANOMALY, DGPU.format(30868): 812 * MIB},
                                     {DGPU_ADAPTER: 4 * GIB})
        limit = int(4 * GIB * gpu_memory.RECONCILE_RATIO + gpu_memory.RECONCILE_SLOP_BYTES)
        self.assertEqual(gpu_memory.anomalies(sample), [{'adapter': DGPU_ADAPTER, 'pid': 2304, 'dedicated_bytes': DWM_ANOMALY,
                                                          'adapter_total_bytes': 4 * GIB, 'limit_bytes': limit}])
        self.assertEqual(gpu_memory.anomalies(reading_with_totals({DGPU.format(1): GIB}, {DGPU_ADAPTER: 4 * GIB})), [])
        for empty in (None, {}, {'adapters': None}): self.assertEqual(gpu_memory.anomalies(empty), [])
        # Without an adapter figure only a known capacity rules a counter out.
        legacy = reading({DGPU.format(2304): DWM_ANOMALY, DGPU.format(1): GIB})
        self.assertEqual(gpu_memory.anomalies(legacy), [])
        self.assertEqual(gpu_memory.anomalies(legacy, capacity_bytes=16 * GIB),
                         [{'adapter': DGPU_ADAPTER, 'pid': 2304, 'dedicated_bytes': DWM_ANOMALY, 'adapter_total_bytes': None, 'limit_bytes': 16 * GIB}])
        crowded = reading_with_totals({DGPU.format(pid): (70 + pid) * GIB for pid in range(12)}, {DGPU_ADAPTER: 4 * GIB})
        rows = gpu_memory.anomalies(crowded)
        self.assertEqual(len(rows), gpu_memory.ANOMALY_ROWS); self.assertEqual(gpu_memory.ANOMALY_ROWS, 8)
        self.assertEqual([row['pid'] for row in rows], [11, 10, 9, 8, 7, 6, 5, 4])
        # The launch decision carries the rows from the same reading.
        self.assertEqual([row['pid'] for row in gpu_memory.launch_reserve_gib(sample)['anomalies']], [2304])
        self.assertEqual(gpu_memory.launch_reserve_gib({'adapters': None, 'unknown_reason': 'x'})['anomalies'], [])

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
