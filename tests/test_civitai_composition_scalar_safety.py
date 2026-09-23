"""Retained scalar validation is bounded, non-leaking and identity-stable."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio_workflow import civitai_composition as C
from test_civitai_composition import image, page, request


class CompositionScalarSafetyTests(unittest.TestCase):
    def assert_no_authority(self, result):
        for key in ('network_performed', 'model_downloaded', 'image_downloaded',
                    'installation_authorized', 'generation_submitted'):
            self.assertIs(result[key], False)

    def cli(self, value):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'snapshot.json'
            raw = json.dumps(value).encode('utf-8')
            source.write_bytes(raw)
            output = io.StringIO()
            with patch('sys.stdout', output), patch('socket.socket', side_effect=AssertionError('No network')):
                code = C.main([str(source)])
            self.assertEqual(source.read_bytes(), raw)
            return code, json.loads(output.getvalue())

    def test_huge_file_sizes_refuse_through_library_and_cli_without_overflow(self):
        for size in (10 ** 400, -(10 ** 400)):
            with self.subTest(negative=size < 0):
                value = request()
                value['model_version']['payload']['files'][0]['sizeKB'] = size
                original = copy.deepcopy(value)
                with self.assertRaisesRegex(ValueError, 'sizeKB'):
                    C.normalize(value)
                code, result = self.cli(value)
                self.assertEqual(code, 2)
                self.assertEqual(result['error']['code'], 'invalid_snapshot')
                self.assertEqual(value, original)

    def test_huge_gallery_numbers_keep_observation_and_field_diagnostics(self):
        cases = (('steps', 'steps'), ('clipSkip', 'clip_skip'), ('cfgScale', 'cfg'),
                 ('width', 'width'), ('height', 'height'), ('weight', None))
        for field, setting in cases:
            for huge in (10 ** 400, -(10 ** 400)):
                with self.subTest(field=field, negative=huge < 0):
                    row = image()
                    if field == 'weight': row['meta']['civitaiResources'][0]['weight'] = huge
                    elif field in ('width', 'height'): row[field] = huge
                    else: row['meta'][field] = huge
                    value = request([page([row])]); original = copy.deepcopy(value)
                    result = C.normalize(value)
                    self.assertEqual(value, original)
                    self.assertEqual(len(result['image_observations']), 1)
                    observation = result['image_observations'][0]
                    self.assertEqual(observation['version_ids'], [101, 202])
                    if field == 'weight':
                        self.assertEqual(observation['resources'], [{'version_id':202, 'type':'checkpoint', 'weight':None}])
                        self.assertIn('invalid_gallery_resource', [d['code'] for d in result['diagnostics']])
                    else:
                        self.assertTrue(any(d['code'] == 'invalid_gallery_setting' and d['setting'] == setting
                                            for d in result['diagnostics']))
                        self.assertNotIn('dimensions' if field in ('width', 'height') else setting, observation['settings'])
                    code, from_cli = self.cli(value)
                    self.assertEqual(code, 0)
                    self.assertEqual(from_cli, result)
                    self.assert_no_authority(result)

    def test_numeric_boundaries_remain_valid(self):
        row = image(width=65536, height=1)
        row['meta'].update(steps=10000, clipSkip=100, cfgScale=-1000)
        row['meta']['civitaiResources'][0]['weight'] = -100
        result = C.normalize(request([page([row])]))
        observation = result['image_observations'][0]
        self.assertEqual(observation['settings']['dimensions'], [65536, 1])
        self.assertEqual(observation['settings']['steps'], 10000)
        self.assertEqual(observation['settings']['clip_skip'], 100)
        self.assertEqual(observation['settings']['cfg'], -1000)
        self.assertEqual(observation['resources'][0]['weight'], -100.0)
        self.assertEqual(result['diagnostics'], [])
        self.assert_no_authority(result)

    def test_credential_query_variants_refuse_without_echoing_values(self):
        keys = ('x-api-key', 'civitai_api_key', 'providerApiKey', 'auth', 'bearer', 'jwt',
                'session', 'session_id', 'cookie', 'set-cookie', 'sig', 'signature',
                'credential', 'credentials', 'passwd', 'pwd', 'X-Amz-Credential', 'X-Amz-Signature',
                'secret_key', 'secretKey', 'SECRET_KEY', 'secretkey', 'client_secret_key',
                'civitaiSecretKey', 'aws_secret_access_key', 'token_value', 'session_cookie_value',
                'credential_value', 'AUTH_HEADER', 'APIKeyValue')
        for source in ('model', 'gallery'):
            for key in keys:
                with self.subTest(source=source, key=key):
                    value = request()
                    receipt = value['model_version']['receipt'] if source == 'model' else value['image_pages'][0]['receipt']
                    receipt['query'][key] = 'SYNTHETIC-SECRET-MARKER'
                    original = copy.deepcopy(value)
                    with self.assertRaisesRegex(ValueError, 'sensitive query') as error:
                        C.normalize(value)
                    self.assertNotIn('SYNTHETIC-SECRET-MARKER', str(error.exception))
                    code, result = self.cli(value)
                    self.assertEqual(code, 2)
                    self.assertNotIn('SYNTHETIC-SECRET-MARKER', json.dumps(result))
                    self.assertEqual(value, original)

    def test_benign_scope_parameters_survive_unchanged(self):
        value = request()
        query = value['image_pages'][0]['receipt']['query']
        query.update(period='Week', sort='Most Reactions', limit=100, customFilter=['a', 'b'],
                     author='example', monkeyCount=1, keyframe=2)
        result = C.normalize(value)
        self.assertEqual(result['source_receipts'][1]['query'], query)
        self.assert_no_authority(result)

    def test_air_case_does_not_change_resource_identity_or_input_provenance(self):
        first = request(); upper = copy.deepcopy(first)
        upper['model_version']['payload']['air'] = first['model_version']['payload']['air'].upper()
        original = copy.deepcopy(upper)
        lower_result, upper_result = C.normalize(first), C.normalize(upper)
        self.assertEqual(upper_result['resource'], lower_result['resource'])
        self.assertNotEqual(upper_result['context_sha256'], lower_result['context_sha256'])
        self.assertEqual(upper, original)
        self.assertEqual(upper_result['diagnostics'], [])
        self.assert_no_authority(upper_result)


if __name__ == '__main__': unittest.main()
