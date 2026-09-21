"""Single-pass framing must not repeatedly decode incomplete bounded values."""
import hashlib
import io
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import inference_trace as eager
import inference_trace_stream as streamed


class ShortReads(io.BytesIO):
    def __init__(self, raw, sizes):
        super().__init__(raw); self.sizes = sizes; self.calls = 0

    def read(self, count=-1):
        if not 0 < count <= 65536: raise AssertionError('Unbounded read')
        size = self.sizes[self.calls % len(self.sizes)]; self.calls += 1
        return super().read(min(count, size))


def trace(token):
    return b'{"schemaVersion":1,"traceEvents":[],"meta":' + token + b'}'


def decode_spy():
    calls = []
    class Decoder(json.JSONDecoder):
        def raw_decode(self, text, *args, **kwargs):
            calls.append(len(text.encode('utf-8')))
            return super().raw_decode(text, *args, **kwargs)
    return calls, patch.object(json, 'JSONDecoder', Decoder)


class Framing(unittest.TestCase):
    def test_each_value_is_decoded_once_independent_of_fragmentation(self):
        for token in (json.dumps('x'*16000).encode(), b'1.'+b'0'*8000,
                      json.dumps({'x': ['quote \\" {}[] '*1000]}).encode()):
            raw = trace(token)
            for sizes in ((1,), (2, 7, 19, 3), (65536,)):
                with self.subTest(token_length=len(token), sizes=sizes):
                    calls, spy = decode_spy()
                    with spy:
                        result = streamed.summarize_trace_stream(ShortReads(raw, sizes))
                    self.assertEqual(5, len(calls), 'Keys and complete values each decode once, never prefixes')
                    self.assertLessEqual(sum(calls), len(raw))
                    self.assertEqual(eager.summarize_trace(raw), result)

    def test_value_cap_precedes_decoding_including_multibyte_payloads(self):
        for token in (json.dumps('x'*200, ensure_ascii=False).encode(),
                      json.dumps('🌍'*60, ensure_ascii=False).encode(), b'1.'+b'0'*200):
            calls, spy = decode_spy()
            with spy, patch.object(streamed, 'MAX_VALUE_BYTES', 64):
                with self.assertRaisesRegex(eager.TraceError, '^trace_value_too_large$'):
                    streamed.summarize_trace_stream(ShortReads(trace(token), (65,)))
            self.assertTrue(all(size <= 64 for size in calls), calls)

    def test_all_two_piece_boundaries_keep_tokens_hash_and_eof_semantics(self):
        tokens = [b'1e+03', b'-1e-1000', b'1.2500', b'true', b'false', b'null',
                  b'"\\uD83C\\uDF0D\\\\\\\"{}[]"',
                  json.dumps({'clé': ['a\\b"{}[]', '🌍', 2**63-1, None]}, ensure_ascii=False).encode()]
        for token in tokens:
            raw = trace(token)+b'\r\n\t '
            expected = eager.summarize_trace(raw)
            for cut in range(1, len(raw)):
                with self.subTest(token=token[:20], cut=cut):
                    self.assertEqual(expected, streamed.summarize_trace_stream(
                        ShortReads(raw, (cut, 65536)), expected_sha256=hashlib.sha256(raw).hexdigest()))

    def test_every_incomplete_prefix_and_bad_ignored_value_is_rejected(self):
        raw = trace(json.dumps({'CANARY': ['🌍', 'a\\b"{}[]', 2**63-1]}, ensure_ascii=False).encode())
        for cut in range(len(raw)):
            with self.subTest(cut=cut), self.assertRaises(eager.TraceError):
                streamed.summarize_trace_stream(ShortReads(raw[:cut], (1, 3, 2)))
        for token in (b'01', b'1e+', b'--1', b'NaN', b'"unterminated', b'[{]}', b'{"x":1,}',
                      b'{"a":1,"\\u0061":2}', b'[truefalse]', b'"\\ud800"', b'"\xff"'):
            raw = trace(token)
            with self.subTest(token=token), self.assertRaises(eager.TraceError):
                streamed.summarize_trace_stream(ShortReads(raw, (1, 5, 13)))

    def test_seeded_shared_input_differential_matrix(self):
        rng = random.Random(401)
        for case in range(300):
            events = []
            for _ in range(rng.randrange(1, 12)):
                events.append(dict(ph=rng.choice(['X','M']), cat=rng.choice(['cpu_op','kernel','unknown']),
                    name=rng.choice(['aten::mm','private CANARY']), pid=rng.choice([0,1,'1']),
                    tid=rng.randrange(4), ts=rng.randrange(100000), dur=rng.randrange(10000),
                    args={'opaque': rng.choice([None, [1,2], {'k':'🌍 "}\\[]'}])}))
            value = dict(traceEvents=events, metadata=[True, None, {'future':2**64-1}], schemaVersion=1)
            raw = json.dumps(value, ensure_ascii=bool(case%2), separators=(',',':')).encode()
            sizes = tuple(rng.randrange(1, 65) for _ in range(5))
            self.assertEqual(eager.summarize_trace(raw), streamed.summarize_trace_stream(ShortReads(raw, sizes)))

    def test_stream_error_class_stays_import_compatible(self):
        self.assertIs(eager.TraceError, streamed.TraceError)

    def test_report_cap_still_refuses_only_after_complete_source_validation(self):
        source = ShortReads(trace(b'null'), (1,))
        with patch.object(eager, 'MAX_REPORT_BYTES', 128):
            with self.assertRaisesRegex(eager.TraceError, '^trace_report_too_large$'):
                streamed.summarize_trace_stream(source)
        self.assertEqual(source.tell(), len(source.getvalue()))

    def test_source_read_failure_after_complete_json_cannot_return_success(self):
        raw = trace(b'null')
        class Failing(ShortReads):
            def read(self, count=-1):
                if self.tell() == len(raw): raise OSError('synthetic read failure')
                return super().read(count)
        with self.assertRaises(OSError): streamed.summarize_trace_stream(Failing(raw, (3,)))


if __name__ == '__main__': unittest.main()
