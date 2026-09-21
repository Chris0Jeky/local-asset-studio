"""New byte-bound receipts must not change the canonical legacy read contract."""
import hashlib
import unittest
from unittest.mock import patch

from studio_workflow import revision_consistency as values
from studio_workflow.core import MAX_BYTES


class ExactStoredValueTests(unittest.TestCase):
    def read(self, raw, digest=None, limit=4096):
        self.assertTrue(hasattr(values, 'exact_stored_value'), 'Exact stored-byte binding is missing')
        actual = raw.encode('utf-8') if isinstance(raw, str) else raw
        return values.exact_stored_value(raw, digest or hashlib.sha256(actual).hexdigest(), max_bytes=limit)

    def test_retains_exact_utf8_bytes_and_separate_digest_facts(self):
        raw = '{ "message": "α", "value": 1 }\n'
        record = self.read(raw)
        self.assertEqual(record.raw, raw.encode('utf-8'))
        self.assertEqual(record.bytes, len(raw.encode('utf-8')))
        self.assertEqual(record.value, {'message': 'α', 'value': 1})
        self.assertTrue(record.matches)
        self.assertEqual(record.observed_sha256, hashlib.sha256(record.raw).hexdigest())
        changed = self.read(raw, '0' * 64)
        self.assertFalse(changed.matches)
        self.assertEqual(changed.stored_sha256, '0' * 64)
        self.assertEqual(changed.observed_sha256, record.observed_sha256)

    def test_whitespace_cannot_be_repaired_into_a_matching_byte_digest(self):
        bound = values.canonical_value({'a': 1})
        spaced = b'{ "a" : 1 }'
        self.assertTrue(values.stored_value(spaced, bound.sha256).matches)
        exact = self.read(spaced, bound.sha256)
        self.assertFalse(exact.matches)
        self.assertEqual(exact.raw, spaced)
        self.assertEqual(self.read(bound.raw, bound.sha256).value, exact.value)

    def test_unicode_byte_limit_not_character_limit(self):
        raw = '"α"'
        self.assertEqual(self.read(raw, limit=4).bytes, 4)
        with self.assertRaisesRegex(ValueError, 'limit'):
            self.read(raw, limit=3)

    def test_limit_is_checked_before_decode(self):
        self.assertTrue(hasattr(values, 'exact_stored_value'))
        with patch.object(values, 'decode', side_effect=AssertionError('Oversized input was decoded')):
            with self.assertRaises(ValueError):
                values.exact_stored_value(b' ' * 17, '0' * 64, max_bytes=16)

    def test_exact_global_limit_is_accepted_and_one_byte_over_is_refused(self):
        raw = b'"' + b'x' * (MAX_BYTES - 2) + b'"'
        self.assertEqual(self.read(raw, limit=MAX_BYTES).bytes, MAX_BYTES)
        with self.assertRaises(ValueError):
            self.read(raw + b' ', limit=MAX_BYTES)

    def test_invalid_limits_are_not_silently_coerced(self):
        for limit in (True, False, -1, 0, 1.0, '12', None, MAX_BYTES + 1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.read(b'{}', limit=limit)

    def test_nontext_storage_values_are_refused(self):
        self.assertTrue(hasattr(values, 'exact_stored_value'))
        for raw in (None, 4, {}, [], bytearray(b'{}'), memoryview(b'{}')):
            with self.subTest(raw=type(raw).__name__), self.assertRaises(ValueError):
                values.exact_stored_value(raw, '0' * 64, max_bytes=4096)

    def test_strict_json_rejections_survive_exact_byte_binding(self):
        malformed = [b'{', b'{"a":1,"a":2}', b'{"__proto__":1}', b'NaN', b'Infinity',
                     b'1e999', b'"\xff"', b'[' * 50 + b'0' + b']' * 50]
        for raw in malformed:
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                self.read(raw)

    def test_storage_encoding_is_utf8_not_json_encoding_autodetection(self):
        for encoding in ('utf-16', 'utf-32', 'utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be'):
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                self.read('{"name":"ascii"}'.encode(encoding))

    def test_escaped_nul_remains_legal_utf8_json(self):
        self.assertEqual(self.read(b'"\\u0000"').value, '\x00')

    def test_input_and_digest_are_not_rewritten(self):
        raw = b' {"ordered":[2,1],"negative":-0.0} '
        record = self.read(raw, 'bad-digest')
        self.assertEqual(record.raw, raw)
        self.assertFalse(record.matches)
        self.assertEqual(record.stored_sha256, 'bad-digest')
        record.value['ordered'].append(9)
        self.assertEqual(record.raw, raw)
        self.assertEqual(record.observed_sha256, hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    unittest.main()
