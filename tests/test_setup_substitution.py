"""Atomic, evidence-bound setup substitution contracts for #144."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from studio_workflow import setup_compatibility as C
from studio_workflow import setup_substitution as S

IDENTITY = 'civitai-version:202'


def draft():
    return {
        'version': 1,
        'updatedAt': 0,
        'templateHash': '1' * 64,
        'pendingInputs': [],
        'recipe': {
            'preset': 'fixture',
            'controls': {
                'lora_name': 'old.safetensors',
                'lora': 0.8,
                'lora2_name': 'lora-y.safetensors',
                'lora2': 0.7,
                'steps': 30,
                'cfg': 5,
                'sampler': 'euler',
                'example_evidence': 'example-42',
            },
            'batch': 1,
            'references': [],
            'parent_assets': [],
            'parent_by_input': {},
        },
    }


def compatibility_request(*, architecture='sdxl', evidence=True):
    candidate = {
        'id': 'accelerator-x', 'name': 'Accelerator X', 'role': 'lora',
        'modality': 'image', 'architecture': architecture,
        'base_lineage': 'illustrious', 'loaders': ['LoraLoader.lora_name'],
        'format': 'safetensors', 'runtime': 'comfyui',
        'requires': ['node:LoraLoader'], 'identity': IDENTITY,
    }
    claims = []
    if evidence:
        claims.append({
            'id': 'accelerator-x-guide', 'candidate_id': 'accelerator-x',
            'resource_identity': IDENTITY, 'kind': 'creator_documentation',
            'scope': 'exact_resource', 'direction': 'supports',
            'objective': 'quality', 'observations': 1, 'independent_sources': 1,
            'source': {'locator': 'https://example.invalid/accelerator-x',
                       'revision': 'sha256:' + '2' * 64,
                       'retrieved_at': '2026-09-21'},
        })
    return {
        'format': C.INPUT_FORMAT,
        'slot': {
            'role': 'lora', 'modality': 'image', 'architecture': 'sdxl',
            'base_lineage': 'illustrious', 'strict_lineage': False,
            'loader': 'LoraLoader.lora_name', 'runtime': 'comfyui',
            'formats': ['safetensors'], 'objective': 'quality',
            'capabilities': ['node:LoraLoader'],
            'known_absent_capabilities': [],
        },
        'candidates': [candidate],
        'evidence': claims,
    }


def profile(*, source_status='current'):
    return {
        'format': S.PROFILE_FORMAT,
        'id': 'accelerator-x-atomic-v1',
        'review_revision': 'sha256:' + '3' * 64,
        'candidate_id': 'accelerator-x',
        'resource_identity': IDENTITY,
        'component_role': 'accelerator',
        'requested_changes': [{
            'control': 'lora_name', 'before': 'old.safetensors',
            'after': 'accelerator-x.safetensors',
            'reason': 'Replace the selected accelerator file.',
        }],
        'dependent_changes': [
            {'control': 'steps', 'before': 30, 'after': 8,
             'reason': 'Use the reviewed accelerated schedule.'},
            {'control': 'cfg', 'before': 5, 'after': 1,
             'reason': 'Use the reviewed ComfyUI guidance value.'},
            {'control': 'sampler', 'before': 'euler', 'after': 'dpmpp_2m',
             'reason': 'Use the reviewed sampler assumption.'},
        ],
        'incompatible_components': [{
            'id': 'appearance-y',
            'resource_identity': 'civitai-version:303',
            'reason': 'The reviewed accelerator profile conflicts with this adapter.',
            'controls': [
                {'control': 'lora2_name', 'before': 'lora-y.safetensors'},
                {'control': 'lora2', 'before': 0.7},
            ],
        }],
        'invalidations': [{
            'kind': 'example', 'id': 'example-42',
            'control': 'example_evidence', 'before': 'example-42',
            'reason': 'The retained example describes the previous model bundle.',
        }],
        'implications': {
            'download_status': 'required',
            'download_bytes': 123456,
            'memory_delta_bytes': -2048,
            'notes': ['Estimate only; preparation must recheck inventory and runtime.'],
        },
        'source_status': source_status,
        'source': {
            'locator': 'https://example.invalid/accelerator-x/profile',
            'revision': 'sha256:' + '4' * 64,
            'retrieved_at': '2026-09-21',
        },
    }


def substitution_request(*, current=None, compatibility=None, card=None):
    compatibility = copy.deepcopy(compatibility or compatibility_request())
    report = C.evaluate(copy.deepcopy(compatibility))
    return {
        'format': S.REQUEST_FORMAT,
        'draft': copy.deepcopy(current or draft()),
        'compatibility_request': compatibility,
        'compatibility_report': report,
        'candidate_id': 'accelerator-x',
        'profile': copy.deepcopy(card or profile()),
    }


class SetupSubstitutionPlanTests(unittest.TestCase):
    def test_complete_profile_yields_one_reviewable_dependency_diff(self):
        result = S.request(substitution_request())
        self.assertEqual(result['format'], S.REPORT_FORMAT)
        self.assertEqual(result['candidate']['status'], 'recommended')
        self.assertEqual(result['candidate']['identity'], IDENTITY)
        self.assertTrue(result['can_apply'])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['generation_submitted'])
        self.assertFalse(result['selection_changed'])
        self.assertEqual(result['blockers'], [])
        controls = result['after']['recipe']['controls']
        self.assertEqual(
            {key: controls[key] for key in ('lora_name', 'steps', 'cfg', 'sampler')},
            {'lora_name': 'accelerator-x.safetensors', 'steps': 8,
             'cfg': 1, 'sampler': 'dpmpp_2m'},
        )
        self.assertNotIn('lora2_name', controls)
        self.assertNotIn('lora2', controls)
        self.assertNotIn('example_evidence', controls)
        self.assertEqual(
            [(row['kind'], row['control']) for row in result['changes']],
            [('requested', 'lora_name'), ('required', 'steps'),
             ('required', 'cfg'), ('required', 'sampler'),
             ('remove_incompatible', 'lora2_name'),
             ('remove_incompatible', 'lora2'),
             ('invalidate_evidence', 'example_evidence')],
        )
        self.assertEqual(result['invalidations'][0]['id'], 'example-42')
        self.assertEqual(result['implications']['download_bytes'], 123456)
        exact = result['proposal_json']
        self.assertEqual(hashlib.sha256(exact.encode()).hexdigest(),
                         result['proposal_sha256'])
        self.assertEqual(json.loads(exact)['after'], result['after'])

    def test_plan_is_deterministic_and_does_not_mutate_inputs(self):
        value = substitution_request()
        before = copy.deepcopy(value)
        first = S.request(value)
        second = S.request(copy.deepcopy(value))
        self.assertEqual(value, before)
        self.assertEqual(first['proposal_json'], second['proposal_json'])
        self.assertEqual(first['proposal_sha256'], second['proposal_sha256'])
        self.assertRegex(first['precondition']['draft_sha256'], r'^[a-f0-9]{64}$')
        self.assertRegex(first['precondition']['profile_sha256'], r'^[a-f0-9]{64}$')

    def test_tampered_or_stale_compatibility_report_refuses(self):
        value = substitution_request()
        value['compatibility_report']['context_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'compatibility|Compatibility|stale'):
            S.request(value)
        value = substitution_request()
        value['compatibility_report']['candidates'][0]['status'] = 'possible'
        with self.assertRaisesRegex(ValueError, 'compatibility|Compatibility|stale'):
            S.request(value)

    def test_unknown_and_incompatible_candidates_remain_inspectable_not_applicable(self):
        unknown = S.request(substitution_request(
            compatibility=compatibility_request(architecture=None)))
        self.assertEqual(unknown['candidate']['status'], 'needs_review')
        self.assertFalse(unknown['can_apply'])
        self.assertIn('candidate_needs_review',
                      [row['code'] for row in unknown['blockers']])
        self.assertEqual(unknown['after']['recipe']['controls']['steps'], 8)

        incompatible = S.request(substitution_request(
            compatibility=compatibility_request(architecture='flux')))
        self.assertEqual(incompatible['candidate']['status'], 'incompatible')
        self.assertFalse(incompatible['can_apply'])
        self.assertIn('candidate_incompatible',
                      [row['code'] for row in incompatible['blockers']])
        self.assertIn('architecture_mismatch',
                      [row['code'] for row in incompatible['candidate']['hard_conflicts']])

    def test_stale_and_blocked_sources_are_disclosed_and_cannot_apply(self):
        for state, code in [('stale', 'source_stale'), ('blocked', 'source_blocked')]:
            with self.subTest(state=state):
                result = S.request(substitution_request(card=profile(source_status=state)))
                self.assertFalse(result['can_apply'])
                self.assertIn(code, [row['code'] for row in result['blockers']])
                self.assertEqual(result['source_status'], state)
                self.assertEqual(result['changes'][0]['control'], 'lora_name')

    def test_possible_candidate_can_apply_without_inventing_optimality(self):
        result = S.request(substitution_request(
            compatibility=compatibility_request(evidence=False)))
        self.assertEqual(result['candidate']['status'], 'possible')
        self.assertTrue(result['can_apply'])
        self.assertEqual(result['candidate']['recommendation_rank'], None)

    def test_conflicting_sources_are_preserved_not_averaged(self):
        compat = compatibility_request()
        negative = copy.deepcopy(compat['evidence'][0])
        negative.update(id='accelerator-x-negative', direction='contradicts')
        compat['evidence'].append(negative)
        result = S.request(substitution_request(compatibility=compat))
        self.assertEqual(result['candidate']['status'], 'possible')
        self.assertIn('strong_evidence_conflict',
                      [row['code'] for row in result['candidate']['limitations']])
        self.assertEqual(result['after']['recipe']['controls']['steps'], 8)
        self.assertEqual(result['after']['recipe']['controls']['cfg'], 1)

    def test_stale_before_duplicate_controls_and_invalid_values_refuse(self):
        stale = substitution_request()
        stale['draft']['recipe']['controls']['steps'] = 31
        with self.assertRaisesRegex(ValueError, 'steps|before|changed'):
            S.request(stale)

        duplicate = substitution_request()
        duplicate['profile']['dependent_changes'].append({
            'control': 'lora_name', 'before': 'old.safetensors',
            'after': 'other.safetensors', 'reason': 'duplicate fixture',
        })
        with self.assertRaisesRegex(ValueError, 'duplicate|Duplicate|control'):
            S.request(duplicate)

        invalid = substitution_request()
        invalid['profile']['dependent_changes'][0]['after'] = float('nan')
        with self.assertRaisesRegex((ValueError, TypeError), 'finite|JSON|value|number'):
            S.request(invalid)

    def test_profile_identity_must_match_the_exact_compatibility_candidate(self):
        value = substitution_request()
        value['profile']['resource_identity'] = 'civitai-version:999'
        with self.assertRaisesRegex(ValueError, 'identity|candidate'):
            S.request(value)
        value = substitution_request()
        value['profile']['candidate_id'] = 'another-candidate'
        with self.assertRaisesRegex(ValueError, 'candidate'):
            S.request(value)


if __name__ == '__main__':
    unittest.main()
