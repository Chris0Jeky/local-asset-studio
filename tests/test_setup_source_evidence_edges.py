"""Additional composition and provenance contracts for the setup source bridge."""
import copy
import unittest

from studio_workflow import source_compatibility as S


FILE_ID = 'sha256:' + 'a' * 64
CONTEXT = 'b' * 64
RECEIPT = 'c' * 64
REVIEW = 'sha256:' + 'd' * 64
RESOURCE_ID = 'urn:air:sdxl:lora:civitai:10@101'


def source_scope(host='civitai.com', scope_sha='e' * 64):
    return {'host': host, 'route': '/api/v1/images',
            'query': {'browsingLevel': '1', 'modelVersionId': '101', 'withMeta': 'true'},
            'auth_context': 'anonymous', 'scope_sha256': scope_sha}


def combination(version_ids, *, observations=4, uploaders=2, scope=None):
    return {
        'source_scope': source_scope() if scope is None else scope,
        'version_ids': version_ids,
        'distinct_observations': observations,
        'distinct_posts': observations,
        'distinct_uploaders': uploaders,
        'post_ids': list(range(1, observations + 1)),
        'uploaders': ['u' + str(index) for index in range(uploaders)],
        'receipt_sha256s': [RECEIPT],
        'resource_usages': [], 'settings': [],
        'engagement': {'reaction_total': 0, 'comment_total': 0},
        'reported_co_use': True, 'compatibility_proven': False,
        'quality_proven': False,
    }


def report(combinations=None, diagnostics=None):
    return {
        'format': 'studio.source-composition-evidence/v1',
        'provider': 'civitai', 'context_sha256': CONTEXT,
        'resource': {
            'source_host': 'civitai.com', 'model_id': 10, 'version_id': 101,
            'identity': RESOURCE_ID, 'model_name': 'Example', 'version_name': 'v1',
            'model_type': 'LORA', 'base_model': 'Illustrious',
            'base_model_type': 'Standard', 'trained_words': [],
            'created_at': None, 'updated_at': None, 'published_at': None,
            'status': 'Published', 'terms': {},
            'files': [{
                'provider_file_id': 1001, 'identity': FILE_ID,
                'name': 'example.safetensors', 'bytes': 1024,
                'file_type': 'Model', 'primary': True, 'format': 'SafeTensor',
                'precision': 'fp16', 'size_class': 'full',
                'hashes': {'sha256': 'a' * 64},
                'scan': {'pickle': 'Success', 'virus': 'Success', 'scanned_at': None},
            }],
            'receipt_sha256': RECEIPT,
        },
        'source_receipts': [{
            'host': 'civitai.com', 'route': '/api/v1/model-versions/101', 'query': {},
            'retrieved_at': '2026-09-21T00:00:00Z', 'response_sha256': RECEIPT,
            'etag': None, 'last_modified': None, 'outcome': 'ok',
            'auth_context': 'anonymous',
        }],
        'image_observations': [],
        'combinations': [combination([101, 202])] if combinations is None else combinations,
        'coverage_complete': True, 'diagnostics': [] if diagnostics is None else diagnostics,
        'network_performed': False, 'model_downloaded': False,
        'image_downloaded': False, 'installation_authorized': False,
        'generation_submitted': False, 'notice': 'retained evidence only',
    }


def mapping(candidate_id='example-style'):
    return {
        'candidate_id': candidate_id, 'name': candidate_id,
        'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
        'base_lineage': 'illustrious', 'loaders': ['LoraLoader.lora_name'],
        'format': 'safetensors', 'runtime': 'comfyui',
        'requires': ['node:LoraLoader'], 'resource_identity': RESOURCE_ID,
        'file_identity': FILE_ID, 'expected_source_context': CONTEXT,
        'review': {'revision': REVIEW, 'reviewed_at': '2026-09-21'},
    }


def request(source=None, reviewed=None):
    return {'format': 'studio.setup-source-adapter/v1',
            'report': report() if source is None else source,
            'mapping': mapping() if reviewed is None else reviewed}


class SourceCompatibilityBridgeEdgeTests(unittest.TestCase):
    def test_multiple_combinations_in_one_scope_get_distinct_evidence_ids(self):
        scope = source_scope()
        source = report([
            combination([101, 202], scope=copy.deepcopy(scope)),
            combination([101, 303], scope=copy.deepcopy(scope)),
        ])
        result = S.adapt(request(source=source))
        claims = [item for item in result['evidence'] if item['kind'] == 'gallery_co_use']
        self.assertEqual(len(claims), 2)
        self.assertEqual(len({item['id'] for item in claims}), 2)

    def test_provider_evidence_ids_are_candidate_scoped(self):
        left = S.adapt(request(reviewed=mapping('style-a')))
        right = S.adapt(request(reviewed=mapping('style-b')))
        self.assertNotEqual(left['evidence'][0]['id'], right['evidence'][0]['id'])

    def test_independent_uploader_breadth_cannot_exceed_observations(self):
        source = report([combination([101, 202], observations=1, uploaders=2)])
        with self.assertRaisesRegex(ValueError, 'uploader breadth'):
            S.adapt(request(source=source))

    def test_resource_receipt_identity_must_be_sha256(self):
        source = report(); source['resource']['receipt_sha256'] = 'not-a-sha'
        with self.assertRaisesRegex(ValueError, 'receipt'):
            S.adapt(request(source=source))

    def test_retained_source_diagnostics_remain_inspectable(self):
        diagnostics = [{'code': 'duplicate_image',
                        'message': 'Repeated source observation was deduplicated.'}]
        result = S.adapt(request(source=report(diagnostics=diagnostics)))
        self.assertEqual(result['source_diagnostics'], diagnostics)

    def test_incomplete_coverage_preserves_exact_mapping_and_positive_observations(self):
        source = report(diagnostics=[{
            'code': 'pagination_incomplete',
            'message': 'An advertised cursor was not retained.',
        }])
        source['coverage_complete'] = False
        result = S.adapt(request(source=source))
        self.assertEqual(result['candidate']['identity'], FILE_ID)
        self.assertFalse(result['source_coverage_complete'])
        self.assertEqual(len(result['source_observations']), 1)
        self.assertEqual(len([item for item in result['evidence']
                              if item['kind'] == 'gallery_co_use']), 1)
        self.assertIn('source_coverage_incomplete',
                      [item['code'] for item in result['diagnostics']])

    def test_coverage_complete_must_be_boolean(self):
        source = report(); source['coverage_complete'] = 'yes'
        with self.assertRaisesRegex(ValueError, 'coverage'):
            S.adapt(request(source=source))


if __name__ == '__main__': unittest.main()
