"""Offline Civitai/Civitai.red version and gallery evidence normalization."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_workflow import civitai_composition as C


SHA = 'a' * 64
FILE_SHA = 'b' * 64


def receipt(host='civitai.com', route='/api/v1/model-versions/101', query=None,
            response_sha256=SHA, outcome='ok'):
    return {'host': host, 'route': route, 'query': {} if query is None else query,
            'retrieved_at': '2026-09-21T00:00:00Z',
            'response_sha256': response_sha256, 'etag': None, 'last_modified': None,
            'outcome': outcome, 'auth_context': 'anonymous'}


def version_payload(**updates):
    value = {
        'id': 101, 'modelId': 10, 'name': 'Example v1', 'baseModel': 'Illustrious',
        'baseModelType': 'Standard', 'air': 'urn:air:sdxl:lora:civitai:10@101',
        'trainedWords': ['example-trigger'], 'createdAt': '2026-09-01T00:00:00Z',
        'updatedAt': '2026-09-10T00:00:00Z', 'publishedAt': '2026-09-11T00:00:00Z',
        'description': '<script>provider text is not executable</script>',
        'model': {'id': 10, 'name': 'Example model', 'type': 'LORA',
                  'allowNoCredit': False, 'allowCommercialUse': 'Image',
                  'allowDerivatives': True, 'allowDifferentLicense': False},
        'files': [{'id': 1001, 'name': 'example.safetensors', 'sizeKB': 1024.5,
                   'type': 'Model', 'primary': True,
                   'metadata': {'format': 'SafeTensor', 'fp': 'fp16', 'size': 'full'},
                   'hashes': {'SHA256': FILE_SHA, 'AutoV2': 'ABC123'},
                   'pickleScanResult': 'Success', 'virusScanResult': 'Success',
                   'scannedAt': '2026-09-11T00:00:00Z'}],
    }
    value.update(updates); return value


def image(image_id=1, post_id=11, username='alice', version_ids=None, meta=None, **updates):
    if version_ids is None: version_ids = [101, 202]
    if meta is None:
        meta = {'civitaiResources': [
                    {'type': 'lora', 'modelVersionId': 101, 'weight': 0.8},
                    {'type': 'checkpoint', 'modelVersionId': 202}],
                'steps': 28, 'sampler': 'Euler', 'scheduler': 'normal',
                'cfgScale': 5.0, 'clipSkip': 2,
                'prompt': 'private prompt must not enter evidence'}
    value = {'id': image_id, 'postId': post_id, 'username': username,
             'createdAt': '2026-09-20T00:00:00Z', 'width': 1024, 'height': 768,
             'modelVersionIds': version_ids, 'meta': meta,
             'stats': {'likeCount': 5, 'heartCount': 2, 'commentCount': 1}}
    value.update(updates); return value


def page(items=None, host='civitai.com', query=None, outcome='ok', sha='c' * 64,
         metadata=None):
    if query is None: query = {'modelVersionId': '101', 'withMeta': 'true', 'browsingLevel': '31'}
    if metadata is None: metadata = {'nextCursor': None}
    return {'receipt': receipt(host, '/api/v1/images', query, sha, outcome),
            'payload': {'items': [image()] if items is None else items, 'metadata': metadata}}


def request(image_pages=None, payload=None):
    return {'format': 'studio.civitai-composition-input/v1',
            'model_version': {'receipt': receipt(),
                              'payload': version_payload() if payload is None else payload},
            'image_pages': [page()] if image_pages is None else image_pages}


class CivitaiCompositionTests(unittest.TestCase):
    def test_exact_version_and_file_facts_are_normalized_without_authority(self):
        result = C.normalize(request())
        self.assertEqual(result['format'], 'studio.source-composition-evidence/v1')
        resource = result['resource']
        self.assertEqual(resource['model_id'], 10); self.assertEqual(resource['version_id'], 101)
        self.assertEqual(resource['identity'], 'urn:air:sdxl:lora:civitai:10@101')
        self.assertEqual(resource['base_model'], 'Illustrious')
        self.assertEqual(resource['trained_words'], ['example-trigger'])
        file = resource['files'][0]
        self.assertEqual(file['identity'], 'sha256:' + FILE_SHA)
        self.assertEqual(file['bytes'], round(1024.5 * 1024))
        self.assertEqual(file['hashes']['sha256'], FILE_SHA)
        self.assertTrue(file['primary'])
        for field in ('network_performed', 'model_downloaded', 'image_downloaded',
                      'installation_authorized', 'generation_submitted'):
            self.assertFalse(result[field])

    def test_gallery_resources_weights_settings_and_engagement_are_retained_as_observations(self):
        result = C.normalize(request())
        observation = result['image_observations'][0]
        self.assertEqual(observation['version_ids'], [101, 202])
        self.assertEqual(observation['resources'][0],
                         {'version_id': 101, 'type': 'lora', 'weight': 0.8})
        self.assertEqual(observation['settings']['steps'], 28)
        self.assertEqual(observation['settings']['dimensions'], [1024, 768])
        self.assertEqual(observation['engagement'], {'reaction_total': 7, 'comment_total': 1})
        combination = result['combinations'][0]
        self.assertEqual(combination['distinct_observations'], 1)
        self.assertEqual(combination['distinct_uploaders'], 1)
        self.assertFalse(combination['compatibility_proven'])
        self.assertFalse(combination['quality_proven'])

    def test_multiple_images_from_one_post_do_not_inflate_combination_breadth(self):
        first = image(1, 11); second = image(2, 11)
        result = C.normalize(request([page([first, second])]))
        self.assertEqual(len(result['image_observations']), 2)
        combination = result['combinations'][0]
        self.assertEqual(combination['distinct_observations'], 1)
        self.assertEqual(combination['distinct_posts'], 1)
        self.assertEqual(combination['distinct_uploaders'], 1)
        self.assertEqual(combination['engagement']['reaction_total'], 7)

    def test_repeated_uploader_is_exposed_not_counted_as_independent_people(self):
        items = [image(i, 10 + i, 'alice') for i in range(1, 5)]
        combination = C.normalize(request([page(items)]))['combinations'][0]
        self.assertEqual(combination['distinct_observations'], 4)
        self.assertEqual(combination['distinct_uploaders'], 1)
        self.assertEqual(combination['uploaders'], ['alice'])

    def test_com_and_red_scopes_are_never_silently_merged(self):
        pages = [page([image()], 'civitai.com', sha='c' * 64),
                 page([image()], 'civitai.red', sha='d' * 64)]
        result = C.normalize(request(pages))
        self.assertEqual(len(result['combinations']), 2)
        self.assertEqual([row['source_scope']['host'] for row in result['combinations']],
                         ['civitai.com', 'civitai.red'])
        self.assertNotEqual(result['combinations'][0]['source_scope']['scope_sha256'],
                            result['combinations'][1]['source_scope']['scope_sha256'])

    def test_browsing_filter_is_part_of_source_scope(self):
        safe = page([image(1)], query={'modelVersionId': '101', 'withMeta': 'true',
                                      'browsingLevel': '1'}, sha='c' * 64)
        broad = page([image(2)], query={'modelVersionId': '101', 'withMeta': 'true',
                                       'browsingLevel': '31'}, sha='d' * 64)
        rows = C.normalize(request([safe, broad]))['combinations']
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['source_scope']['query']['browsingLevel'] for row in rows],
                         ['1', '31'])

    def test_filtered_or_blocked_page_is_unknown_not_an_empty_authoritative_result(self):
        filtered = page([], 'civitai.red', outcome='filtered', sha='d' * 64)
        result = C.normalize(request([filtered]))
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['combinations'], [])
        self.assertIn('source_filtered', [item['code'] for item in result['diagnostics']])
        self.assertEqual(result['source_receipts'][1]['outcome'], 'filtered')

    def test_unfetched_next_cursor_is_explicitly_incomplete(self):
        result = C.normalize(request([page(metadata={'nextCursor': 'next-page'})]))
        self.assertFalse(result['coverage_complete'])
        self.assertIn('pagination_incomplete', [item['code'] for item in result['diagnostics']])

    def test_absent_or_malformed_meta_keeps_top_level_ids_without_inventing_weights(self):
        absent = image(1, meta=None); absent['meta'] = None
        malformed = image(2); malformed['meta'] = 'not-an-object'
        result = C.normalize(request([page([absent, malformed])]))
        self.assertEqual([row['metadata_state'] for row in result['image_observations']],
                         ['absent', 'malformed'])
        self.assertEqual([row['version_ids'] for row in result['image_observations']],
                         [[101, 202], [101, 202]])
        self.assertTrue(all(row['resources'] == [] for row in result['image_observations']))
        self.assertIn('malformed_image_metadata', [item['code'] for item in result['diagnostics']])

    def test_invalid_resource_weight_is_skipped_and_visible(self):
        bad = image(); bad['meta']['civitaiResources'][0]['weight'] = 101
        result = C.normalize(request([page([bad])]))
        self.assertEqual(result['image_observations'][0]['version_ids'], [101, 202])
        self.assertEqual(result['image_observations'][0]['resources'],
                         [{'version_id': 202, 'type': 'checkpoint', 'weight': None}])
        self.assertIn('invalid_gallery_resource', [item['code'] for item in result['diagnostics']])

    def test_same_filename_with_distinct_provider_file_ids_is_retained(self):
        files = copy.deepcopy(version_payload()['files'])
        other = copy.deepcopy(files[0]); other['id'] = 1002; other['hashes'] = {}; other['primary'] = False
        value = version_payload(files=[files[0], other])
        rows = C.normalize(request(payload=value))['resource']['files']
        self.assertEqual([row['provider_file_id'] for row in rows], [1001, 1002])
        self.assertEqual([row['name'] for row in rows], ['example.safetensors', 'example.safetensors'])
        self.assertEqual(rows[1]['identity'], 'civitai-file:101/1002')

    def test_duplicate_file_id_and_version_route_mismatch_refuse(self):
        files = copy.deepcopy(version_payload()['files']); files.append(copy.deepcopy(files[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate file ID'):
            C.normalize(request(payload=version_payload(files=files)))
        bad = request(); bad['model_version']['receipt']['route'] = '/api/v1/model-versions/999'
        with self.assertRaisesRegex(ValueError, 'version identity'):
            C.normalize(bad)

    def test_credentials_in_query_and_unknown_hosts_refuse(self):
        bad = request([page(query={'apiKey': 'secret'})])
        with self.assertRaisesRegex(ValueError, 'sensitive query'):
            C.normalize(bad)
        bad = request([page(host='www.civitai.com')])
        with self.assertRaisesRegex(ValueError, 'source host'):
            C.normalize(bad)

    def test_conflicting_duplicate_image_is_excluded_not_first_wins(self):
        first = image(); changed = image(); changed['modelVersionIds'] = [101, 303]
        result = C.normalize(request([page([first, changed])]))
        self.assertEqual(result['image_observations'], [])
        self.assertEqual(result['combinations'], [])
        self.assertIn('conflicting_duplicate_image',
                      [item['code'] for item in result['diagnostics']])

    def test_input_is_immutable_and_output_omits_prompt_description_and_media_urls(self):
        value = request(); value['model_version']['payload']['downloadUrl'] = 'https://example.invalid/model'
        value['image_pages'][0]['payload']['items'][0]['url'] = 'https://example.invalid/image'
        before = copy.deepcopy(value); first = C.normalize(value); second = C.normalize(copy.deepcopy(value))
        self.assertEqual(value, before); self.assertEqual(first['context_sha256'], second['context_sha256'])
        encoded = json.dumps(first)
        self.assertNotIn('provider text is not executable', encoded)
        self.assertNotIn('private prompt must not enter evidence', encoded)
        self.assertNotIn('example.invalid', encoded)

    def test_bounds_refuse_before_processing(self):
        with self.assertRaises(ValueError): C.normalize(request([page([])] * 33))
        too_many = [image(i + 1, i + 1) for i in range(1001)]
        with self.assertRaises(ValueError): C.normalize(request([page(too_many)]))


class CivitaiCompositionCLITests(unittest.TestCase):
    def test_cli_normalizes_a_retained_file_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'snapshot.json'; path.write_text(json.dumps(request()), encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output): code = C.main([str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['resource']['version_id'], 101)
        self.assertFalse(result['network_performed'])

    def test_cli_reports_invalid_input_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'snapshot.json'; path.write_text('{}', encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output): code = C.main([str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())['error']['code'], 'invalid_snapshot')


if __name__ == '__main__': unittest.main()
