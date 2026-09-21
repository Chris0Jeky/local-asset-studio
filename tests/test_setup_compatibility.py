"""Provider-neutral setup compatibility and recommendation policy. Never contacts a provider."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_workflow import setup_compatibility as C


FORMAT = 'studio.setup-compatibility-input/v1'
IDENTITY = 'civitai-version:101'


def candidate(**updates):
    value = {
        'id': 'style-a', 'name': 'Style A', 'role': 'lora', 'modality': 'image',
        'architecture': 'sdxl', 'base_lineage': 'illustrious',
        'loaders': ['LoraLoader.lora_name'], 'format': 'safetensors',
        'runtime': 'comfyui', 'requires': ['node:LoraLoader'], 'identity': IDENTITY,
    }
    value.update(updates)
    return value


def claim(**updates):
    value = {
        'id': 'creator-quality', 'candidate_id': 'style-a',
        'resource_identity': IDENTITY, 'kind': 'creator_documentation',
        'scope': 'exact_resource', 'direction': 'supports', 'objective': 'quality',
        'observations': 1, 'independent_sources': 1,
        'source': {'locator': 'Synthetic reviewed card', 'revision': IDENTITY,
                   'retrieved_at': '2026-09-21'},
    }
    value.update(updates)
    return value


def request(candidates=None, evidence=None, **slot_updates):
    slot = {
        'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
        'base_lineage': 'illustrious', 'strict_lineage': False,
        'loader': 'LoraLoader.lora_name', 'runtime': 'comfyui',
        'formats': ['safetensors'], 'objective': 'quality',
        'capabilities': ['node:LoraLoader'], 'known_absent_capabilities': [],
    }
    slot.update(slot_updates)
    return {'format': FORMAT, 'slot': slot,
            'candidates': candidates if candidates is not None else [candidate()],
            'evidence': evidence if evidence is not None else []}


def row(value):
    return C.evaluate(value)['candidates'][0]


class SetupCompatibilityPolicyTests(unittest.TestCase):
    def test_hard_compatible_candidate_without_prescriptive_evidence_is_possible(self):
        result = C.evaluate(request())
        self.assertEqual(result['format'], 'studio.setup-compatibility-report/v1')
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertTrue(result['candidates'][0]['selectable'])
        self.assertFalse(result['provider_accessed'])
        self.assertFalse(result['generation_submitted'])
        self.assertFalse(result['selection_changed'])

    def test_exact_objective_creator_guidance_can_recommend(self):
        result = row(request(evidence=[claim()]))
        self.assertEqual(result['status'], 'recommended')
        self.assertEqual(result['recommendation_rank'], 1)
        self.assertEqual(result['evidence_summary']['strong_support'], 1)

    def test_compatibility_evidence_does_not_invent_quality_optimality(self):
        result = row(request(evidence=[claim(objective='compatibility')]))
        self.assertEqual(result['status'], 'possible')
        self.assertEqual(result['evidence_summary']['compatibility_support'], 1)

    def test_wrong_role_modality_architecture_loader_format_and_runtime_are_incompatible(self):
        cases = [
            (candidate(role='checkpoint'), 'role_mismatch'),
            (candidate(modality='video'), 'modality_mismatch'),
            (candidate(architecture='flux'), 'architecture_mismatch'),
            (candidate(loaders=['CustomLoader.patch']), 'loader_mismatch'),
            (candidate(format='gguf'), 'format_mismatch'),
            (candidate(runtime='diffusers'), 'runtime_mismatch'),
        ]
        for value, code in cases:
            with self.subTest(code=code):
                result = row(request(candidates=[value], evidence=[claim()]))
                self.assertEqual(result['status'], 'incompatible')
                self.assertFalse(result['selectable'])
                self.assertIn(code, [item['code'] for item in result['hard_conflicts']])

    def test_missing_required_fact_is_needs_review_not_possible(self):
        cases = [
            (candidate(architecture=None), 'architecture_unknown'),
            (candidate(loaders=[]), 'loader_unknown'),
            (candidate(format=None), 'format_unknown'),
            (candidate(runtime=None), 'runtime_unknown'),
            (candidate(identity=None), 'identity_unknown'),
            (candidate(base_lineage=None), 'base_lineage_unknown'),
        ]
        for value, code in cases:
            with self.subTest(code=code):
                result = row(request(candidates=[value]))
                self.assertEqual(result['status'], 'needs_review')
                self.assertFalse(result['selectable'])
                self.assertTrue(result['expert_override_required'])
                self.assertIn(code, [item['code'] for item in result['unknowns']])

    def test_explicitly_absent_requirement_is_incompatible_but_unobserved_is_unknown(self):
        value = candidate(requires=['node:LoraLoader', 'companion:clip-l'])
        absent = row(request(candidates=[value], known_absent_capabilities=['companion:clip-l']))
        self.assertEqual(absent['status'], 'incompatible')
        self.assertIn('required_capability_absent', [item['code'] for item in absent['hard_conflicts']])
        unknown = row(request(candidates=[value]))
        self.assertEqual(unknown['status'], 'needs_review')
        self.assertIn('required_capability_unknown', [item['code'] for item in unknown['unknowns']])

    def test_lineage_difference_is_possible_unless_slot_requires_exact_lineage(self):
        value = candidate(base_lineage='pony')
        loose = row(request(candidates=[value]))
        self.assertEqual(loose['status'], 'possible')
        self.assertIn('base_lineage_differs', [item['code'] for item in loose['limitations']])
        strict = row(request(candidates=[value], strict_lineage=True))
        self.assertEqual(strict['status'], 'incompatible')
        self.assertIn('base_lineage_mismatch', [item['code'] for item in strict['hard_conflicts']])

    def test_exact_positive_evidence_can_promote_a_soft_lineage_difference(self):
        result = row(request(candidates=[candidate(base_lineage='pony')], evidence=[claim()]))
        self.assertEqual(result['status'], 'recommended')
        self.assertIn('base_lineage_differs', [item['code'] for item in result['limitations']])

    def test_gallery_co_use_needs_breadth_and_never_overrides_a_hard_gate(self):
        broad = claim(id='gallery', kind='gallery_co_use', observations=4,
                      independent_sources=2, source={'locator': 'Retained gallery bundle',
                      'revision': 'sha256:' + 'a' * 64, 'retrieved_at': '2026-09-21'})
        self.assertEqual(row(request(evidence=[broad]))['status'], 'recommended')
        narrow = copy.deepcopy(broad); narrow.update(observations=20, independent_sources=1)
        self.assertEqual(row(request(evidence=[narrow]))['status'], 'possible')
        wrong = row(request(candidates=[candidate(architecture='flux')], evidence=[broad]))
        self.assertEqual(wrong['status'], 'incompatible')

    def test_family_scope_and_historical_observation_cannot_promote(self):
        family = claim(scope='family', resource_identity=None)
        historical = claim(id='history', kind='local_observation')
        result = row(request(evidence=[family, historical]))
        self.assertEqual(result['status'], 'possible')
        self.assertEqual(result['evidence_summary']['weak_support'], 2)

    def test_exact_claim_for_another_version_is_ignored_with_diagnostic(self):
        result = C.evaluate(request(evidence=[claim(resource_identity='civitai-version:999')]))
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertEqual(result['candidates'][0]['evidence_summary']['strong_support'], 0)
        self.assertIn('evidence_identity_mismatch', [item['code'] for item in result['diagnostics']])

    def test_strong_support_and_contradiction_remain_possible_with_conflict(self):
        negative = claim(id='negative', direction='contradicts')
        result = row(request(evidence=[claim(), negative]))
        self.assertEqual(result['status'], 'possible')
        self.assertEqual(result['evidence_summary']['strong_support'], 1)
        self.assertEqual(result['evidence_summary']['strong_contradiction'], 1)
        self.assertIn('strong_evidence_conflict', [item['code'] for item in result['limitations']])

    def test_deterministic_ranking_uses_evidence_then_name_and_id(self):
        values = [candidate(id='z', name='Zulu', identity='civitai-version:3'),
                  candidate(id='b', name='Beta', identity='civitai-version:2'),
                  candidate(id='a', name='Alpha', identity='civitai-version:1')]
        evidence = [claim(id='z-e', candidate_id='z', resource_identity='civitai-version:3'),
                    claim(id='b-e', candidate_id='b', resource_identity='civitai-version:2'),
                    claim(id='a-e', candidate_id='a', resource_identity='civitai-version:1')]
        result = C.evaluate(request(candidates=list(reversed(values)), evidence=list(reversed(evidence))))
        self.assertEqual([item['id'] for item in result['candidates']], ['a', 'b', 'z'])
        self.assertEqual([item['recommendation_rank'] for item in result['candidates']], [1, 2, 3])

    def test_state_order_is_recommended_possible_review_then_incompatible(self):
        values = [candidate(id='bad', name='Bad', architecture='flux', identity='civitai-version:4'),
                  candidate(id='unknown', name='Unknown', identity=None),
                  candidate(id='possible', name='Possible', identity='civitai-version:2'),
                  candidate(id='best', name='Best', identity='civitai-version:1')]
        evidence = [claim(candidate_id='best', resource_identity='civitai-version:1')]
        result = C.evaluate(request(candidates=values, evidence=evidence))
        self.assertEqual([(item['id'], item['status']) for item in result['candidates']],
                         [('best', 'recommended'), ('possible', 'possible'),
                          ('unknown', 'needs_review'), ('bad', 'incompatible')])

    def test_input_is_not_mutated_and_context_identity_is_stable(self):
        value = request(evidence=[claim()]); before = copy.deepcopy(value)
        first = C.evaluate(value); second = C.evaluate(copy.deepcopy(value))
        self.assertEqual(value, before)
        self.assertEqual(first['context_sha256'], second['context_sha256'])
        self.assertRegex(first['context_sha256'], r'^[a-f0-9]{64}$')

    def test_invalid_candidates_refuse_and_invalid_evidence_is_visible(self):
        for values in [[], [candidate(), candidate()], [candidate(id='Bad Space')]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                C.evaluate(request(candidates=values))
        malformed = claim(observations=-1)
        result = C.evaluate(request(evidence=[malformed]))
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertIn('invalid_evidence', [item['code'] for item in result['diagnostics']])

    def test_bounds_and_credential_like_source_values_refuse_evidence(self):
        too_many = [candidate(id='c' + str(i), identity='civitai-version:' + str(i + 1)) for i in range(257)]
        with self.assertRaises(ValueError): C.evaluate(request(candidates=too_many))
        secret = claim(source={'locator': 'https://user:secret@example.org',
                               'revision': IDENTITY, 'retrieved_at': '2026-09-21'})
        result = C.evaluate(request(evidence=[secret]))
        self.assertIn('invalid_evidence', [item['code'] for item in result['diagnostics']])


class SetupCompatibilityCLITests(unittest.TestCase):
    def test_cli_emits_the_same_zero_authority_report(self):
        value = request(evidence=[claim()])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'request.json'; path.write_text(json.dumps(value), encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output): code = C.main([str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['candidates'][0]['status'], 'recommended')
        self.assertFalse(result['provider_accessed'])

    def test_cli_reports_invalid_input_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'request.json'; path.write_text('{}', encoding='utf-8')
            output = io.StringIO()
            with mock.patch('sys.stdout', output): code = C.main([str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())['error']['code'], 'invalid_request')


if __name__ == '__main__': unittest.main()
