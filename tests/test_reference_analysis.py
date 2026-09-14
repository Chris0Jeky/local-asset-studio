"""Reference observations become explicit, source-bound draft inputs, not jobs."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from studio_prompt import reference_analysis as r
from studio_prompt.schema import digest, validate


class ReferenceAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.refs = []
        for n in range(4):
            raw = ('source-%d' % n).encode(); name = 'ref%d.png' % n
            (self.root / name).write_bytes(raw)
            self.refs.append({'id': 'picture-%d' % (n + 1), 'path': name,
                'sha256': hashlib.sha256(raw).hexdigest(), 'role_hint': 'auto'})
        self.q = r.new_request('Same feeling, with this pose', self.refs)
        self.answer = {'summary': 'Keep the ink style and use the final pose.',
            'assumptions': ['The last picture supplies pose.'], 'questions': [],
            'images': [{'reference_id': ref['id'], 'suggested_role': 'style' if n < 3 else 'pose',
                'description': 'A figure in an ink illustration.', 'tags': ['ink', 'standing'],
                'facets': {'style': 'fine ink lines', 'palette': 'warm muted colours',
                           'action': 'standing with raised left arm', 'subject': 'blue coat'},
                'uncertain_facets': [], 'unknowns': ['Hidden hand is not visible.']}
                for n, ref in enumerate(self.refs)]}
        self.inputs = [{'reference_id': ref['id'], 'source_sha256': ref['sha256'],
                        'analysis_sha256': 'a' * 64, 'analysis_size': [256, 768]}
                       for ref in self.refs]

    def report(self): return r.make_report(self.q, self.answer, self.inputs)
    def test_four_images_and_short_or_empty_brief(self):
        self.assertEqual(len(r.new_request('', self.refs)['references']), 4)
        self.assertEqual(self.q['brief'], 'Same feeling, with this pose')
    def test_refuses_missing_excess_duplicate_and_unsafe_references(self):
        for refs in ([], self.refs + [self.refs[0]], [self.refs[0]] * 2):
            with self.subTest(refs=refs), self.assertRaises(ValueError): r.new_request('', refs)
        for key, value in [('path', '../outside.png'), ('path', 'C:\\image.png'),
                           ('sha256', 'not-a-hash'), ('role_hint', 'execute')]:
            refs = copy.deepcopy(self.refs); refs[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): r.new_request('', refs)
    def test_request_does_not_mutate_input(self):
        original = copy.deepcopy(self.refs); r.new_request('', self.refs)['references'][0]['path'] = 'other'
        self.assertEqual(self.refs, original)
    def test_answer_must_cover_exact_image_order(self):
        for rows in (self.answer['images'][:-1], list(reversed(self.answer['images'])), [self.answer['images'][0]] * 4):
            a = copy.deepcopy(self.answer); a['images'] = rows
            with self.subTest(rows=rows), self.assertRaises(ValueError): r.make_report(self.q, a, self.inputs)
    def test_explicit_hint_cannot_be_reassigned_by_model(self):
        self.q['references'][0]['role_hint'] = 'identity'
        with self.assertRaisesRegex(ValueError, 'role hint'): self.report()
    def test_invalid_and_unbounded_model_output(self):
        for field, value in [('tags', ['x'] * 21), ('suggested_role', 'mask'),
                             ('facets', {'artist': 'guessed'}), ('description', 'x' * 1001),
                             ('uncertain_facets', ['invented']), ('unknowns', ['x'] * 9)]:
            a = copy.deepcopy(self.answer); a['images'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): r.make_report(self.q, a, self.inputs)
        a = copy.deepcopy(self.answer); a['execute'] = True
        with self.assertRaises(ValueError): r.make_report(self.q, a, self.inputs)
    def test_geometry_and_hash_evidence_must_match(self):
        for key, value in [('source_sha256', 'b' * 64), ('analysis_sha256', 'bad'),
                           ('analysis_size', [True, 768]), ('analysis_size', [769, 768])]:
            inputs = copy.deepcopy(self.inputs); inputs[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): r.make_report(self.q, self.answer, inputs)
        with self.assertRaises(ValueError): r.make_report(self.q, self.answer, self.inputs[:-1])
    def test_review_defaults_are_role_scoped_and_do_not_transfer_tags(self):
        choice = r.review_template(self.report())
        self.assertEqual(choice['selections'][0]['facets'], ['palette', 'style'])
        self.assertEqual(choice['selections'][3]['facets'], ['action'])
        self.assertEqual(choice['selections'][0]['tags'], [])
    def test_projection_is_valid_existing_intent_and_retains_all_sources(self):
        report = self.report(); before = copy.deepcopy(report)
        result = r.draft(report, r.review_template(report), self.root)
        validate(result['intent'])
        self.assertEqual(len(result['intent']['references']), 4)
        self.assertEqual(result['intent']['brief'], self.q['brief'])
        self.assertNotIn('subject', result['intent']['facets'])
        self.assertIn('raised left arm', result['intent']['facets']['action'])
        self.assertFalse(result['generation_submitted']); self.assertFalse(result['execution_authorized'])
        self.assertEqual(report, before)
    def test_blank_brief_uses_explicitly_reviewed_summary(self):
        self.q['brief'] = ''; report = self.report()
        result = r.draft(report, r.review_template(report), self.root)
        self.assertEqual(result['intent']['brief'], self.answer['summary'])
        self.assertEqual(result['brief_origin'], 'reviewed_analysis_summary')
    def test_user_can_edit_description_without_rewriting_observation(self):
        report = self.report(); choice = r.review_template(report)
        choice['selections'][0]['overrides'] = {'palette': 'cool blue and silver'}
        result = r.draft(report, choice, self.root)
        self.assertIn('cool blue', result['intent']['facets']['palette'])
        self.assertEqual(result['transfers'][0]['origin'], 'user_edit')
        self.assertEqual(report['answer']['images'][0]['facets']['palette'], 'warm muted colours')
    def test_uncertain_facets_not_selected_by_default_and_require_edit(self):
        self.answer['images'][0]['uncertain_facets'] = ['palette']; report = self.report()
        choice = r.review_template(report)
        self.assertNotIn('palette', choice['selections'][0]['facets'])
        choice['selections'][0]['facets'].append('palette')
        with self.assertRaisesRegex(ValueError, 'uncertain'): r.draft(report, choice, self.root)
        choice['selections'][0]['overrides']['palette'] = 'warm colours selected by user'
        self.assertTrue(r.draft(report, choice, self.root)['transfers'])
    def test_no_cross_role_transfer_or_unknown_selected_tags(self):
        report = self.report()
        for key, value in [('facets', ['subject']), ('tags', ['invented LoRA']), ('overrides', {'subject': 'red coat'})]:
            choice = r.review_template(report); choice['selections'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): r.draft(report, choice, self.root)
    def test_report_or_review_changes_refuse(self):
        report = self.report(); choice = r.review_template(report)
        report['answer']['summary'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'report'): r.draft(report, choice, self.root)
        report = self.report(); choice['report_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'Stale'): r.draft(report, choice, self.root)
    def test_source_replaced_after_analysis_refuses_draft(self):
        report = self.report(); (self.root / self.refs[2]['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'): r.draft(report, r.review_template(report), self.root)
    def test_reordered_or_omitted_review_refs_refuse(self):
        report = self.report()
        for change in (lambda rows: rows.pop(), lambda rows: rows.reverse()):
            choice = r.review_template(report); change(choice['selections'])
            with self.assertRaises(ValueError): r.draft(report, choice, self.root)
    def test_selected_tags_are_explicit_and_keep_attribution(self):
        report = self.report(); choice = r.review_template(report); choice['selections'][0]['tags'] = ['ink']
        result = r.draft(report, choice, self.root)
        self.assertEqual(result['intent']['tags'], ['ink'])
        self.assertTrue(any(x['field'] == 'tags' and x['reference_id'] == 'picture-1' for x in result['transfers']))
    def test_questions_and_occlusion_remain_unresolved(self):
        self.answer['questions'] = ['Which identity should be retained?']; report = self.report()
        result = r.draft(report, r.review_template(report), self.root)
        self.assertEqual(result['unresolved_questions'], self.answer['questions'])
        self.assertIn('not visible', result['unknowns'][0]['text'])
    def test_report_cannot_claim_authority_even_with_new_digest(self):
        report = self.report(); report['execution_authorized'] = True
        report['report_sha256'] = digest({k:v for k,v in report.items() if k != 'report_sha256'})
        with self.assertRaises(ValueError): r.review_template(report)


if __name__ == '__main__': unittest.main()
