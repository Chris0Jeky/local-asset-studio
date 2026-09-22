import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import voice_profile
import voice_profile_qualification as qualification


HEX_A = 'a' * 64
HEX_B = 'b' * 64
HEX_C = 'c' * 64
REV_A = '1' * 40
REV_B = '2' * 40
REV_C = '3' * 40


def candidate_policy(plan, candidate_id):
    return next(item for item in plan['candidates'] if item['id'] == candidate_id)


def producer_for(policy):
    model_ids = {
        'qwen3-voice-design-v1': 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
        'qwen3-reusable-reference-v1': 'Qwen/Qwen3-TTS-12Hz-1.7B-Base',
        'indextts-2-5-expressive-v1': 'index-tts/IndexTTS-2.5',
        'kokoro-af-heart-control-v1': 'hexgrad/Kokoro-82M',
    }
    revisions = {
        'qwen3-voice-design-v1': REV_A,
        'qwen3-reusable-reference-v1': REV_A,
        'indextts-2-5-expressive-v1': REV_B,
        'kokoro-af-heart-control-v1': REV_C,
    }
    return {
        'family': policy['producer_family'],
        'adapter': policy['adapter'],
        'model_id': model_ids[policy['id']],
        'model_revision': revisions[policy['id']],
        'runtime_sha256': HEX_C,
    }


def reference_for(policy):
    if policy['reference_requirement'] == 'none':
        return None
    return {
        'audio_sha256': HEX_A,
        'transcript_sha256': HEX_B,
        'permission_scope': 'owner-recorded-original',
    }


def measured_candidate(plan, candidate_id):
    policy = candidate_policy(plan, candidate_id)
    line_ids = [item['id'] for item in plan['evaluation']['lines']]
    contrast = plan['delivery_contrast']
    return {
        'id': candidate_id,
        'status': 'measured',
        'producer': producer_for(policy),
        'configuration_sha256': HEX_A,
        'reference': reference_for(policy),
        'metrics': {
            'load_seconds': 4.0,
            'first_audio_seconds': 6.0,
            'generation_seconds': 120.0,
            'peak_host_bytes': 4_000_000_000,
            'peak_vram_bytes': 0,
            'generated_seconds': 80.0,
            'accepted_seconds': 70.0,
            'correction_seconds': 15.0,
        },
        'lines': [
            {
                'id': line_id,
                'audio_sha256': HEX_B,
                'machine': {
                    'status': 'exact',
                    'transcript_sha256': HEX_C,
                    'substitutions': 0,
                    'insertions': 0,
                    'deletions': 0,
                    'empty': False,
                },
                'owner': {
                    'clarity': 5,
                    'warmth': 4,
                    'fatigue': 4,
                    'identity': 4,
                    'delivery': 4,
                    'accepted': True,
                    'notes': 'Clear and stable in this bounded audition.',
                },
            }
            for line_id in line_ids
        ],
        'delivery_contrast': {
            'calm_line_id': contrast['calm_line_id'],
            'spark_line_id': contrast['spark_line_id'],
            'identity_consistency': 4,
            'delivery_control': 4,
            'accepted': True,
            'notes': 'The delivery changed while the perceived speaker remained stable.',
        },
        'notes': 'Measured on the same canonical script and policy revision.',
    }


def accepted_report(plan):
    selected = 'qwen3-reusable-reference-v1'
    measured = [
        'qwen3-voice-design-v1',
        selected,
        'indextts-2-5-expressive-v1',
        'kokoro-af-heart-control-v1',
    ]
    return {
        'schema_version': 1,
        'plan_sha256': plan['plan_sha256'],
        'profile_id': plan['profile']['id'],
        'evaluation_set_sha256': plan['evaluation']['sha256'],
        'candidates': [measured_candidate(plan, identifier) for identifier in measured],
        'long_form': {
            'candidate_id': selected,
            'manifest_sha256': HEX_A,
            'audio_sha256': HEX_B,
            'duration_seconds': 360.0,
            'owner': {
                'listened_end_to_end': True,
                'identity_consistent': True,
                'pronunciation_reviewed': True,
                'accepted': True,
                'fatigue': 4,
                'notes': 'Reviewed end to end without material identity drift.',
            },
        },
        'decision': {
            'state': 'accepted',
            'candidate_id': selected,
            'profile_id': plan['profile']['id'],
            'rationale': 'The reusable candidate remained clear and low-fatigue in the long-form review.',
            'owner_reviewed_at': '2026-09-19T18:30:00Z',
        },
    }


def local_accepted_registry(path):
    catalog = voice_profile.load_catalog()
    base = next(item for item in catalog['profiles'] if item['id'] == 'ember-brief-v1')
    replacement = copy.deepcopy(base)
    replacement['revision'] += 1
    replacement['status'] = 'accepted'
    replacement['supersedes_profile_sha256'] = voice_profile.profile_digest(base)
    replacement['identity'].update(
        model_id='Qwen/Qwen3-TTS-12Hz-1.7B-Base',
        model_revision=REV_A,
        voice='ember-brief-reference-v1',
        reference={
            'asset_id': 'asset-ember-brief-reference-v1',
            'sha256': HEX_A,
            'transcript_sha256': HEX_B,
            'permission_scope': 'owner-recorded-original',
        },
    )
    replacement['producer'] = {
        'adapter': 'qwen3-tts-profile',
        'runnable': True,
        'speaker_id': 'ember-brief',
    }
    for delivery in replacement['deliveries']:
        delivery['status'] = 'qualified'
    replacement['acceptance'] = {
        'state': 'accepted',
        'owner_review': 'accepted',
        'qualification_report_sha256': HEX_A,
        'long_form_manifest_sha256': HEX_B,
        'long_form_audio_sha256': HEX_C,
        'accepted_at': '2026-09-19T18:00:00Z',
    }
    path.write_text(
        json.dumps({'schema_version': 1, 'profiles': [replacement]}),
        encoding='utf-8',
    )


class VoiceProfileQualificationTests(unittest.TestCase):
    def test_plan_is_deterministic_and_bound_to_canonical_policy(self):
        first = qualification.build_plan('ember-brief-v1')
        second = qualification.build_plan('ember-brief-v1')
        self.assertEqual(first, second)
        self.assertFalse(first['generation_submitted'])
        self.assertRegex(first['plan_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(
            first['policy']['id'],
            'spoken-brief-qualification-policy-v1',
        )
        self.assertEqual(first['policy']['revision'], 1)
        self.assertRegex(first['policy']['sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(
            [item['id'] for item in first['candidates']],
            [
                'qwen3-voice-design-v1',
                'qwen3-reusable-reference-v1',
                'indextts-2-5-expressive-v1',
                'kokoro-af-heart-control-v1',
            ],
        )
        self.assertEqual(sum(bool(item['control']) for item in first['candidates']), 1)
        self.assertEqual(first['long_form']['minimum_seconds'], 300)
        self.assertEqual(first['long_form']['maximum_seconds'], 600)

    def test_rehashed_plan_cannot_weaken_canonical_policy(self):
        plan = qualification.build_plan('ember-brief-v1')
        mutations = []

        candidate = copy.deepcopy(plan)
        candidate['candidates'][0]['role'] = 'weakened-role'
        mutations.append(candidate)

        measurements = copy.deepcopy(plan)
        measurements['measurement_fields'].pop()
        mutations.append(measurements)

        bounds = copy.deepcopy(plan)
        bounds['long_form']['minimum_seconds'] = 1
        mutations.append(bounds)

        evaluation = copy.deepcopy(plan)
        evaluation['evaluation']['lines'][0]['text'] = 'Locally rewritten words.'
        evaluation['evaluation']['sha256'] = qualification.canonical_digest({
            'schema_version': 1,
            'id': evaluation['evaluation']['id'],
            'revision': evaluation['evaluation']['revision'],
            'name': 'Spoken Brief shared voice qualification set',
            'lines': evaluation['evaluation']['lines'],
        })
        mutations.append(evaluation)

        for mutated in mutations:
            mutated['plan_sha256'] = qualification.canonical_digest(
                {key: value for key, value in mutated.items() if key != 'plan_sha256'}
            )
            report = accepted_report(plan)
            report['plan_sha256'] = mutated['plan_sha256']
            with self.subTest(mutated=mutated), self.assertRaisesRegex(
                qualification.QualificationError,
                r'canonical (policy|evaluation)',
            ):
                qualification.validate_report(mutated, report)

    def test_local_profile_registry_cannot_rewrite_policy_or_evaluation(self):
        plain = qualification.build_plan('ember-brief-v1')
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / 'profiles.json'
            local_accepted_registry(registry)
            local = qualification.build_plan('ember-brief-v1', registry_path=registry)
        self.assertNotEqual(plain['profile']['binding_sha256'], local['profile']['binding_sha256'])
        for field in ('policy', 'evaluation', 'candidates', 'measurement_fields', 'long_form', 'delivery_contrast'):
            self.assertEqual(plain[field], local[field])

    def test_delivery_contrast_uses_identical_text_with_distinct_deliveries(self):
        plan = qualification.build_plan('ember-brief-v1')
        contrast = plan['delivery_contrast']
        lines = {item['id']: item for item in plan['evaluation']['lines']}
        calm = lines[contrast['calm_line_id']]
        spark = lines[contrast['spark_line_id']]
        self.assertEqual(calm['text'], spark['text'])
        self.assertEqual(calm['delivery_id'], 'calm-brief')
        self.assertEqual(spark['delivery_id'], 'spark-recap')
        self.assertNotEqual(calm['delivery_id'], spark['delivery_id'])

    def test_complete_owner_accepted_report_returns_profile_acceptance_evidence(self):
        plan = qualification.build_plan('ember-brief-v1')
        report = accepted_report(plan)
        snapshot = copy.deepcopy(report)
        result = qualification.validate_report(plan, report)
        self.assertEqual(report, snapshot)
        self.assertEqual((result['state'], result['profile_id'], result['candidate_id']),
                         ('accepted', 'ember-brief-v1', 'qwen3-reusable-reference-v1'))
        self.assertEqual(result['selected_producer_family'], 'qwen3-tts')
        self.assertEqual(result['independent_producer_families'], ['indextts'])
        self.assertEqual(result['reference']['audio_sha256'], HEX_A)
        self.assertEqual(result['long_form_manifest_sha256'], HEX_A)
        self.assertEqual(result['long_form_audio_sha256'], HEX_B)
        self.assertRegex(result['qualification_report_sha256'], r'^[0-9a-f]{64}$')

    def test_report_requires_control_required_candidates_and_two_non_controls(self):
        plan = qualification.build_plan('ember-brief-v1')
        missing_control = accepted_report(plan)
        missing_control['candidates'] = [
            item for item in missing_control['candidates']
            if item['id'] != 'kokoro-af-heart-control-v1'
        ]
        with self.assertRaisesRegex(qualification.QualificationError, 'control'):
            qualification.validate_report(plan, missing_control)

        missing_required = accepted_report(plan)
        missing_required['candidates'] = [
            item for item in missing_required['candidates']
            if item['id'] != 'qwen3-voice-design-v1'
        ]
        with self.assertRaisesRegex(qualification.QualificationError, 'required candidate'):
            qualification.validate_report(plan, missing_required)

        only_one_non_control = accepted_report(plan)
        only_one_non_control['candidates'] = [
            item for item in only_one_non_control['candidates']
            if item['id'] in ('qwen3-reusable-reference-v1', 'kokoro-af-heart-control-v1')
        ]
        with self.assertRaisesRegex(qualification.QualificationError, 'two measured non-control'):
            qualification.validate_report(plan, only_one_non_control)

    def test_accepted_route_requires_an_independent_producer_family(self):
        plan = qualification.build_plan('ember-brief-v1')
        report = accepted_report(plan)
        report['candidates'] = [
            item for item in report['candidates']
            if item['id'] != 'indextts-2-5-expressive-v1'
        ]
        with self.assertRaisesRegex(qualification.QualificationError, 'independent producer family'):
            qualification.validate_report(plan, report)

    def test_candidate_producer_must_match_policy_and_pin_runtime(self):
        plan = qualification.build_plan('ember-brief-v1')
        family = accepted_report(plan)
        family['candidates'][1]['producer']['family'] = 'different-family'
        with self.assertRaisesRegex(qualification.QualificationError, 'producer family'):
            qualification.validate_report(plan, family)

        adapter = accepted_report(plan)
        adapter['candidates'][1]['producer']['adapter'] = 'different-adapter'
        with self.assertRaisesRegex(qualification.QualificationError, 'adapter'):
            qualification.validate_report(plan, adapter)

        revision = accepted_report(plan)
        revision['candidates'][1]['producer']['model_revision'] = 'short'
        with self.assertRaisesRegex(qualification.QualificationError, 'model_revision'):
            qualification.validate_report(plan, revision)

        runtime = accepted_report(plan)
        runtime['candidates'][1]['producer']['runtime_sha256'] = 'short'
        with self.assertRaisesRegex(qualification.QualificationError, 'runtime_sha256'):
            qualification.validate_report(plan, runtime)

    def test_reference_required_candidate_needs_exact_local_evidence(self):
        plan = qualification.build_plan('ember-brief-v1')
        report = accepted_report(plan)
        report['candidates'][1]['reference'] = None
        with self.assertRaisesRegex(qualification.QualificationError, 'reference'):
            qualification.validate_report(plan, report)

        scope = accepted_report(plan)
        scope['candidates'][1]['reference']['permission_scope'] = r'C:\recordings\voice.wav'
        with self.assertRaisesRegex(qualification.QualificationError, 'permission_scope'):
            qualification.validate_report(plan, scope)

    def test_delivery_contrast_is_separate_and_required_for_selected_candidate(self):
        plan = qualification.build_plan('ember-brief-v1')
        wrong_pair = accepted_report(plan)
        wrong_pair['candidates'][1]['delivery_contrast']['calm_line_id'] = 'neutral'
        with self.assertRaisesRegex(qualification.QualificationError, 'delivery contrast'):
            qualification.validate_report(plan, wrong_pair)

        rejected = accepted_report(plan)
        rejected['candidates'][1]['delivery_contrast']['accepted'] = False
        with self.assertRaisesRegex(qualification.QualificationError, 'contrast'):
            qualification.validate_report(plan, rejected)

    def test_report_rejects_non_finite_boolean_and_negative_metrics(self):
        plan = qualification.build_plan('ember-brief-v1')
        cases = [float('nan'), float('inf'), True, -0.01]
        for invalid in cases:
            report = accepted_report(plan)
            report['candidates'][0]['metrics']['generation_seconds'] = invalid
            with self.subTest(invalid=repr(invalid)), self.assertRaisesRegex(
                    qualification.QualificationError, 'generation_seconds'):
                qualification.validate_report(plan, report)

    def test_report_requires_exact_evaluation_line_coverage_and_unique_ids(self):
        plan = qualification.build_plan('ember-brief-v1')
        report = accepted_report(plan)
        report['candidates'][0]['lines'].pop()
        with self.assertRaisesRegex(qualification.QualificationError, 'evaluation lines'):
            qualification.validate_report(plan, report)

        duplicate = accepted_report(plan)
        duplicate['candidates'].append(copy.deepcopy(duplicate['candidates'][0]))
        with self.assertRaisesRegex(qualification.QualificationError, 'duplicate candidate'):
            qualification.validate_report(plan, duplicate)

    def test_long_form_must_be_five_to_ten_minutes_and_owner_reviewed(self):
        plan = qualification.build_plan('ember-brief-v1')
        for duration in (299.9, 600.1):
            report = accepted_report(plan)
            report['long_form']['duration_seconds'] = duration
            with self.subTest(duration=duration), self.assertRaisesRegex(
                    qualification.QualificationError, '300'):
                qualification.validate_report(plan, report)

        not_listened = accepted_report(plan)
        not_listened['long_form']['owner']['listened_end_to_end'] = False
        with self.assertRaisesRegex(qualification.QualificationError, 'end to end'):
            qualification.validate_report(plan, not_listened)

    def test_accepted_decision_must_select_measured_selectable_non_control_candidate(self):
        plan = qualification.build_plan('ember-brief-v1')
        report = accepted_report(plan)
        report['decision']['candidate_id'] = 'missing-candidate'
        with self.assertRaisesRegex(qualification.QualificationError, 'measured'):
            qualification.validate_report(plan, report)

        control = accepted_report(plan)
        control['decision']['candidate_id'] = 'kokoro-af-heart-control-v1'
        with self.assertRaisesRegex(qualification.QualificationError, 'non-control'):
            qualification.validate_report(plan, control)

        exploration = accepted_report(plan)
        exploration['decision']['candidate_id'] = 'qwen3-voice-design-v1'
        exploration['long_form']['candidate_id'] = 'qwen3-voice-design-v1'
        with self.assertRaisesRegex(qualification.QualificationError, 'selectable'):
            qualification.validate_report(plan, exploration)


if __name__ == '__main__':
    unittest.main()
