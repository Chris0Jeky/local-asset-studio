"""Finite-number admission at the shared Prompt JSON boundary."""
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio_prompt import schema


class PromptJsonNumberTests(unittest.TestCase):
    def test_overflowing_exponents_are_rejected_at_every_depth(self):
        for token in (b'1e309', b'-1e309', b'1E+9999', b'-9.9e9999'):
            for raw in (token, b'['+token+b']', b'{"outer":[{"value":'+token+b'}]}'):
                with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'Nonfinite JSON number'):
                    schema.decode(raw)

    def test_large_decimal_without_exponent_cannot_create_infinity(self):
        raw=b'9'*400+b'.0'
        with self.assertRaisesRegex(ValueError, 'Nonfinite JSON number'):
            schema.decode(raw)

    def test_existing_nonfinite_constant_rejection_is_preserved(self):
        for raw in (b'NaN', b'Infinity', b'-Infinity', b'{"value":NaN}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'Nonfinite JSON number'):
                schema.decode(raw)

    def test_finite_floats_keep_normal_json_semantics(self):
        for token in ('1e308', '-1e308', '0.125', '1e-9999', '-0.0'):
            with self.subTest(token=token):
                value=schema.decode(token.encode('ascii'))
                self.assertIs(type(value),float)
                self.assertTrue(math.isfinite(value))
                self.assertEqual(value,float(token))
                self.assertEqual(math.copysign(1,value),math.copysign(1,float(token)))

    def test_integer_precision_and_non_numeric_types_do_not_change(self):
        value=schema.decode(b'{"integer":9007199254740993,"flag":true,"none":null,"text":"1e9999"}')
        self.assertEqual(value,{'integer':9007199254740993,'flag':True,'none':None,'text':'1e9999'})
        self.assertIs(type(value['integer']),int)
        self.assertIs(type(value['flag']),bool)

    def test_duplicate_key_rejection_is_preserved(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            schema.decode(b'{"value":1.25,"value":2.5}')

    def test_size_limit_runs_before_number_parsing(self):
        with patch.object(schema.json,'loads') as loads:
            with self.assertRaisesRegex(ValueError, 'JSON exceeds byte limit'):
                schema.decode(b'1e9999',limit=5)
            loads.assert_not_called()

    def test_file_reader_uses_the_same_nonfinite_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'overflow.json'
            path.write_bytes(b'{"duration_seconds":1e9999}')
            with self.assertRaisesRegex(ValueError, 'Nonfinite JSON number'):
                schema.read_json(path)
            self.assertEqual(path.read_bytes(),b'{"duration_seconds":1e9999}')

    def test_finite_creative_intent_round_trip_preserves_its_digest(self):
        intent=schema.new_brief('A quiet observatory','video')
        intent['parameters']['duration_seconds']=1.25
        decoded=schema.decode(schema.canonical(intent))
        self.assertEqual(schema.validate(decoded),intent)
        self.assertEqual(schema.digest(decoded),schema.digest(intent))


if __name__=='__main__':unittest.main()
