"""The interpreter's integer parser limit must not escape the domain decoder."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import strict_json
import voice_profile


@unittest.skipUnless(hasattr(sys, 'set_int_max_str_digits'), 'bounded integer decoder unavailable')
class VoiceProfileIntegerJSON(unittest.TestCase):
    def setUp(self):
        previous = sys.get_int_max_str_digits()
        self.addCleanup(sys.set_int_max_str_digits, previous)
        self.limit = sys.int_info.str_digits_check_threshold
        sys.set_int_max_str_digits(self.limit)
        self.raw = b'{"schema_version":' + b'9' * (self.limit + 1) + b'}'

    def test_actual_integer_parser_refusal_has_strict_json_error_type(self):
        with self.assertRaises(ValueError): json.loads(self.raw)
        with self.assertRaisesRegex(strict_json.StrictJsonError, 'UTF-8 JSON'):
            strict_json.loads_strict(self.raw, label='profile evidence')

    def test_file_decoder_and_profile_loader_preserve_their_domain_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'profile.json'; path.write_bytes(self.raw)
            with self.subTest(api='strict file'):
                with self.assertRaises(strict_json.StrictJsonError):
                    strict_json.load_bounded_json(path, label='profile evidence', maximum_bytes=2048)
            with self.subTest(api='profile catalogue'):
                with self.assertRaises(voice_profile.VoiceProfileError): voice_profile.load_catalog(path)
            self.assertEqual(path.read_bytes(), self.raw)

    def test_valid_integer_boundary_and_existing_diagnostics_remain_unchanged(self):
        raw = b'{"n":' + b'7' * self.limit + b'}'
        self.assertEqual(strict_json.loads_strict(raw, label='valid'), json.loads(raw))
        for raw, diagnostic in ((b'{"x":1,"x":2}', 'duplicate key'),
                                (b'{"x":NaN}', 'non-standard numeric'),
                                (b'\xff', 'UTF-8 JSON')):
            with self.subTest(raw=raw), self.assertRaisesRegex(strict_json.StrictJsonError, diagnostic):
                strict_json.loads_strict(raw, label='invalid')


if __name__ == '__main__': unittest.main()
