"""Incremental trace parsing consumes the complete bounded source before reporting."""
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import inference_trace as eager
try:
    import inference_trace_stream as streamed
except ModuleNotFoundError:
    streamed = None


def event(**changes):
    result = dict(ph='X', cat='cpu_op', name='aten::mm', pid=1, tid=2, ts=1, dur=2)
    result.update(changes)
    return result


def wire(events=(), **extra):
    return json.dumps(dict(schemaVersion=1, traceEvents=list(events), **extra), ensure_ascii=False).encode()


class Chunks(io.BytesIO):
    def __init__(self, raw, sizes=(1,)):
        super().__init__(raw); self.sizes = sizes; self.requests = []

    def read(self, count=-1):
        if type(count) is not int or not 0 < count <= 65536:
            raise AssertionError('Reader requested an unbounded or oversized read')
        self.requests.append(count)
        return super().read(min(count, self.sizes[(len(self.requests)-1) % len(self.sizes)]))


class TraceStreamTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(streamed, 'Incremental trace inspection has not been implemented')

    def inspect(self, raw, sizes=(65536,), **options):
        stream = Chunks(raw, sizes)
        result = streamed.summarize_trace_stream(stream, **options)
        self.assertEqual(stream.tell(), len(raw))
        self.assertFalse(stream.closed)
        return result

    def reject(self, raw, code=None, sizes=(65536,)):
        with self.assertRaises(eager.TraceError) as raised:
            self.inspect(raw, sizes)
        if code: self.assertEqual(raised.exception.code, code)
        self.assertNotIn('CANARY', str(raised.exception))

    def test_real_producer_fixture_is_exactly_equal_to_small_reader(self):
        raw = (Path(__file__).parent / 'fixtures/inference_trace_cpu.json').read_bytes()
        self.assertEqual(self.inspect(raw, (1, 7, 63, 4096)), eager.summarize_trace(raw))

    def test_one_byte_reads_preserve_numbers_strings_escapes_and_utf8(self):
        raw = wire([event(ts=12.125, dur=0.001, args={'text': 'a\\b "c" \u00e9 \U0001f30d'})],
                   note='CANARY private text', scalar=1e20)
        self.assertEqual(self.inspect(raw, (1,)), eager.summarize_trace(raw))
        self.assertNotIn('CANARY', json.dumps(self.inspect(raw, (1,))))

    def test_numeric_prefix_never_commits_before_exponent_or_fraction(self):
        for token in ('1e+3', '1.000', '-1e-3', '1e-100000', '0.0001'):
            with self.subTest(token=token):
                raw = wire([event()])[:-1] + b', "other": ' + token.encode() + b'}'
                self.assertEqual(self.inspect(raw, (1,)), eager.summarize_trace(raw))

    def test_schema_after_events_is_validated_before_success(self):
        raw = b'{"traceEvents":[' + json.dumps(event()).encode() + b'],"schemaVersion":1}'
        self.assertEqual(self.inspect(raw, (3,)), eager.summarize_trace(raw))
        for suffix in (b'2}', b'true}', b'null}'):
            self.reject(raw[:-2] + suffix, 'trace_format_unsupported', (3,))

    def test_unsorted_nested_cross_lane_spans_keep_exact_metrics(self):
        rows = [event(ts=20,dur=60),event(ts=0,dur=100),event(tid='2',ts=30,dur=5),
                event(cat='kernel',name='CANARY kernel',pid=0,tid=7,ts=2,dur=100),
                event(cat='kernel',name='CANARY kernel',pid=0,tid=8,ts=2,dur=100)]
        raw=wire(rows)
        self.assertEqual(self.inspect(raw, (19,53)), eager.summarize_trace(raw))
        result=self.inspect(raw)
        self.assertIsNone(result['job_wall_time_ns'])
        self.assertFalse(result['causal_speedup_qualified'])

    def test_hash_covers_ignored_metadata_and_trailing_whitespace(self):
        raw=wire([event()], note='ignored') + b' \r\n\t'
        digest=hashlib.sha256(raw).hexdigest()
        self.assertEqual(self.inspect(raw,(5,),expected_sha256=digest)['input_sha256'],digest)
        with self.assertRaisesRegex(eager.TraceError,'^trace_hash_mismatch$'):
            self.inspect(raw,expected_sha256='0'*64)

    def test_invalid_expected_hash_refuses_before_read(self):
        stream=Chunks(wire())
        with self.assertRaisesRegex(eager.TraceError,'^expected_hash_invalid$'):
            streamed.summarize_trace_stream(stream,expected_sha256=True)
        self.assertEqual(stream.requests,[])

    def test_more_than_small_event_cap_is_supported_without_changing_defaults(self):
        raw=wire([event(ts=i) for i in range(4097)])
        result=self.inspect(raw)
        self.assertEqual(result['recognized_events'],4097)
        with self.assertRaises(eager.TraceError):eager.summarize_trace(raw)
        self.assertEqual((eager.MAX_BYTES,eager.MAX_EVENTS,eager.MAX_OPERATORS),(1048576,4096,128))

    def test_thousands_of_distinct_operator_identities_have_bounded_output(self):
        raw=wire([event(name=f'private operator {i}') for i in range(2048)])
        result=self.inspect(raw)
        self.assertEqual(len(result['operators']),32)
        self.assertEqual(result['omitted_operator_rows'],2016)
        self.assertNotIn('private operator',json.dumps(result))

    def test_large_ignored_payloads_are_discarded_but_input_identity_is_complete(self):
        rows=[event(args={'CANARY':'x'*2000}) for _ in range(600)]
        raw=wire(rows)
        self.assertGreater(len(raw),1048576)
        result=self.inspect(raw)
        self.assertEqual(result['input_bytes'],len(raw))
        self.assertEqual(result['recognized_events'],600)
        self.assertEqual(result['input_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertNotIn('CANARY',json.dumps(result))

    def test_late_bad_event_does_not_return_partial_metrics(self):
        self.reject(wire([event()]*100 + [event(dur=-1)]),'trace_time_invalid',(4096,))

    def test_truncated_documents_and_extra_documents_refuse(self):
        valid=wire([event()])
        for raw in (valid[:-1],valid[:-2],valid+b'{}',valid+b'null',b'[]',b'',b'{'):
            with self.subTest(raw=raw[:40]):self.reject(raw,sizes=(1,))

    def test_duplicate_top_level_and_nested_keys_refuse(self):
        for raw in (b'{"schemaVersion":1,"traceEvents":[],"traceEvents":[]}',
                    b'{"schemaVersion":1,"traceEvents":[],"schemaVersion":1}',
                    b'{"schemaVersion":1,"traceEvents":[],"meta":{"a":1,"a":2}}'):
            with self.subTest(raw=raw):self.reject(raw,'trace_json_invalid',(1,))

    def test_corrupt_ignored_metadata_and_nonfinite_numbers_refuse(self):
        for value in (b'NaN',b'Infinity',b'01',b'1e',b'1.',b'{"CANARY":}',b'[1,]'):
            raw=b'{"schemaVersion":1,"traceEvents":[],"meta":'+value+b'}'
            with self.subTest(value=value):self.reject(raw,sizes=(1,))

    def test_invalid_utf8_and_surrogate_values_refuse(self):
        for value in (b'"\xff"',b'"\xe2\x82"',b'"\\ud800"'):
            raw=b'{"schemaVersion":1,"traceEvents":[],"meta":'+value+b'}'
            with self.subTest(value=value):self.reject(raw,'trace_json_invalid',(1,))

    def test_root_key_missing_schema_and_wrong_event_array_refuse(self):
        for raw in (b'{"traceEvents":[]}',b'{"schemaVersion":1}',
                    b'{"schemaVersion":1,"traceEvents":{}}',b'{1:2}',
                    b'{"schemaVersion":1,"traceEvents":[],}'):
            with self.subTest(raw=raw):self.reject(raw,sizes=(1,))

    def test_depth_is_counted_from_document_root(self):
        nested=[]
        for _ in range(30):nested=[nested]
        self.assertEqual(self.inspect(wire(meta=nested)),eager.summarize_trace(wire(meta=nested)))
        self.reject(wire(meta=[nested]),'trace_json_invalid')
        event_nested=[]
        for _ in range(28):event_nested=[event_nested]
        raw=wire([event(args=event_nested)])
        self.assertEqual(self.inspect(raw),eager.summarize_trace(raw))
        self.reject(wire([event(args=[event_nested])]),'trace_json_invalid')

    def test_byte_value_event_and_key_caps_fail_closed(self):
        with patch.object(streamed,'MAX_STREAM_BYTES',20):self.reject(wire(),'trace_too_large')
        with patch.object(streamed,'MAX_VALUE_BYTES',64):self.reject(wire(meta='x'*100),'trace_value_too_large')
        with patch.object(streamed,'MAX_STREAM_EVENTS',1):self.reject(wire([event(),event()]),'trace_events_exceeded')
        with patch.object(streamed,'MAX_TOP_KEYS',2):self.reject(wire(meta=None),'trace_keys_exceeded')
        self.reject(wire(**{'k'*257:None}),'trace_key_invalid')

    def test_large_operator_and_existing_lane_limits_stay_finite(self):
        with patch.object(streamed,'MAX_STREAM_OPERATORS',2):
            self.reject(wire([event(name=str(i)) for i in range(3)]),'trace_operators_exceeded')
        self.reject(wire([event(tid=i) for i in range(65)]),'trace_lanes_exceeded')

    def test_value_cap_counts_utf8_bytes_not_characters(self):
        with patch.object(streamed,'MAX_VALUE_BYTES',32):
            self.reject(wire(meta='\U0001f30d'*9),'trace_value_too_large',(1,))

    def test_whitespace_and_chunk_boundary_at_exact_limit(self):
        raw=b' \r\n'+wire([event()])+b' '*1000
        with patch.object(streamed,'MAX_STREAM_BYTES',len(raw)):
            result=self.inspect(raw,(17,))
        self.assertEqual(result['input_bytes'],len(raw))
        with patch.object(streamed,'MAX_STREAM_BYTES',len(raw)-1):
            self.reject(raw,'trace_too_large',(17,))

    def test_completed_numeric_prefix_obeys_value_cap_before_next_refill(self):
        raw = b'{"schemaVersion":1,"traceEvents":[],"meta":1.' + b'0'*20000 + b'}'
        source = Chunks(raw, (64,))
        with patch.object(streamed, 'MAX_VALUE_BYTES', 128):
            with self.assertRaisesRegex(eager.TraceError, '^trace_value_too_large$'):
                streamed.summarize_trace_stream(source)
        self.assertLess(source.tell(), 512, 'A numeric prefix must not accumulate the whole source')

    def test_nonbinary_and_oversized_reader_responses_refuse(self):
        class Bad:
            def __init__(self,value):self.value=value
            def read(self,count):return self.value
        for value in (None,'text',b'x'*65537):
            with self.subTest(value_type=type(value)):
                with self.assertRaisesRegex(eager.TraceError,'^trace_stream_invalid$'):
                    streamed.summarize_trace_stream(Bad(value))

    def test_missing_device_observation_never_becomes_zero(self):
        result=self.inspect(wire([event()]))
        self.assertEqual(result['device_timing']['status'],'unavailable')
        self.assertIsNone(result['device_timing']['coverage'])
        self.assertEqual(result['producer_identity'],'unverified')
        self.assertEqual(result['job_binding'],'unbound')


if __name__=='__main__':unittest.main()
