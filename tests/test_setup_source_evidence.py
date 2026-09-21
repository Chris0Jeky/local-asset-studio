"""Retained source evidence must enter setup compatibility through reviewed exact mappings."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_workflow import setup_compatibility as C
from studio_workflow import source_compatibility as S


FILE_ID = 'sha256:' + 'a' * 64
CONTEXT = 'b' * 64
RECEIPT = 'c' * 64
REVIEW = 'sha256:' + 'd' * 64


def source_scope(host='civitai.com', browsing='1'):
    return {'host': host, 'route': '/api/v1/images',
            'query': {'browsingLevel': browsing, 'modelVersionId': '101', 'withMeta': 'true'},
            'auth_context': 'anonymous', 'scope_sha256': ('e' if host == 'civitai.com' else 'f') * 64}


def report(*, resource_identity='urn:air:sdxl:lora:civitai:10@101',
           base_model='Illustrious', model_type='LORA', combinations=None,
           file_identity=FILE_ID, file_format='SafeTensor'):
    if combinations is None:
        combinations = [{
            'source_scope': source_scope(), 'version_ids': [101, 202],
            'distinct_observations': 4, 'distinct_posts': 4, 'distinct_uploaders': 2,
            'post_ids': [11, 12, 13, 14], 'uploaders': ['alice', 'bob'],
            'receipt_sha256s': [RECEIPT], 'resource_usages': [
                {'version_id': 101, 'types': ['lora'], 'weights': [0.8]},
                {'version_id': 202, 'types': ['checkpoint'], 'weights': []}],
            'settings': [{'steps': 24, 'cfg': 5, 'count': 4}],
            'engagement': {'reaction_total': 999999, 'comment_total': 5000},
            'reported_co_use': True, 'compatibility_proven': False, 'quality_proven': False,
        }]
    return {
        'format': 'studio.source-composition-evidence/v1', 'provider': 'civitai',
        'context_sha256': CONTEXT,
        'resource': {
            'source_host': 'civitai.com', 'model_id': 10, 'version_id': 101,
            'identity': resource_identity, 'model_name': 'Example', 'version_name': 'v1',
            'model_type': model_type, 'base_model': base_model,
            'base_model_type': 'Standard', 'trained_words': ['example'],
            'created_at': '2026-09-01T00:00:00Z', 'updated_at': None,
            'published_at': '2026-09-02T00:00:00Z', 'status': 'Published',
            'terms': {}, 'files': [{
                'provider_file_id': 1001, 'identity': file_identity,
                'name': 'example.safetensors', 'bytes': 1024,
                'file_type': 'Model', 'primary': True, 'format': file_format,
                'precision': 'fp16', 'size_class': 'full',
                'hashes': {'sha256': 'a' * 64},
                'scan': {'pickle': 'Success', 'virus': 'Success', 'scanned_at': '2026-09-02'},
            }], 'receipt_sha256': RECEIPT,
        },
        'source_receipts': [{
            'host': 'civitai.com', 'route': '/api/v1/model-versions/101', 'query': {},
            'retrieved_at': '2026-09-21T00:00:00Z', 'response_sha256': RECEIPT,
            'etag': None, 'last_modified': None, 'outcome': 'ok', 'auth_context': 'anonymous',
        }],
        'image_observations': [], 'combinations': combinations,
        'coverage_complete': True, 'diagnostics': [],
        'network_performed': False, 'model_downloaded': False, 'image_downloaded': False,
        'installation_authorized': False, 'generation_submitted': False,
        'notice': 'retained evidence only',
    }


def mapping(**updates):
    value = {
        'candidate_id': 'example-style', 'name': 'Example style',
        'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
        'base_lineage': 'illustrious', 'loaders': ['LoraLoader.lora_name'],
        'format': 'safetensors', 'runtime': 'comfyui',
        'requires': ['node:LoraLoader'],
        'resource_identity': 'urn:air:sdxl:lora:civitai:10@101',
        'file_identity': FILE_ID, 'expected_source_context': CONTEXT,
        'review': {'revision': REVIEW, 'reviewed_at': '2026-09-21'},
    }
    value.update(updates)
    return value


def request(*, source=None, reviewed=None):
    return {'format': 'studio.setup-source-adapter/v1',
            'report': report() if source is None else source,
            'mapping': mapping() if reviewed is None else reviewed}


def slot(**updates):
    value = {
        'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
        'base_lineage': 'illustrious', 'strict_lineage': True,
        'loader': 'LoraLoader.lora_name', 'runtime': 'comfyui',
        'formats': ['safetensors'], 'objective': 'quality',
        'capabilities': ['node:LoraLoader'], 'known_absent_capabilities': [],
    }
    value.update(updates)
    return value


def evaluate(adapted, **slot_updates):
    value = {'format': C.INPUT_FORMAT, 'slot': slot(**slot_updates),
             'candidates': [adapted['candidate']], 'evidence': adapted['evidence']}
    return C.evaluate(value)['candidates'][0]


class SourceCompatibilityBridgeTests(unittest.TestCase):
    def test_reviewed_exact_file_builds_candidate_and_non_authoritative_evidence(self):
        value = request(); before = copy.deepcopy(value)
        result = S.adapt(value)
        self.assertEqual(value, before)
        self.assertEqual(result['format'], 'studio.setup-source-candidate/v1')
        self.assertEqual(result['candidate'], {
            'id': 'example-style', 'name': 'Example style', 'role': 'lora',
            'modality': 'image', 'architecture': 'sdxl', 'base_lineage': 'illustrious',
            'loaders': ['LoraLoader.lora_name'], 'format': 'safetensors',
            'runtime': 'comfyui', 'requires': ['node:LoraLoader'], 'identity': FILE_ID,
        })
        provider = result['evidence'][0]
        self.assertEqual((provider['kind'], provider['scope'], provider['objective']),
                         ('provider_metadata', 'exact_resource', 'compatibility'))
        self.assertEqual(provider['resource_identity'], FILE_ID)
        self.assertFalse(result['provider_accessed'])
        self.assertFalse(result['selection_changed'])
        self.assertFalse(result['installation_authorized'])
        self.assertFalse(result['generation_submitted'])

    def test_provider_labels_never_replace_reviewed_architecture_or_lineage(self):
        source = report(base_model='Qwen Image 2.1', model_type='Checkpoint')
        reviewed = mapping(architecture='qwen-image-edit-2511',
                           base_lineage='qwen-image-edit-2511')
        result = S.adapt(request(source=source, reviewed=reviewed))
        self.assertEqual(result['candidate']['architecture'], 'qwen-image-edit-2511')
        self.assertEqual(result['candidate']['base_lineage'], 'qwen-image-edit-2511')
        self.assertIn('provider_claim_differs', [item['code'] for item in result['diagnostics']])

    def test_qwen_edit_2511_mapping_is_incompatible_with_qwen_image_21_slot(self):
        adapted = S.adapt(request(reviewed=mapping(
            architecture='qwen-image-edit-2511', base_lineage='qwen-image-edit-2511')))
        result = evaluate(adapted, architecture='qwen-image-2.1', base_lineage='qwen-image-2.1')
        self.assertEqual(result['status'], 'incompatible')
        self.assertIn('architecture_mismatch', [item['code'] for item in result['hard_conflicts']])

    def test_flux1_gallery_popularity_cannot_override_flux2_klein_mismatch(self):
        source = report(resource_identity='civitai-version:2165902', base_model='Flux.1 D')
        reviewed = mapping(resource_identity='civitai-version:2165902',
                           architecture='flux.1-dev', base_lineage='flux.1-dev')
        adapted = S.adapt(request(source=source, reviewed=reviewed))
        result = evaluate(adapted, architecture='flux.2-klein', base_lineage='flux.2-klein')
        self.assertEqual(result['status'], 'incompatible')
        self.assertGreater(adapted['source_observations'][0]['engagement']['reaction_total'], 0)
        self.assertIn('architecture_mismatch', [item['code'] for item in result['hard_conflicts']])

    def test_gallery_co_use_is_family_scoped_compatibility_evidence_not_quality_advice(self):
        result = S.adapt(request())
        gallery = [item for item in result['evidence'] if item['kind'] == 'gallery_co_use']
        self.assertEqual(len(gallery), 1)
        self.assertEqual(gallery[0]['scope'], 'family')
        self.assertIsNone(gallery[0]['resource_identity'])
        self.assertEqual(gallery[0]['objective'], 'compatibility')
        self.assertEqual(gallery[0]['observations'], 4)
        self.assertEqual(gallery[0]['independent_sources'], 2)
        self.assertEqual(evaluate(result)['status'], 'possible')

    def test_engagement_does_not_change_evidence_counts_or_ranking(self):
        low = report(); low['combinations'][0]['engagement'] = {'reaction_total': 0, 'comment_total': 0}
        high = report(); high['combinations'][0]['engagement'] = {
            'reaction_total': 1_000_000_000, 'comment_total': 1_000_000_000}
        left = S.adapt(request(source=low)); right = S.adapt(request(source=high))
        left_claim = [x for x in left['evidence'] if x['kind'] == 'gallery_co_use'][0]
        right_claim = [x for x in right['evidence'] if x['kind'] == 'gallery_co_use'][0]
        self.assertEqual(left_claim, right_claim)

    def test_com_and_red_scopes_remain_separate_claims(self):
        first = report()['combinations'][0]
        second = copy.deepcopy(first); second['source_scope'] = source_scope('civitai.red', '31')
        second['receipt_sha256s'] = ['f' * 64]
        result = S.adapt(request(source=report(combinations=[first, second])))
        gallery = [item for item in result['evidence'] if item['kind'] == 'gallery_co_use']
        self.assertEqual(len(gallery), 2)
        self.assertNotEqual(gallery[0]['id'], gallery[1]['id'])
        self.assertEqual({x['source']['locator'] for x in gallery},
                         {'Retained civitai.com gallery composition',
                          'Retained civitai.red gallery composition'})

    def test_zero_uploader_breadth_stays_observable_but_not_evidence(self):
        combination = report()['combinations'][0]
        combination['distinct_uploaders'] = 0; combination['uploaders'] = []
        result = S.adapt(request(source=report(combinations=[combination])))
        self.assertEqual([x for x in result['evidence'] if x['kind'] == 'gallery_co_use'], [])
        self.assertEqual(len(result['source_observations']), 1)
        self.assertIn('gallery_independence_unknown', [x['code'] for x in result['diagnostics']])

    def test_stale_context_wrong_resource_or_missing_file_refuses(self):
        cases = [
            mapping(expected_source_context='0' * 64),
            mapping(resource_identity='civitai-version:999'),
            mapping(file_identity='sha256:' + '9' * 64),
        ]
        for reviewed in cases:
            with self.subTest(reviewed=reviewed), self.assertRaises(ValueError):
                S.adapt(request(reviewed=reviewed))

    def test_known_provider_format_contradiction_refuses_but_unknown_is_diagnostic(self):
        with self.assertRaisesRegex(ValueError, 'format'):
            S.adapt(request(reviewed=mapping(format='gguf')))
        source = report(file_format=None)
        result = S.adapt(request(source=source))
        self.assertIn('provider_format_unknown', [item['code'] for item in result['diagnostics']])

    def test_source_authority_or_malformed_review_pin_refuses(self):
        source = report(); source['network_performed'] = True
        with self.assertRaisesRegex(ValueError, 'zero authority'):
            S.adapt(request(source=source))
        with self.assertRaisesRegex(ValueError, 'review revision'):
            S.adapt(request(reviewed=mapping(review={'revision': 'latest',
                                                     'reviewed_at': '2026-09-21'})))

    def test_output_is_deterministic_under_combination_reordering(self):
        first = report()['combinations'][0]
        second = copy.deepcopy(first); second['source_scope'] = source_scope('civitai.red', '31')
        second['receipt_sha256s'] = ['f' * 64]
        left = S.adapt(request(source=report(combinations=[first, second])))
        right = S.adapt(request(source=report(combinations=[second, first])))
        self.assertEqual(left, right)
        self.assertRegex(left['context_sha256'], r'^[a-f0-9]{64}$')


class SourceCompatibilityCLITests(unittest.TestCase):
    def test_cli_emits_same_zero_authority_bridge(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.json'; path.write_text(json.dumps(request()), encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output): code = S.main([str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['candidate']['identity'], FILE_ID)
        self.assertFalse(result['provider_accessed'])

    def test_cli_returns_bounded_structured_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.json'; path.write_text('{}', encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output): code = S.main([str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())['error']['code'], 'invalid_source_mapping')


if __name__ == '__main__': unittest.main()
