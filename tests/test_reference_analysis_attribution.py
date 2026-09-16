"""Prompt-facing facet text stays semantic while provenance retains source identity."""
import hashlib
import unittest

from studio_prompt import reference_analysis as analysis


class ReferenceFacetAttributionTests(unittest.TestCase):
    def report(self, observations):
        references = []
        images = []
        inputs = []
        originals = {}
        for index, (role, facets) in enumerate(observations, 1):
            reference_id = f'picture-{index}'
            path = f'reference-{index}.png'
            raw = f'source-{index}'.encode('ascii')
            source_hash = hashlib.sha256(raw).hexdigest()
            references.append({
                'id': reference_id,
                'path': path,
                'sha256': source_hash,
                'role_hint': role,
            })
            images.append({
                'reference_id': reference_id,
                'suggested_role': role,
                'description': 'A reviewed image reference.',
                'tags': [],
                'facets': facets,
                'uncertain_facets': [],
                'unknowns': [],
            })
            inputs.append({
                'reference_id': reference_id,
                'source_sha256': source_hash,
                'analysis_sha256': hashlib.sha256(f'analysis-{index}'.encode('ascii')).hexdigest(),
                'analysis_size': [256, 256],
            })
            originals[reference_id] = raw
        request = analysis.new_request('Use the reviewed visual traits.', references)
        answer = {
            'summary': 'A bounded reviewed reference description.',
            'assumptions': [],
            'questions': [],
            'images': images,
        }
        return analysis.make_report(request, answer, inputs), originals

    def test_one_contributor_does_not_leak_internal_reference_id_into_prompt_facet(self):
        report, originals = self.report([
            ('pose', {'action': 'standing with the left arm raised'}),
        ])
        result = analysis.draft(
            report,
            analysis.review_template(report),
            source_bytes=originals,
        )
        self.assertEqual(result['intent']['facets']['action'], 'standing with the left arm raised')
        self.assertNotIn('picture-1:', result['intent']['facets']['action'])
        self.assertEqual(result['transfers'][0]['reference_id'], 'picture-1')
        self.assertEqual(result['intent']['references'][0]['take'], [
            'action: standing with the left arm raised',
        ])

    def test_multiple_contributors_keep_labels_to_disambiguate_their_values(self):
        report, originals = self.report([
            ('style', {'style': 'fine ink lines'}),
            ('style', {'style': 'soft painterly shading'}),
        ])
        result = analysis.draft(
            report,
            analysis.review_template(report),
            source_bytes=originals,
        )
        self.assertEqual(
            result['intent']['facets']['style'],
            'picture-1: fine ink lines; picture-2: soft painterly shading',
        )
        self.assertEqual(
            [item['reference_id'] for item in result['transfers']],
            ['picture-1', 'picture-2'],
        )

    def test_duplicate_paths_and_content_hashes_are_refused_before_analysis(self):
        first = {
            'id': 'picture-1',
            'path': 'first.png',
            'sha256': 'a' * 64,
            'role_hint': 'style',
        }
        duplicate_path = {
            'id': 'picture-2',
            'path': 'first.png',
            'sha256': 'b' * 64,
            'role_hint': 'pose',
        }
        with self.assertRaisesRegex(ValueError, 'Duplicate reference path'):
            analysis.new_request('', [first, duplicate_path])

        duplicate_content = {
            'id': 'picture-2',
            'path': 'second.png',
            'sha256': 'a' * 64,
            'role_hint': 'pose',
        }
        with self.assertRaisesRegex(ValueError, 'Duplicate reference content'):
            analysis.new_request('', [first, duplicate_content])


if __name__ == '__main__':
    unittest.main()
