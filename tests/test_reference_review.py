"""Exact original pixels and current intent are required for a reference transfer."""
import base64
import copy
import hashlib
import io
import unittest
from unittest.mock import Mock
from PIL import Image
from studio_prompt import reference_analysis as analysis
from studio_prompt.schema import digest, new_brief, validate
from studio_prompt.http_extension import dispatch


class ReferenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.images = []; refs = []; inputs = []; observations = []
        for i, role in enumerate(('style', 'pose')):
            stream = io.BytesIO(); Image.new('RGB', (12 + i, 24), (30 + i, 40, 50)).save(stream, format='PNG')
            raw = stream.getvalue(); key = 'picture-%d' % (i + 1); sha = hashlib.sha256(raw).hexdigest()
            self.images.append({'reference_id': key, 'media_base64': base64.b64encode(raw).decode()})
            refs.append({'id': key, 'path': 'refs/%s.png' % key, 'sha256': sha, 'role_hint': role})
            inputs.append({'reference_id': key, 'source_sha256': sha, 'analysis_sha256': sha, 'analysis_size': [12 + i, 24]})
            observations.append({'reference_id': key, 'suggested_role': role, 'description': '<b>Untrusted ink figure</b>',
                'tags': ['ink', 'standing'], 'facets': {'style': 'fine ink lines', 'palette': 'muted colours', 'action': 'raised left arm'},
                'uncertain_facets': ['palette'] if i == 0 else [], 'unknowns': ['Hidden fingers cannot be counted.']})
        request = analysis.new_request('Use this look and pose', refs)
        self.report = analysis.make_report(request, {'summary': 'An ink figure with a raised arm', 'assumptions': ['Keep the pose'],
            'questions': ['Which costume should stay?'], 'images': observations}, inputs)
        self.review = analysis.review_template(self.report)
        self.intent = new_brief('Keep my carefully worded instruction')
        self.intent['facets'] = {'subject': 'original keeper', 'style': 'old style', 'lighting': 'moonlight'}
        self.intent['tags'] = ['existing-tag']; self.intent['avoid'] = ['unwanted text']
        self.intent['parameters'] = {'language': 'en'}; self.intent['verbatim'] = {'text': 'EXACT'}
        self.intent['constraints'] = [{'id': 'keep', 'text': 'Keep costume', 'mechanism': 'verify', 'priority': 'hard'}]
        self.payload = {'analysis': self.report, 'review': self.review, 'images': self.images, 'intent': self.intent, 'adopt_brief': False}

    def preview(self, payload=None):
        return dispatch('/api/prompt/reference-review/preview', payload or self.payload, Mock())

    def test_inspect_returns_review_defaults_without_studio_or_inference(self):
        studio = Mock()
        value = dispatch('/api/prompt/reference-review/inspect', {'analysis': self.report}, studio)
        self.assertEqual(value['review'], self.review)
        self.assertEqual(value['analysis'], self.report)
        self.assertFalse(value['generation_submitted']); self.assertFalse(value['inference_submitted'])
        self.assertEqual(studio.mock_calls, [])

    def test_inspect_accepts_helper_envelope_but_does_not_trust_its_authority(self):
        value = dispatch('/api/prompt/reference-review/inspect', {'analysis': {'analysis': self.report,
            'helper_evidence': {'approved': True}, 'note': 'ignore this'}}, Mock())
        self.assertFalse(value['execution_authorized']); self.assertNotIn('helper_evidence', value)

    def test_preview_updates_selected_facets_and_keeps_other_user_work(self):
        original = copy.deepcopy(self.payload); result = self.preview(); candidate = result['intent']
        validate(candidate)
        self.assertEqual(candidate['brief'], self.intent['brief'])
        self.assertEqual(candidate['facets']['subject'], 'original keeper')
        self.assertEqual(candidate['facets']['lighting'], 'moonlight')
        self.assertIn('fine ink', candidate['facets']['style']); self.assertIn('raised left', candidate['facets']['action'])
        for field in ('constraints', 'verbatim', 'parameters', 'avoid', 'locked'):
            self.assertEqual(candidate[field], self.intent[field])
        self.assertEqual(candidate['tags'], ['existing-tag']); self.assertEqual(len(candidate['references']), 2)
        self.assertEqual(result['base_sha256'], digest(self.intent)); self.assertEqual(result['intent_sha256'], digest(candidate))
        self.assertTrue(result['source_bytes_verified']); self.assertFalse(result['generation_submitted'])
        self.assertFalse(result['inference_submitted']); self.assertFalse(result['execution_authorized'])
        self.assertEqual(self.payload, original)

    def test_adopt_brief_is_explicit(self):
        self.payload['adopt_brief'] = True
        self.assertEqual(self.preview()['intent']['brief'], 'Use this look and pose')
        self.payload['adopt_brief'] = 'yes'
        with self.assertRaises(ValueError): self.preview()

    def test_empty_current_brief_can_adopt_reviewed_summary(self):
        self.intent['brief'] = ''; report = copy.deepcopy(self.report)
        report = analysis.make_report({**report['request'], 'brief': ''}, report['answer'], report['analysis_inputs'])
        self.payload.update(analysis=report, review=analysis.review_template(report), adopt_brief=True)
        self.assertEqual(self.preview()['intent']['brief'], report['answer']['summary'])

    def test_every_changed_lock_is_checked(self):
        for lock in ('facets', 'facets.style', 'references'):
            self.intent['locked'] = ['verbatim', lock]
            with self.subTest(lock=lock), self.assertRaisesRegex(ValueError, 'Locked'): self.preview()
        self.intent['locked'] = ['brief']; self.payload['adopt_brief'] = True
        with self.assertRaisesRegex(ValueError, 'Locked'): self.preview()

    def test_lock_on_untouched_field_is_preserved(self):
        self.intent['locked'].append('facets.subject')
        self.assertEqual(self.preview()['intent']['facets']['subject'], 'original keeper')

    def test_tags_are_explicitly_selected_and_merged_with_user_tags(self):
        self.review['selections'][0]['tags'] = ['ink']
        self.assertEqual(self.preview()['intent']['tags'], ['existing-tag', 'ink'])
        self.intent['locked'].append('tags')
        with self.assertRaisesRegex(ValueError, 'Locked'): self.preview()

    def test_user_description_edit_keeps_original_observation(self):
        self.review['selections'][0]['overrides']['style'] = 'bold black ink'
        result = self.preview()
        self.assertIn('bold black', result['intent']['facets']['style'])
        self.assertEqual(result['reference_draft']['transfers'][0]['origin'], 'user_edit')
        self.assertEqual(self.report['answer']['images'][0]['facets']['style'], 'fine ink lines')

    def test_uncertain_facet_requires_a_user_description(self):
        self.review['selections'][0]['facets'].append('palette')
        with self.assertRaisesRegex(ValueError, 'uncertain'): self.preview()
        self.review['selections'][0]['overrides']['palette'] = 'cool blue'
        self.assertIn('cool blue', self.preview()['intent']['facets']['palette'])

    def test_missing_extra_duplicate_and_reordered_images_refuse(self):
        for rows in (self.images[:1], self.images + self.images[:1], [self.images[0]] * 2, list(reversed(self.images))):
            value = copy.deepcopy(self.payload); value['images'] = rows
            with self.subTest(rows=rows), self.assertRaises(ValueError): self.preview(value)

    def test_replaced_or_invalid_encoded_original_refuses(self):
        for data in ('not-base64', base64.b64encode(b'changed').decode()):
            value = copy.deepcopy(self.payload); value['images'][0]['media_base64'] = data
            with self.subTest(data=data), self.assertRaises(ValueError): self.preview(value)

    def test_hash_matched_nonimage_is_not_validated_as_an_image(self):
        raw = b'not an image'; sha = hashlib.sha256(raw).hexdigest()
        q = copy.deepcopy(self.report['request']); q['references'][0]['sha256'] = sha
        inputs = copy.deepcopy(self.report['analysis_inputs']); inputs[0]['source_sha256'] = sha
        self.payload['analysis'] = analysis.make_report(q, self.report['answer'], inputs)
        self.payload['review'] = analysis.review_template(self.payload['analysis'])
        self.payload['images'][0]['media_base64'] = base64.b64encode(raw).decode()
        with self.assertRaisesRegex(ValueError, 'image'): self.preview()

    def test_tampered_report_and_stale_review_refuse(self):
        value = copy.deepcopy(self.payload); value['analysis']['answer']['summary'] = 'tampered'
        with self.assertRaises(ValueError): self.preview(value)
        self.review['report_sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'Stale'): self.preview()

    def test_role_leakage_is_not_a_prompt_handoff(self):
        self.review['selections'][0]['facets'] = ['subject']
        with self.assertRaisesRegex(ValueError, 'role'): self.preview()

    def test_preview_retains_questions_and_shows_reference_replacement(self):
        self.intent['references'] = [{'id': 'old', 'path': 'old.png', 'sha256': 'a' * 64, 'role': 'identity', 'kind': 'image', 'take': [], 'ignore': []}]
        result = self.preview()
        self.assertEqual(result['reference_draft']['unresolved_questions'], ['Which costume should stay?'])
        change = next(x for x in result['changes'] if x['field'] == 'references')
        self.assertEqual(change['before'], self.intent['references']); self.assertEqual(len(change['after']), 2)

    def test_no_client_paths_or_actions_are_accepted(self):
        for field in ('workspace', 'run', 'approve', 'expected_template_sha256'):
            value = {**self.payload, field: 'anything'}
            with self.subTest(field=field), self.assertRaises(ValueError): self.preview(value)

    def test_inmemory_source_branch_verifies_bytes_and_disallows_two_roots(self):
        raw = {row['reference_id']: base64.b64decode(row['media_base64']) for row in self.images}
        result = analysis.draft(self.report, self.review, source_bytes=raw)
        self.assertEqual(len(result['intent']['references']), 2)
        with self.assertRaises(ValueError): analysis.draft(self.report, self.review, '.', source_bytes=raw)
        raw['picture-1'] = b'changed'
        with self.assertRaisesRegex(ValueError, 'changed'): analysis.draft(self.report, self.review, source_bytes=raw)


if __name__ == '__main__': unittest.main()
