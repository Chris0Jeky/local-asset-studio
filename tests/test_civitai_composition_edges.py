"""Additional source-scope and malformed-observation contracts."""
import copy
import unittest

from studio_workflow import civitai_composition as C


SHA = 'a' * 64
FILE_SHA = 'B' * 64


def receipt(host='civitai.com', route='/api/v1/model-versions/101', query=None,
            outcome='ok', response_sha256=SHA):
    return {'host': host, 'route': route, 'query': {} if query is None else query,
            'retrieved_at': '2026-09-21T00:00:00Z',
            'response_sha256': response_sha256, 'etag': None, 'last_modified': None,
            'outcome': outcome, 'auth_context': 'anonymous'}


def model(air='urn:air:sdxl:lora:civitai:10@101'):
    return {'id': 101, 'modelId': 10, 'air': air, 'baseModel': 'Illustrious',
            'baseModelType': 'Standard', 'trainedWords': [],
            'model': {'id': 10, 'name': 'Example', 'type': 'LORA'},
            'files': [{'id': 1001, 'name': 'example.safetensors', 'sizeKB': 1,
                       'hashes': {'SHA256': FILE_SHA}}]}


def image(image_id=1, post_id=11, meta=None, stats=None):
    if meta is None:
        meta = {'civitaiResources': [
            {'type': 'lora', 'modelVersionId': 101, 'weight': 0.8},
            {'type': 'checkpoint', 'modelVersionId': 202}], 'steps': 24}
    return {'id': image_id, 'postId': post_id, 'username': 'alice',
            'modelVersionIds': [101, 202], 'meta': meta,
            'width': 1024, 'height': 1024, 'stats': {} if stats is None else stats}


def page(items=None, *, host='civitai.com', query=None, outcome='ok', sha='c' * 64):
    if query is None:
        query = {'modelVersionId': '101', 'withMeta': 'true', 'browsingLevel': '31'}
    return {'receipt': receipt(host, '/api/v1/images', query, outcome, sha),
            'payload': {'items': [image()] if items is None else items,
                        'metadata': {'nextCursor': None}}}


def request(pages=None, payload=None, model_outcome='ok'):
    return {'format': C.INPUT_FORMAT,
            'model_version': {'receipt': receipt(outcome=model_outcome),
                              'payload': model() if payload is None else payload},
            'image_pages': [page()] if pages is None else pages}


class CivitaiCompositionEdgeTests(unittest.TestCase):
    def test_model_snapshot_must_be_successful(self):
        with self.assertRaisesRegex(ValueError, 'outcome ok'):
            C.normalize(request(model_outcome='filtered'))

    def test_image_query_must_target_exact_version_and_request_metadata(self):
        wrong = page(query={'modelVersionId': '999', 'withMeta': 'true'})
        with self.assertRaisesRegex(ValueError, 'target the normalized'):
            C.normalize(request([wrong]))
        missing = page(query={'modelVersionId': '101'})
        with self.assertRaisesRegex(ValueError, 'request metadata explicitly'):
            C.normalize(request([missing]))

    def test_boolean_with_meta_is_accepted_and_remains_in_scope(self):
        row = C.normalize(request([page(query={'modelVersionId': 101, 'withMeta': True})]))
        self.assertIs(row['combinations'][0]['source_scope']['query']['withMeta'], True)

    def test_invalid_stats_are_diagnostic_not_loss_of_composition_evidence(self):
        bad = image(stats={'likeCount': -1, 'commentCount': 'many'})
        result = C.normalize(request([page([bad])]))
        self.assertEqual(len(result['image_observations']), 1)
        self.assertEqual(result['image_observations'][0]['engagement'],
                         {'reaction_total': 0, 'comment_total': 0})
        self.assertEqual([item['code'] for item in result['diagnostics']],
                         ['invalid_image_stat', 'invalid_image_stat'])

    def test_gallery_resources_can_restore_ids_missing_from_top_level_metadata(self):
        value = image(); value['modelVersionIds'] = [101]
        result = C.normalize(request([page([value])]))
        self.assertEqual(result['image_observations'][0]['version_ids'], [101, 202])
        self.assertEqual(result['combinations'][0]['version_ids'], [101, 202])

    def test_invalid_or_mismatched_air_falls_back_to_exact_version_identity(self):
        for air in ('bad air value', 'urn:air:sdxl:lora:civitai:10@999',
                    'urn:air:sdxl:lora:civitai:99@101'):
            with self.subTest(air=air):
                result = C.normalize(request(payload=model(air)))
                self.assertEqual(result['resource']['identity'], 'civitai-version:101')
                self.assertIn('invalid_air', [item['code'] for item in result['diagnostics']])

    def test_sha256_is_normalized_and_becomes_file_identity(self):
        row = C.normalize(request())['resource']['files'][0]
        self.assertEqual(row['hashes']['sha256'], FILE_SHA.casefold())
        self.assertEqual(row['identity'], 'sha256:' + FILE_SHA.casefold())

    def test_sensitive_authorization_prefix_is_refused(self):
        value = page(query={'modelVersionId': '101', 'withMeta': 'true',
                            'AuthorizationBearer': 'secret'})
        with self.assertRaisesRegex(ValueError, 'sensitive query'):
            C.normalize(request([value]))

    def test_identical_duplicate_image_merges_receipts_with_one_observation(self):
        first = page([image()], sha='c' * 64)
        second = page([copy.deepcopy(image())], sha='d' * 64)
        result = C.normalize(request([first, second]))
        self.assertEqual(len(result['image_observations']), 1)
        self.assertEqual(result['image_observations'][0]['receipt_sha256s'],
                         ['c' * 64, 'd' * 64])
        self.assertEqual(result['combinations'][0]['receipt_sha256s'],
                         ['c' * 64, 'd' * 64])
        self.assertIn('duplicate_image', [item['code'] for item in result['diagnostics']])

    def test_same_image_id_on_distinct_hosts_is_not_a_conflict(self):
        result = C.normalize(request([
            page([image()], host='civitai.com', sha='c' * 64),
            page([image()], host='civitai.red', sha='d' * 64)]))
        self.assertEqual(len(result['image_observations']), 2)
        self.assertEqual(len(result['combinations']), 2)
        self.assertNotIn('conflicting_duplicate_image',
                         [item['code'] for item in result['diagnostics']])


if __name__ == '__main__': unittest.main()
