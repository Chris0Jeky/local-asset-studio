"""Additional composition and provenance contracts for the setup source bridge."""
import copy
import unittest

from studio_workflow import source_compatibility as S


FILE_ID = 'sha256:' + 'a' * 64
CONTEXT = 'b' * 64
RECEIPT = 'c' * 64
GALLERY_RECEIPT = 'f' * 64
REVIEW = 'sha256:' + 'd' * 64
RESOURCE_ID = 'urn:air:sdxl:lora:civitai:10@101'


def source_scope(host='civitai.com', scope_sha='e' * 64):
    return {'host': host, 'route': '/api/v1/images',
            'query': {'browsingLevel': '1', 'modelVersionId': '101', 'withMeta': 'true'},
            'auth_context': 'anonymous', 'scope_sha256': scope_sha}


def receipt(response_sha, route, *, host='civitai.com',
            retrieved_at='2026-09-21T00:00:00Z', outcome='ok'):
    return {
        'host': host, 'route': route, 'query': {},
        'retrieved_at': retrieved_at, 'response_sha256': response_sha,
        'etag': None, 'last_modified': None, 'outcome': outcome,
        'auth_context': 'anonymous',
    }


def combination(version_ids, *, observations=4, uploaders=2, scope=None):
    return {
        'source_scope': source_scope() if scope is None else scope,
        'version_ids': version_ids,
        'distinct_observations': observations,
        'distinct_posts': observations,
        'distinct_uploaders': uploaders,
        'post_ids': list(range(1, observations + 1)),
        'uploaders': ['u' + str(index) for index in range(uploaders)],
        'receipt_sha256s': [GALLERY_RECEIPT],
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
        'source_receipts': [
            receipt(RECEIPT, '/api/v1/model-versions/101'),
            receipt(GALLERY_RECEIPT, '/api/v1/images'),
        ],
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

    def test_provider_evidence_requires_one_exact_successful_model_version_receipt(self):
        for label, receipts in [
            ('missing', [receipt(GALLERY_RECEIPT, '/api/v1/images')]),
            ('wrong-route', [receipt(RECEIPT, '/api/v1/images'),
                             receipt(GALLERY_RECEIPT, '/api/v1/images')]),
            ('failed', [receipt(RECEIPT, '/api/v1/model-versions/101', outcome='error'),
                        receipt(GALLERY_RECEIPT, '/api/v1/images')]),
            ('ambiguous', [receipt(RECEIPT, '/api/v1/model-versions/101'),
                           receipt(RECEIPT, '/api/v1/model-versions/101'),
                           receipt(GALLERY_RECEIPT, '/api/v1/images')]),
        ]:
            with self.subTest(label=label):
                source = report(); source['source_receipts'] = receipts
                with self.assertRaisesRegex(ValueError, 'model-version receipt|resource receipt'):
                    S.adapt(request(source=source))

    def test_provider_evidence_date_comes_from_the_exact_resource_receipt(self):
        source = report()
        source['source_receipts'].insert(0, receipt(
            '1' * 64, '/api/v1/model-versions/999',
            retrieved_at='2020-01-01T00:00:00Z'))
        source['source_receipts'][1]['retrieved_at'] = '2026-09-20T10:30:00Z'
        result = S.adapt(request(source=source))
        self.assertEqual(result['evidence'][0]['source']['retrieved_at'], '2026-09-20')

    def test_resource_version_must_match_the_canonical_resource_identity(self):
        source = report(); source['resource']['version_id'] = 999
        with self.assertRaisesRegex(ValueError, 'version.*identity|identity.*version'):
            S.adapt(request(source=source))

    def test_duplicate_gallery_combination_key_is_refused_even_without_uploaders(self):
        left = combination([101, 202], uploaders=0)
        right = copy.deepcopy(left)
        right['engagement']['comment_total'] = 9
        source = report([left, right])
        with self.assertRaisesRegex(ValueError, 'Duplicate gallery.*combination'):
            S.adapt(request(source=source))

    def test_gallery_claim_requires_a_successful_retained_scope_receipt(self):
        for label, hashes, extra in [
            ('empty', [], []),
            ('unknown', ['2' * 64], []),
            ('wrong-route', ['2' * 64], [receipt('2' * 64, '/api/v1/model-versions/202')]),
            ('failed', ['2' * 64], [receipt('2' * 64, '/api/v1/images', outcome='error')]),
        ]:
            with self.subTest(label=label):
                item = combination([101, 202]); item['receipt_sha256s'] = hashes
                source = report([item]); source['source_receipts'].extend(extra)
                with self.assertRaisesRegex(ValueError, 'gallery receipt|retained receipt'):
                    S.adapt(request(source=source))

    def test_gallery_date_comes_from_the_matching_scope_receipt(self):
        source = report()
        source['source_receipts'].insert(0, receipt(
            '3' * 64, '/api/v1/images', retrieved_at='2020-01-01T00:00:00Z'))
        source['source_receipts'][-1]['retrieved_at'] = '2026-09-19T11:00:00Z'
        result = S.adapt(request(source=source))
        claim = next(item for item in result['evidence'] if item['kind'] == 'gallery_co_use')
        self.assertEqual(claim['source']['retrieved_at'], '2026-09-19')

    def test_uploader_breadth_matches_distinct_retained_uploader_identities(self):
        item = combination([101, 202], observations=4, uploaders=2)
        item['uploaders'] = ['same-uploader', 'same-uploader']
        source = report([item])
        with self.assertRaisesRegex(ValueError, 'uploader.*identit|distinct uploader'):
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
