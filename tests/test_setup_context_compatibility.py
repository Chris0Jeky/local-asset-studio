"""Live setup context must bind source candidates to exact local/runtime observations."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_workflow import setup_context_compatibility as L


FILE_HASH = 'a' * 64
FILE_ID = 'sha256:' + FILE_HASH
INVENTORY = 'b' * 64
SCHEMA = 'c' * 64
SOURCE_CONTEXT = 'd' * 64
REVIEW = 'sha256:' + 'e' * 64


def slot(**updates):
    value = {
        'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
        'base_lineage': 'illustrious', 'strict_lineage': True,
        'loader': 'LoraLoader.lora_name', 'runtime': 'comfyui',
        'formats': ['safetensors'], 'objective': 'quality',
        'capabilities': [], 'known_absent_capabilities': [],
    }
    value.update(updates)
    return value


def source_candidate(**candidate_updates):
    candidate = {
        'id': 'example-style', 'name': 'Example style',
        'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
        'base_lineage': 'illustrious', 'loaders': ['LoraLoader.lora_name'],
        'format': 'safetensors', 'runtime': 'comfyui',
        'requires': ['node:LoraLoader'], 'identity': FILE_ID,
    }
    candidate.update(candidate_updates)
    evidence = [{
        'id': 'provider-' + candidate['id'], 'candidate_id': candidate['id'],
        'resource_identity': candidate['identity'], 'kind': 'provider_metadata',
        'scope': 'exact_resource', 'direction': 'supports',
        'objective': 'compatibility', 'observations': 1,
        'independent_sources': 1,
        'source': {
            'locator': 'Retained Civitai model-version metadata',
            'revision': 'sha256:' + 'f' * 64,
            'retrieved_at': '2026-09-21',
        },
    }]
    return {
        'format': 'studio.setup-source-candidate/v1',
        'context_sha256': SOURCE_CONTEXT,
        'source_context_sha256': '1' * 64,
        'source_coverage_complete': True,
        'review_revision': REVIEW,
        'candidate': candidate,
        'evidence': evidence,
        'source_observations': [],
        'source_diagnostics': [],
        'diagnostics': [],
        'provider_claims': {},
        'provider_accessed': False,
        'file_hashed': False,
        'model_downloaded': False,
        'selection_changed': False,
        'installation_authorized': False,
        'generation_submitted': False,
        'notice': 'retained evidence only',
    }


def context(**updates):
    value = {
        'backend_id': 'primary', 'runtime': 'comfyui', 'switching': False,
        'inventory_revision': INVENTORY, 'schema_revision': SCHEMA,
        'schema_complete': True, 'node_classes': ['LoraLoader'],
        'assets': [{
            'asset_id': 'example-style',
            'file': 'loras/example.safetensors',
            'sha256': FILE_HASH,
            'present': True,
            'verified': True,
            'verification': 'stat-fresh-sha256-receipt',
        }],
    }
    value.update(updates)
    return value


def binding(**updates):
    value = {
        'candidate_id': 'example-style',
        'asset_id': 'example-style',
        'file': 'loras/example.safetensors',
        'backend_id': 'primary',
        'required_node_classes': ['LoraLoader'],
    }
    value.update(updates)
    return value


def controlled_run(candidate_id='example-style', identity=FILE_ID):
    return {
        'id': 'quality-run', 'candidate_id': candidate_id,
        'resource_identity': identity, 'kind': 'controlled_run',
        'scope': 'exact_resource', 'direction': 'supports',
        'objective': 'quality', 'observations': 3,
        'independent_sources': 1,
        'source': {
            'locator': 'Retained local quality comparison',
            'revision': 'sha256:' + '9' * 64,
            'retrieved_at': '2026-09-21',
        },
    }


def request(*, source=None, live=None, bind=None, evidence=None, target=None):
    return {
        'format': 'studio.setup-context-compatibility/v1',
        'slot': slot() if target is None else target,
        'source_candidates': [source_candidate() if source is None else source],
        'bindings': [binding() if bind is None else bind],
        'context': context() if live is None else live,
        'evidence': [controlled_run()] if evidence is None else evidence,
    }


def row(result):
    return result['compatibility']['candidates'][0]


class SetupContextCompatibilityTests(unittest.TestCase):
    def test_verified_exact_file_backend_and_schema_can_recommend(self):
        value = request()
        before = copy.deepcopy(value)
        result = L.evaluate(value)
        self.assertEqual(value, before)
        self.assertEqual(result['format'], 'studio.setup-context-compatibility-report/v1')
        self.assertEqual(row(result)['status'], 'recommended')
        self.assertTrue(row(result)['selectable'])
        self.assertEqual(row(result)['recommendation_rank'], 1)
        local = [item for item in result['compatibility_input']['evidence']
                 if item['kind'] == 'local_observation']
        self.assertEqual(len(local), 1)
        self.assertEqual(local[0]['resource_identity'], FILE_ID)
        self.assertEqual(result['precondition'], {
            'inventory_revision': INVENTORY,
            'schema_revision': SCHEMA,
            'backend_id': 'primary',
            'runtime': 'comfyui',
            'switching': False,
        })
        for key in ('provider_accessed', 'file_hashed', 'model_downloaded',
                    'installation_authorized', 'backend_switched',
                    'selection_changed', 'generation_submitted'):
            self.assertFalse(result[key], key)

    def test_present_but_unverified_file_needs_review(self):
        live = context()
        live['assets'][0]['verified'] = False
        live['assets'][0]['verification'] = 'explicit-reverification-required'
        result = L.evaluate(request(live=live))
        self.assertEqual(row(result)['status'], 'needs_review')
        self.assertTrue(row(result)['expert_override_required'])
        self.assertIn('required_capability_unknown',
                      [item['code'] for item in row(result)['unknowns']])
        self.assertIn('local_file_unverified',
                      [item['code'] for item in result['diagnostics']])
        self.assertFalse(any(item['kind'] == 'local_observation'
                             for item in result['compatibility_input']['evidence']))

    def test_missing_exact_file_is_incompatible(self):
        live = context()
        live['assets'][0].update(present=False, verified=False,
                                 verification='missing')
        result = L.evaluate(request(live=live))
        self.assertEqual(row(result)['status'], 'incompatible')
        self.assertFalse(row(result)['selectable'])
        conflicts = row(result)['hard_conflicts']
        self.assertIn('required_capability_absent',
                      [item['code'] for item in conflicts])
        self.assertTrue(any(item.get('capability', '').startswith('local-file:')
                            for item in conflicts))

    def test_stable_wrong_backend_is_incompatible_but_switching_is_unknown(self):
        wrong = context(backend_id='secondary')
        result = L.evaluate(request(live=wrong))
        self.assertEqual(row(result)['status'], 'incompatible')
        self.assertIn('backend_mismatch',
                      [item['code'] for item in result['diagnostics']])

        switching = context(backend_id='secondary', switching=True)
        result = L.evaluate(request(live=switching))
        self.assertEqual(row(result)['status'], 'needs_review')
        self.assertIn('backend_switching',
                      [item['code'] for item in result['diagnostics']])

    def test_complete_missing_node_is_incompatible_but_partial_schema_is_unknown(self):
        missing = context(node_classes=[])
        result = L.evaluate(request(live=missing))
        self.assertEqual(row(result)['status'], 'incompatible')
        self.assertIn('node_missing',
                      [item['code'] for item in result['diagnostics']])

        partial = context(node_classes=[], schema_complete=False,
                          schema_revision=None)
        result = L.evaluate(request(live=partial))
        self.assertEqual(row(result)['status'], 'needs_review')
        self.assertIn('node_unknown',
                      [item['code'] for item in result['diagnostics']])

    def test_hard_architecture_conflict_still_wins_over_local_and_quality_evidence(self):
        source = source_candidate(architecture='flux.1-dev',
                                  base_lineage='flux.1-dev')
        result = L.evaluate(request(
            source=source,
            target=slot(architecture='flux.2-klein',
                        base_lineage='flux.2-klein')))
        self.assertEqual(row(result)['status'], 'incompatible')
        self.assertIn('architecture_mismatch',
                      [item['code'] for item in row(result)['hard_conflicts']])
        self.assertEqual(row(result)['evidence_summary']['strong_support'], 1)

    def test_candidate_file_pin_must_match_exact_inventory_asset(self):
        live = context()
        live['assets'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'identity'):
            L.evaluate(request(live=live))

        with self.assertRaisesRegex(ValueError, 'file'):
            L.evaluate(request(bind=binding(file='loras/other.safetensors')))

    def test_binding_and_candidate_sets_must_match_exactly(self):
        extra = binding(candidate_id='other', asset_id='example-style')
        value = request()
        value['bindings'].append(extra)
        with self.assertRaisesRegex(ValueError, 'binding'):
            L.evaluate(value)

        value = request()
        value['bindings'] = []
        with self.assertRaisesRegex(ValueError, 'binding'):
            L.evaluate(value)

    def test_source_report_must_remain_zero_authority(self):
        source = source_candidate()
        source['provider_accessed'] = True
        with self.assertRaisesRegex(ValueError, 'zero authority'):
            L.evaluate(request(source=source))

    def test_live_context_cannot_contradict_declared_slot_runtime_or_capabilities(self):
        with self.assertRaisesRegex(ValueError, 'runtime'):
            L.evaluate(request(target=slot(runtime='other-runtime')))
        target = slot(known_absent_capabilities=['node:LoraLoader'])
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            L.evaluate(request(target=target))

    def test_context_identity_changes_when_live_revision_changes(self):
        first = L.evaluate(request())
        changed = context(inventory_revision='7' * 64)
        second = L.evaluate(request(live=changed))
        self.assertNotEqual(first['context_sha256'], second['context_sha256'])
        self.assertNotEqual(first['compatibility']['context_sha256'],
                            second['compatibility']['context_sha256'])

    def test_candidate_and_binding_order_do_not_change_result(self):
        second_source = source_candidate(
            id='second-style', name='Second style',
            identity='sha256:' + '2' * 64,
            requires=['node:LoraLoader'])
        second_source['context_sha256'] = '3' * 64
        live = context()
        live['assets'].append({
            'asset_id': 'second-style',
            'file': 'loras/second.safetensors',
            'sha256': '2' * 64,
            'present': True, 'verified': True,
            'verification': 'stat-fresh-sha256-receipt',
        })
        second_binding = binding(candidate_id='second-style',
                                 asset_id='second-style',
                                 file='loras/second.safetensors')
        evidence = [controlled_run(), controlled_run(
            candidate_id='second-style', identity='sha256:' + '2' * 64)]
        evidence[1]['id'] = 'quality-run-second'
        left = request(live=live, evidence=evidence)
        left['source_candidates'].append(second_source)
        left['bindings'].append(second_binding)
        right = copy.deepcopy(left)
        right['source_candidates'].reverse()
        right['bindings'].reverse()
        right['context']['assets'].reverse()
        right['context']['node_classes'].reverse()
        right['evidence'].reverse()
        self.assertEqual(L.evaluate(left), L.evaluate(right))


class SetupContextCompatibilityCLITests(unittest.TestCase):
    def test_cli_emits_same_bounded_zero_authority_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'context.json'
            path.write_text(json.dumps(request()), encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output):
                code = L.main([str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(row(result)['status'], 'recommended')
        self.assertFalse(result['generation_submitted'])

    def test_cli_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'context.json'
            path.write_text('{}', encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output):
                code = L.main([str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())['error']['code'],
                         'invalid_setup_context')


if __name__ == '__main__':
    unittest.main()
