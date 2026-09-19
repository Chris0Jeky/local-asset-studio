import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import voice_profile_qualification as qualification


HEX_A = 'a' * 64
HEX_B = 'b' * 64
HEX_C = 'c' * 64


def measured_candidate(candidate_id, line_ids):
    return {
        'id': candidate_id,
        'status': 'measured',
        'configuration_sha256': HEX_A,
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
        'notes': 'Measured on the same script revision.',
    }


def accepted_report(plan):
    candidate_ids = [item['id'] for item in plan['candidates']]
    line_ids = [item['id'] for item in plan['evaluation']['lines']]
    selected = 'qwen3-reusable-reference-v1'
    measured = ['qwen3-voice-design-v1', selected, 'kokoro-af-heart-control-v1']
    assert set(measured).issubset(candidate_ids)
    return {
        'schema_version': 1,
        'plan_sha256': plan['plan_sha256'],
        'profile_id': plan['profile']['id'],
        'evaluation_set_sha256': plan['evaluation']['sha256'],
        'candidates': [measured_candidate(identifier, line_ids) for identifier in measured],
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


class VoiceProfileQualificationTests(unittest.TestCase):
    def test_plan_is_deterministic_and_declares_zero_generation(self):
        first = qualification.build_plan('ember-brief-v1')
        second = qualification.build_plan('ember-brief-v1')
        self.assertEqual(first, second)
        self.assertFalse(first['generation_submitted'])
        self.assertRegex(first['plan_sha256'], r'^[0-9a-f]{64}$')
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
        self.assertGreaterEqual(len(first['evaluation']['lines']), 8)
        self.assertEqual(first['long_form']['minimum_seconds'], 300)
        self.assertEqual(first['long_form']['maximum_seconds'], 600)

    def test_complete_owner_accepted_report_returns_profile_acceptance_evidence(self):
        plan = qualification.build_plan('ember-brief-v1')
        report = accepted_report(plan)
        snapshot = copy.deepcopy(report)
        result = qualification.validate_report(plan, report)
        self.assertEqual(report, snapshot)
        self.assertEqual((result['state'], result['profile_id'], result['candidate_id']),
                         ('accepted', 'ember-brief-v1', 'qwen3-reusable-reference-v1'))
        self.assertEqual(result['long_form_manifest_sha256'], HEX_A)
        self.assertEqual(result['long_form_audio_sha256'], HEX_B)
        self.assertRegex(result['qualification_report_sha256'], r'^[0-9a-f]{64}$')

    def test_report_requires_the_control_and_two_measured_non_control_candidates(self):
        plan = qualification.build_plan('ember-brief-v1')
        missing_control = accepted_report(plan)
        missing_control['candidates'] = [
            item for item in missing_control['candidates']
            if item['id'] != 'kokoro-af-heart-control-v1'
        ]
        with self.assertRaisesRegex(qualification.QualificationError, 'control'):
            qualification.validate_report(plan, missing_control)

        only_one_non_control = accepted_report(plan)
        only_one_non_control['candidates'] = [
            item for item in only_one_non_control['candidates']
            if item['id'] != 'qwen3-voice-design-v1'
        ]
        with self.assertRaisesRegex(qualification.QualificationError, 'two measured non-control'):
            qualification.validate_report(plan, only_one_non_control)

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

    def test_accepted_decision_must_select_a_measured_non_control_candidate(self):
        plan = qualification.build_plan('ember-brief-v1')
        report = accepted_report(plan)
        report['decision']['candidate_id'] = 'indextts-2-5-expressive-v1'
        with self.assertRaisesRegex(qualification.QualificationError, 'measured'):
            qualification.validate_report(plan, report)

        control = accepted_report(plan)
        control['decision']['candidate_id'] = 'kokoro-af-heart-control-v1'
        with self.assertRaisesRegex(qualification.QualificationError, 'non-control'):
            qualification.validate_report(plan, control)


if __name__ == '__main__':
    unittest.main()
