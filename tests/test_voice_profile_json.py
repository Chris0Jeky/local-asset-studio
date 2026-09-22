import json
from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

import voice_profile
import voice_profile_qualification as qualification


class VoiceProfileJsonBoundaryTests(unittest.TestCase):
    def write(self, root, name, text):
        path = Path(root) / name
        path.write_text(text, encoding='utf-8')
        return path

    def test_catalog_rejects_duplicate_nested_key_before_schema_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write(
                temporary,
                'catalog.json',
                '{"schema_version":1,"profiles":[{'
                '"id":"first-profile","id":"second-profile",'
                '"revision":1,"name":"Duplicate","status":"experimental",'
                '"identity":{},"producer":{},"deliveries":[],"lexicon":{},'
                '"mix":{},"acceptance":{}}]}',
            )
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, r'duplicate key.*id'):
                voice_profile.load_catalog(path)

    def test_local_registry_rejects_duplicate_top_level_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write(
                temporary,
                'registry.json',
                '{"schema_version":1,"schema_version":1,"profiles":[]}',
            )
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, r'duplicate key.*schema_version'):
                voice_profile.load_registry(path, voice_profile.load_catalog())

    def test_qualification_plan_reader_rejects_duplicate_nested_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write(
                temporary,
                'plan.json',
                '{"schema_version":1,"policy":{"id":"first","id":"second"}}',
            )
            with self.assertRaisesRegex(qualification.QualificationError, r'duplicate key.*id'):
                qualification._read_json(path, 'qualification plan')

    def test_qualification_report_reader_rejects_nonstandard_numeric_constants(self):
        for constant in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as temporary:
                path = self.write(
                    temporary,
                    'report.json',
                    '{"schema_version":1,"duration_seconds":' + constant + '}',
                )
                with self.assertRaisesRegex(
                    qualification.QualificationError,
                    r'non-standard numeric constant',
                ):
                    qualification._read_json(path, 'qualification report')

    def test_profile_catalog_rejects_nonstandard_numeric_constant_before_field_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write(
                temporary,
                'catalog.json',
                '{"schema_version":1,"profiles":[{'
                '"id":"profile","revision":NaN,"name":"Invalid",'
                '"status":"experimental","identity":{},"producer":{},'
                '"deliveries":[],"lexicon":{},"mix":{},"acceptance":{}}]}',
            )
            with self.assertRaisesRegex(
                voice_profile.VoiceProfileError,
                r'non-standard numeric constant',
            ):
                voice_profile.load_catalog(path)


if __name__ == '__main__':
    unittest.main()
