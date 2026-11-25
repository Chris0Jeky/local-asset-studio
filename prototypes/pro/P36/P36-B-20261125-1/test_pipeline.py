"""Behavioral gates: a receipt is not permission to pass identity drift downstream."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


class BootstrapTests(unittest.TestCase):
    def test_pipeline_entrypoint_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('pipeline'),
                             'The offline character receipt implementation is required')


class FamilyTests(unittest.TestCase):
    def setUp(self):
        import pipeline as p
        self.p = p
        self.policy = {
            'version': 1,
            'features': {
                'hair': {'kind': 'rgb', 'tolerance': 0.08},
                'eyes': {'kind': 'rgb', 'tolerance': 0.08},
                'eye_spacing': {'kind': 'ratio', 'tolerance': 0.04},
                'braid_side': {'kind': 'trait'},
            },
            'required': {s: {'front': ['hair', 'eyes', 'eye_spacing', 'braid_side']}
                         for s in p.STAGES},
            'quality_required': {'rig': ['weights', 'deformation']},
        }
        self.family = p.create_family('sable-p36', '1' * 32, 'sable', self.policy,
                                      mode='synthetic')

    def receipt(self, stage, *, family=None, accepted=True, drift=False):
        p = self.p; family = family or self.family
        sha = p.digest({'stage': stage})
        features = {
            name: {'value': value, 'provenance': 'fixture_truth', 'media_sha256': sha}
            for name, value in {'hair': [80, 20, 90], 'eyes': [120, 70, 150],
                                'eye_spacing': 0.42, 'braid_side': 'anatomical-left'}.items()
        }
        if drift: features['eyes']['value'] = [20, 180, 20]
        identity = {'sheet': {'views': [{'id': 'front', 'media_sha256': sha,
                                        'features': features}]}}
        if stage == 'concept': identity['anchor_features'] = copy.deepcopy(features)
        artifact = {'key': stage + '-front', 'asset_id': 'asset-' + stage,
                    'path': stage + '/front.png', 'sha256': sha, 'bytes': 256,
                    'media_type': 'image/png', 'role': 'identity-view',
                    'dimensions': [32, 32], 'colour_space': 'srgb', 'alpha': 'opaque',
                    'licence': {'name': 'Synthetic fixture; no character asset',
                                'source': 'fixture:P36', 'commercial': 'unknown'}}
        quality = [{'name': name, 'outcome': 'pass', 'evidence_ref': 'fixture:' + name}
                   for name in self.policy['quality_required'].get(stage, [])]
        receipt = p.prepare_receipt(family, stage, artifacts=[artifact],
                                    recipe={'route_id': 'synthetic-no-generation',
                                            'controls': {'seed': '18446744073709551615'}},
                                    references=[], identity=identity, quality=quality)
        receipt = p.attest(receipt, 'generation', 'completed', 'fixture', 'fixture:bytes')
        if accepted:
            receipt = p.attest(receipt, 'inspection', 'inspected', 'fixture', 'fixture:inspection')
            receipt = p.attest(receipt, 'acceptance', 'accepted', 'owner', 'fixture:acceptance')
        return receipt

    def add(self, stage, **kwargs):
        r = self.receipt(stage, **kwargs)
        self.family = self.p.record_receipt(self.family, r)
        return r

    def through(self, stage):
        for s in self.p.STAGES:
            self.add(s)
            if s == stage: break

    def codes(self, gate):
        return [b['code'] for b in gate['blockers']]

    def test_generation_does_not_accept_or_clear(self):
        r = self.add('concept', accepted=False)
        gate = self.p.assess(self.family, 'concept')
        self.assertFalse(gate['passed'])
        self.assertIn('acceptance_required', self.codes(gate))
        self.assertEqual(r['licence']['state'], 'unknown')
        self.assertEqual(r['inspection']['state'], 'unreviewed')

    def test_cannot_start_turnaround_without_accepted_concept(self):
        self.add('concept', accepted=False)
        with self.assertRaisesRegex(self.p.PipelineError, 'blocked'):
            self.receipt('turnaround')

    def test_identity_drift_blocks_all_downstream_actions(self):
        self.add('concept'); self.add('turnaround', drift=True)
        self.assertFalse(self.p.assess(self.family, 'turnaround')['passed'])
        for stage in self.p.STAGES[2:]:
            with self.subTest(stage=stage):
                self.assertFalse(self.p.next_gate(self.family, stage)['passed'])

    def test_failed_identity_is_not_repaired_by_owner_acceptance(self):
        self.add('concept'); self.add('turnaround', drift=True)
        self.assertIn('identity_drift', self.codes(self.p.assess(self.family, 'turnaround')))

    def test_selected_concept_replacement_invalidates_every_descendant(self):
        self.through('unreal')
        old = copy.deepcopy(self.family)
        r = self.receipt('concept')
        r['payload']['recipe']['controls']['seed'] = '24'
        r = self.p.seal(r)
        for dim, state, actor in [('generation', 'completed', 'fixture'),
                                  ('inspection', 'inspected', 'fixture'),
                                  ('acceptance', 'accepted', 'owner')]:
            r = self.p.attest(r, dim, state, actor, 'fixture:replacement')
        self.family = self.p.record_receipt(self.family, r)
        for stage in self.p.STAGES[1:]:
            with self.subTest(stage=stage):
                self.assertFalse(self.p.assess(self.family, stage)['passed'])
        self.assertTrue(set(old['receipts']).issubset(self.family['receipts']))

    def test_replacement_of_selected_turnaround_invalidates_existing_mesh(self):
        self.through('mesh')
        r = self.receipt('turnaround')
        r['payload']['recipe']['controls']['seed'] = '8'
        r = self.p.seal(r)
        for dim, state, actor in [('generation', 'completed', 'fixture'),
                                  ('inspection', 'inspected', 'fixture'),
                                  ('acceptance', 'accepted', 'owner')]:
            r = self.p.attest(r, dim, state, actor, 'fixture:replacement')
        self.family = self.p.record_receipt(self.family, r)
        self.assertFalse(self.p.assess(self.family, 'mesh')['passed'])

    def test_uncertain_submission_retains_prompt_id_and_blocks(self):
        r = self.receipt('concept')
        r = self.p.attest(r, 'generation', 'uncertain', 'fixture', 'prompt:known-123')
        self.family = self.p.record_receipt(self.family, r)
        self.assertIn('uncertain_submission', self.codes(self.p.assess(self.family, 'concept')))
        self.assertEqual(self.family['receipts'][r['id']]['generation']['evidence_ref'],
                         'prompt:known-123')
        self.assertFalse(self.p.next_gate(self.family, 'turnaround')['passed'])

    def test_no_cross_family_or_workspace_receipt(self):
        r = self.receipt('concept')
        for field, value in [('workspace_id', '2' * 32), ('family_id', 'different')]:
            other = copy.deepcopy(r); other['payload'][field] = value
            other = self.p.seal(other)
            with self.subTest(field=field), self.assertRaises(self.p.PipelineError):
                self.p.record_receipt(self.family, other)

    def test_tampering_receipt_is_rejected(self):
        r = self.receipt('concept'); r['payload']['recipe']['route_id'] = 'substituted'
        with self.assertRaisesRegex(self.p.PipelineError, 'digest'):
            self.p.record_receipt(self.family, r)

    def test_rehashed_content_does_not_reuse_old_acceptance(self):
        self.add('concept')
        r = self.receipt('turnaround')
        r['payload']['recipe']['route_id'] = 'changed'
        r = self.p.seal(r)
        self.family = self.p.record_receipt(self.family, r)
        self.assertIn('stale_attestation', self.codes(self.p.assess(self.family, 'turnaround')))

    def test_mutated_policy_cannot_retroactively_relax_gates(self):
        self.through('turnaround')
        self.family['policy']['features']['eyes']['tolerance'] = 10
        with self.assertRaises(self.p.PipelineError):
            self.p.assess(self.family, 'turnaround')

    def test_unknown_licence_is_preserved_separately_from_art_pass(self):
        self.through('unreal')
        self.assertTrue(self.p.assess(self.family, 'unreal')['passed'])
        release = self.p.assess(self.family, 'unreal', require_licence=True,
                                intended_use='commercial-game')
        self.assertFalse(release['passed'])
        self.assertIn('licence_clearance_required', self.codes(release))

    def test_licence_decision_is_intended_use_bound(self):
        r = self.receipt('concept')
        r = self.p.attest(r, 'licence', 'cleared', 'owner', 'fixture:terms',
                          intended_use='private-study')
        self.family = self.p.record_receipt(self.family, r)
        self.assertTrue(self.p.assess(self.family, 'concept', require_licence=True,
                                      intended_use='private-study')['passed'])
        self.assertFalse(self.p.assess(self.family, 'concept', require_licence=True,
                                       intended_use='commercial-game')['passed'])

    def test_agent_cannot_be_recorded_as_owner_acceptance(self):
        r = self.receipt('concept', accepted=False)
        with self.assertRaises(self.p.PipelineError):
            self.p.attest(r, 'acceptance', 'accepted', 'agent', 'agent:looks-good')

    def test_parent_laundering_is_rejected(self):
        self.through('turnaround')
        r = self.receipt('expressions'); r['payload']['parents'] = {}
        with self.assertRaises(self.p.PipelineError):
            self.p.record_receipt(self.family, self.p.seal(r))

    def test_sheet_observations_must_reference_receipt_media(self):
        self.add('concept')
        r = self.receipt('turnaround')
        r['payload']['identity']['sheet']['views'][0]['media_sha256'] = 'f' * 64
        r = self.p.seal(r)
        self.family = self.p.record_receipt(self.family, r)
        self.assertIn('unbound_identity_media', self.codes(self.p.assess(self.family, 'turnaround')))

    def test_required_native_quality_failure_blocks_next_stage(self):
        self.through('mesh')
        r = self.receipt('rig'); r['payload']['quality'][1]['outcome'] = 'fail'
        r = self.p.seal(r)
        self.family = self.p.record_receipt(self.family, r)
        self.assertIn('quality_gate_failed', self.codes(self.p.assess(self.family, 'rig')))
        self.assertFalse(self.p.next_gate(self.family, 'toon')['passed'])

    def test_recording_is_idempotent_and_input_is_not_mutated(self):
        r = self.receipt('concept'); before = copy.deepcopy(self.family)
        first = self.p.record_receipt(self.family, r)
        second = self.p.record_receipt(first, r)
        self.assertEqual(self.family, before)
        self.assertEqual(first, second)

    def test_invalid_json_numbers_and_duplicate_keys_refuse(self):
        for raw in ['{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.subTest(raw=raw), self.assertRaises(self.p.PipelineError):
                self.p.decode_json(raw)

    def test_uncertain_stage_cannot_be_replaced_by_fresh_submission(self):
        self.add('concept')
        receipt = self.receipt('turnaround')
        receipt = self.p.attest(receipt, 'generation', 'uncertain', 'fixture', 'prompt:retained')
        self.family = self.p.record_receipt(self.family, receipt)
        with self.assertRaisesRegex(self.p.PipelineError, 'uncertain|blocked'):
            self.receipt('turnaround')

    def test_uncertainty_can_only_resolve_same_payload_and_prompt(self):
        self.add('concept')
        receipt = self.receipt('turnaround')
        receipt = self.p.attest(receipt, 'generation', 'uncertain', 'fixture', 'prompt:retained')
        self.family = self.p.record_receipt(self.family, receipt)
        with self.assertRaises(self.p.PipelineError):
            self.p.resolve_uncertain(self.family, 'turnaround', 'completed', 'prompt:other',
                                     'fixture:history-confirmation')
        resolved = self.p.resolve_uncertain(self.family, 'turnaround', 'completed', 'prompt:retained',
                                            'fixture:history-confirmation')
        active = resolved['receipts'][resolved['heads']['turnaround']]
        self.assertEqual(active['payload'], receipt['payload'])
        self.assertEqual(active['generation']['evidence_ref'], 'prompt:retained')
        self.assertEqual(active['generation']['observation_ref'], 'fixture:history-confirmation')
        self.assertTrue(self.p.assess(resolved, 'turnaround')['passed'])

    def test_unreferenced_history_tampering_is_detected(self):
        old = self.add('concept')
        r = self.receipt('concept'); r['payload']['recipe']['controls']['seed'] = '4'
        r = self.p.seal(r)
        self.family = self.p.record_receipt(self.family, r)
        self.family['receipts'][old['id']]['payload']['recipe']['controls']['seed'] = 'tampered'
        with self.assertRaises(self.p.PipelineError):
            self.p.assess(self.family, 'concept')

    def test_native_quality_reference_requires_nonempty_text(self):
        self.through('mesh')
        for value in (1, {'not': 'a reference'}, '', None):
            r = self.receipt('rig'); r['payload']['quality'][0]['evidence_ref'] = value
            with self.subTest(value=value), self.assertRaises(self.p.PipelineError):
                self.p.record_receipt(self.family, self.p.seal(r))


if __name__ == '__main__': unittest.main()
