"""Additional refusal and conflict contracts for setup compatibility advice."""
import copy
import unittest

from studio_workflow import setup_compatibility as C


IDENTITY = 'civitai-version:101'


def candidate(**updates):
    value = {
        'id': 'style-a', 'name': 'Style A', 'role': 'lora', 'modality': 'image',
        'architecture': 'sdxl', 'base_lineage': 'illustrious',
        'loaders': ['LoraLoader.lora_name'], 'format': 'safetensors',
        'runtime': 'comfyui', 'requires': ['node:LoraLoader'], 'identity': IDENTITY,
    }
    value.update(updates); return value


def claim(**updates):
    value = {
        'id': 'claim-a', 'candidate_id': 'style-a', 'resource_identity': IDENTITY,
        'kind': 'creator_documentation', 'scope': 'exact_resource',
        'direction': 'supports', 'objective': 'quality', 'observations': 1,
        'independent_sources': 1,
        'source': {'locator': 'Reviewed synthetic source', 'revision': IDENTITY,
                   'retrieved_at': '2026-09-21'},
    }
    value.update(updates); return value


def request(evidence=None, candidates=None, **slot_updates):
    slot = {
        'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
        'base_lineage': 'illustrious', 'strict_lineage': False,
        'loader': 'LoraLoader.lora_name', 'runtime': 'comfyui',
        'formats': ['safetensors'], 'objective': 'quality',
        'capabilities': ['node:LoraLoader'], 'known_absent_capabilities': [],
    }
    slot.update(slot_updates)
    return {'format': C.INPUT_FORMAT, 'slot': slot,
            'candidates': [candidate()] if candidates is None else candidates,
            'evidence': [] if evidence is None else evidence}


class SetupCompatibilityEdgeTests(unittest.TestCase):
    def test_exact_compatibility_contradiction_suppresses_gallery_recommendation(self):
        gallery = claim(id='gallery', kind='gallery_co_use', observations=8,
                        independent_sources=4,
                        source={'locator': 'Reviewed retained gallery bundle',
                                'revision': 'sha256:' + 'a' * 64,
                                'retrieved_at': '2026-09-21'})
        contradiction = claim(id='compat-negative', objective='compatibility',
                              direction='contradicts')
        row = C.evaluate(request([gallery, contradiction]))['candidates'][0]
        self.assertEqual(row['status'], 'possible')
        self.assertEqual(row['evidence_summary']['qualified_gallery_claims'], 1)
        self.assertEqual(row['evidence_summary']['compatibility_contradiction'], 1)
        self.assertIn('compatibility_evidence_contradiction',
                      [item['code'] for item in row['limitations']])

    def test_exact_evidence_without_retained_revision_is_diagnostic_only(self):
        value = claim(); value['source']['revision'] = None
        result = C.evaluate(request([value]))
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertIn('invalid_evidence', [item['code'] for item in result['diagnostics']])

    def test_duplicate_evidence_ids_are_all_excluded(self):
        result = C.evaluate(request([claim(), copy.deepcopy(claim())]))
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertEqual(result['candidates'][0]['evidence_summary']['applied_claims'], [])
        self.assertEqual([item['code'] for item in result['diagnostics']],
                         ['invalid_evidence', 'invalid_evidence'])

    def test_evidence_for_unlisted_candidate_is_visible_and_not_applied(self):
        value = claim(candidate_id='not-in-request')
        result = C.evaluate(request([value]))
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertIn('unknown_evidence_candidate',
                      [item['code'] for item in result['diagnostics']])

    def test_present_and_absent_capability_overlap_refuses_request(self):
        with self.assertRaisesRegex(ValueError, 'both present and absent'):
            C.evaluate(request(known_absent_capabilities=['node:LoraLoader']))

    def test_strict_lineage_requires_an_explicit_target_lineage(self):
        with self.assertRaisesRegex(ValueError, 'strict lineage'):
            C.evaluate(request(base_lineage=None, strict_lineage=True))

    def test_slot_objective_uses_evidence_identifier_grammar(self):
        for invalid in ('Quality', 'image quality'):
            with self.subTest(objective=invalid):
                with self.assertRaisesRegex(ValueError, 'identifier'):
                    C.evaluate(request(objective=invalid))

    def test_controlled_run_needs_at_least_one_observation(self):
        empty = claim(kind='controlled_run', observations=0, independent_sources=0)
        result = C.evaluate(request([empty]))
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertEqual(result['candidates'][0]['evidence_summary']['strong_support'], 0)
        self.assertIn('invalid_evidence', [item['code'] for item in result['diagnostics']])

    def test_gallery_source_breadth_cannot_exceed_observations(self):
        inflated = claim(
            kind='gallery_co_use', observations=3, independent_sources=4,
            source={'locator': 'Reviewed retained gallery bundle',
                    'revision': 'sha256:' + 'b' * 64,
                    'retrieved_at': '2026-09-21'},
        )
        with self.assertRaisesRegex(ValueError, 'independent|observations'):
            C.validate_evidence(inflated)
        result = C.evaluate(request([inflated]))
        self.assertEqual(result['candidates'][0]['status'], 'possible')
        self.assertEqual(
            result['candidates'][0]['evidence_summary']['qualified_gallery_claims'], 0)
        self.assertIn('invalid_evidence',
                      [item['code'] for item in result['diagnostics']])

    def test_duplicate_non_null_resource_identity_refuses_alias_candidates(self):
        duplicate = candidate(id='style-b', name='Style B')
        with self.assertRaisesRegex(ValueError, 'Duplicate candidate resource identity'):
            C.evaluate(request(candidates=[candidate(), duplicate]))
        unknowns = [candidate(id='unknown-a', name='Unknown A', identity=None),
                    candidate(id='unknown-b', name='Unknown B', identity=None)]
        result = C.evaluate(request(candidates=unknowns))
        self.assertEqual(result['counts']['needs_review'], 2)

    def test_canonical_air_can_identify_an_exact_resource(self):
        air = 'urn:air:sdxl:lora:civitai:12345@67890'
        value = candidate(identity=air)
        evidence = claim(resource_identity=air,
                         source={'locator': 'Retained AIR-scoped source',
                                 'revision': air, 'retrieved_at': '2026-09-21'})
        row = C.evaluate(request([evidence], [value]))['candidates'][0]
        self.assertEqual(row['status'], 'recommended')
        self.assertEqual(row['identity'], air)

    def test_source_revision_cannot_be_a_credential_bearing_url(self):
        value = claim(source={'locator': 'Reviewed source',
                              'revision': 'https://user:secret@example.org/revision',
                              'retrieved_at': '2026-09-21'})
        result = C.evaluate(request([value]))
        self.assertIn('invalid_evidence', [item['code'] for item in result['diagnostics']])

    def test_unrelated_objective_is_not_used_for_ranking(self):
        speed = claim(objective='speed')
        row = C.evaluate(request([speed]))['candidates'][0]
        self.assertEqual(row['status'], 'possible')
        self.assertEqual(row['evidence_summary']['applied_claims'], [])


if __name__ == '__main__': unittest.main()
