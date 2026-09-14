"""Saved trace contracts: bounded, payload-free and overlap-aware."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
try:
    import inference_trace as subject
except ModuleNotFoundError:
    subject = None


def event(cat='cpu_op', name='aten::mm', ts=100, dur=10, pid=1, tid=2, ph='X', **extra):
    return dict(ph=ph, cat=cat, name=name, ts=ts, dur=dur, pid=pid, tid=tid, **extra)


def wire(events, **extra):
    return json.dumps(dict(schemaVersion=1, traceEvents=events, **extra)).encode()


class InferenceTraceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(subject, 'The offline trace reducer has not been implemented')

    def reject(self, raw, code):
        with self.assertRaisesRegex(subject.TraceError, '^' + code + '$'):
            subject.summarize_trace(raw)

    def test_nested_cpu_spans_are_not_additive_wall_time(self):
        result = subject.summarize_trace(wire([event(ts=0, dur=100), event(ts=20, dur=60)]))
        lane = result['lanes'][0]
        self.assertEqual(lane['inclusive_duration_ns'], 160000)
        self.assertEqual(lane['active_union_ns'], 100000)
        self.assertEqual(lane['span_ns'], 100000)
        self.assertIsNone(result['job_wall_time_ns'])
        self.assertFalse(result['causal_speedup_qualified'])

    def test_device_lanes_remain_separate_from_cpu_and_each_other(self):
        rows = [event(), event('kernel', 'private kernel', pid=0, tid=7),
                event('kernel', 'private kernel', pid=0, tid=8),
                event('gpu_memcpy', 'Memcpy HtoD', pid=0, tid=7)]
        result = subject.summarize_trace(wire(rows))
        self.assertEqual(len(result['lanes']), 4)
        self.assertEqual(result['device_timing']['status'], 'observed')
        self.assertIsNone(result['device_timing']['coverage'])
        self.assertNotIn('total_gpu_time_ns', result)

    def test_missing_device_events_are_unavailable_not_zero(self):
        result = subject.summarize_trace(wire([event()]))
        self.assertEqual(result['device_timing'], {'status': 'unavailable', 'coverage': None,
                          'reason': 'no_supported_device_spans'})
        self.assertEqual(result['job_binding'], 'unbound')

    def test_unknown_categories_and_non_complete_phases_are_disclosed(self):
        rows = [event(), event('user_annotation', 'private prompt'), event(ph='B'),
                {'ph': 'M', 'name': 'process_name', 'args': {'name': 'private path'}}]
        result = subject.summarize_trace(wire(rows))
        self.assertEqual(result['recognized_events'], 1)
        self.assertEqual(result['ignored_events'], 3)
        self.assertEqual(result['unsupported_duration_events'], 2)
        self.assertEqual(result['status'], 'observed_subset')

    def test_metadata_only_trace_is_not_claimed_empty_success(self):
        result = subject.summarize_trace(wire([{'ph': 'M'}]))
        self.assertEqual(result['status'], 'no_supported_events')
        self.assertEqual(result['lanes'], [])
        self.assertEqual(result['device_timing']['status'], 'unavailable')

    def test_microseconds_are_not_display_time_units(self):
        raw = wire([event(ts=100, dur=2)], displayTimeUnit='ms')
        self.assertEqual(subject.summarize_trace(raw)['lanes'][0]['inclusive_duration_ns'], 2000)

    def test_decimal_timestamp_arithmetic_is_exact_at_large_offsets(self):
        raw = b'{"schemaVersion":1,"traceEvents":[{"ph":"X","cat":"cpu_op","name":"aten::mm","pid":1,"tid":1,"ts":6454227037136.212,"dur":0.001}]}'
        lane = subject.summarize_trace(raw)['lanes'][0]
        self.assertEqual(lane['active_union_ns'], 1)
        self.assertEqual(lane['span_ns'], 1)

    def test_extreme_fraction_cannot_round_to_an_integer_nanosecond(self):
        base = wire([event()]).replace(b'"dur": 10', b'"dur": 0.0010000000000000000000000000000000000001')
        self.reject(base, 'trace_time_precision')
        base = wire([event()]).replace(b'"dur": 10', b'"dur": 1e-1000000')
        self.reject(base, 'trace_time_precision')

    def test_zero_duration_is_a_legitimate_observation(self):
        result = subject.summarize_trace(wire([event('kernel', dur=0)]))
        self.assertEqual(result['device_timing']['status'], 'observed')
        self.assertEqual(result['lanes'][0]['active_union_ns'], 0)

    def test_unsorted_overlapping_and_touching_intervals(self):
        spans = [event(ts=25,dur=5), event(ts=0,dur=10), event(ts=8,dur=4), event(ts=12,dur=3)]
        lane = subject.summarize_trace(wire(spans))['lanes'][0]
        self.assertEqual(lane['active_union_ns'], 20000)
        self.assertEqual(lane['span_ns'], 30000)

    def test_reordered_events_keep_same_projection_apart_from_input_hash(self):
        rows = [event(ts=40), event(name='aten::copy_', ts=1), event('kernel', pid=0,tid=0)]
        a = subject.summarize_trace(wire(rows)); b = subject.summarize_trace(wire(rows[::-1]))
        a.pop('input_sha256'); b.pop('input_sha256')
        self.assertEqual(a, b)

    def test_input_hash_pins_exact_bytes(self):
        raw = wire([event()]); identity = hashlib.sha256(raw).hexdigest()
        self.assertEqual(subject.summarize_trace(raw, expected_sha256=identity)['input_sha256'], identity)
        with self.assertRaisesRegex(subject.TraceError, '^trace_hash_mismatch$'):
            subject.summarize_trace(raw, expected_sha256='0'*64)
        for invalid in ('a', True, 'A'*64):
            with self.assertRaisesRegex(subject.TraceError, '^expected_hash_invalid$'):
                subject.summarize_trace(raw, expected_sha256=invalid)

    def test_no_private_labels_paths_arguments_or_ids_echoed(self):
        secret = 'CANARY_private_prompt_C:/users/private.bin'
        result = subject.summarize_trace(wire([event(name=secret,pid=secret,tid=secret,args={'prompt':secret}),
                                              event('kernel',secret,pid=secret,tid=secret)],
                                             traceName=secret, deviceProperties=[{'name':secret}]))
        text = json.dumps(result)
        self.assertNotIn(secret, text)
        self.assertNotIn('deviceProperties', text)
        self.assertTrue(all(len(row['identity_sha256']) == 64 for row in result['operators']))

    def test_only_fixed_allowlisted_operator_names_are_returned(self):
        result = subject.summarize_trace(wire([event(name='aten::private_prompt'), event(name='aten::mm')]))
        self.assertEqual({row['label'] for row in result['operators']}, {'redacted', 'aten::mm'})

    def test_boolean_and_string_process_ids_do_not_collide_with_integers(self):
        self.reject(wire([event(pid=True)]), 'trace_lane_invalid')
        result = subject.summarize_trace(wire([event(pid=1), event(pid='1')]))
        self.assertEqual(len(result['lanes']), 2)

    def test_invalid_recognized_events_fail_instead_of_disappearing(self):
        for field, value, code in [('ts',True,'trace_time_invalid'), ('dur',-1,'trace_time_invalid'),
                                  ('dur','2','trace_time_invalid'), ('pid',None,'trace_lane_invalid'),
                                  ('name',[],'trace_name_invalid'), ('dur',0.0001,'trace_time_precision')]:
            with self.subTest(field=field,value=value): self.reject(wire([event(**{field:value})]), code)

    def test_extreme_numbers_and_nonfinite_values_refuse(self):
        for value in (float('nan'), float('inf'), 10**40):
            with self.subTest(value=value):
                with self.assertRaises(subject.TraceError): subject.summarize_trace(wire([event(ts=value)]))
        self.reject(wire([event(dur=300000001)]), 'trace_time_invalid')

    def test_unknown_or_missing_format_and_malformed_json_refuse(self):
        for raw in (b'{}', b'[]', b'{"schemaVersion":true,"traceEvents":[]}', b'{"schemaVersion":2,"traceEvents":[]}'):
            with self.subTest(raw=raw): self.reject(raw, 'trace_format_unsupported')
        for raw in (b'', b'{', b'\xff', b'{"schemaVersion":1,"schemaVersion":1,"traceEvents":[]}'):
            with self.subTest(raw=raw): self.reject(raw, 'trace_json_invalid')

    def test_unrepresentable_decimal_is_a_payload_free_error(self):
        raw = b'{"schemaVersion":1,"traceEvents":[],"CANARY":1e999999999999999999999999999999}'
        self.reject(raw, 'trace_json_invalid')

    def test_non_event_member_refuses(self):
        self.reject(wire([None]), 'trace_event_invalid')
        self.reject(wire([event(ph=1)]), 'trace_event_invalid')

    def test_limits_reject_before_creating_a_partial_report(self):
        with patch.object(subject, 'MAX_BYTES', 10): self.reject(wire([]), 'trace_too_large')
        with patch.object(subject, 'MAX_EVENTS', 1): self.reject(wire([event(),event()]), 'trace_events_exceeded')
        with patch.object(subject, 'MAX_LANES', 1): self.reject(wire([event(tid=1),event(tid=2)]), 'trace_lanes_exceeded')
        with patch.object(subject, 'MAX_OPERATORS', 1):
            self.reject(wire([event(name='a'),event(name='b')]), 'trace_operators_exceeded')

    def test_deep_json_and_surrogates_refuse_without_echo(self):
        nested = 1
        for _ in range(40): nested = [nested]
        self.reject(wire([], extra=nested), 'trace_json_invalid')
        self.reject(wire([event(name='\ud800')]), 'trace_json_invalid')

    def test_output_operator_rows_are_bounded_with_omitted_count(self):
        result = subject.summarize_trace(wire([event(name=f'op{i}',dur=i) for i in range(40)]))
        self.assertEqual(len(result['operators']),32)
        self.assertEqual(result['omitted_operator_rows'],8)
        self.assertEqual(result['recognized_events'],40)

    def test_caller_bytes_are_not_mutated(self):
        raw = wire([event()]); before = raw[:]
        subject.summarize_trace(raw)
        self.assertEqual(raw,before)

    def test_import_does_not_import_torch_or_start_a_server(self):
        import subprocess
        root=Path(__file__).resolve().parents[1]
        code="import sys; sys.path.insert(0, 'app'); import inference_trace; assert 'torch' not in sys.modules; assert 'server' not in sys.modules"
        result=subprocess.run([sys.executable,'-c',code],cwd=root,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__': unittest.main()
