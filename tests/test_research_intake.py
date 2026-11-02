import copy
import json
from pathlib import Path
import tempfile
import unittest

from studio_workflow import research_intake as ri


def source():
    token = '\ue200cite\ue202search1\ue201'
    return {'version': 1, 'title': 'Synthetic research', 'widget_state': {
        'status': 'completed', 'report_message': {
            'content': {'content_type': 'text', 'parts': ['# Report\nClaim. ' + token]},
            'metadata': {'content_references': [{'type': 'grouped_webpages',
                'matched_text': token, 'items': [{'title': 'Primary',
                    'url': 'https://example.org/source', 'supporting_websites': []}]}]}}}}


class ResearchIntakeTests(unittest.TestCase):
    def test_exact_bytes_and_text_are_preserved_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = (json.dumps(source(), ensure_ascii=False, indent=3) + '\n').encode()
            path = Path(tmp) / 'source.json'; path.write_bytes(raw)
            dest = Path(tmp) / 'archive'
            result = ri.import_report(path, dest)
            self.assertEqual((dest / 'source.json').read_bytes(), raw)
            self.assertEqual((dest / 'report.original.md').read_text(),
                             source()['widget_state']['report_message']['content']['parts'][0])
            self.assertIn('https://example.org/source', (dest / 'report.md').read_text())
            self.assertEqual(result['visibility'], 'private_local')
            self.assertFalse(result['claims_independently_verified'])
            self.assertEqual(ri.verify_archive(dest)['status'], 'intact')
            self.assertEqual(path.read_bytes(), raw)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'in.json'; path.write_text(json.dumps(source()))
            dest = Path(tmp) / 'archive'; ri.import_report(path, dest)
            with self.assertRaises(FileExistsError): ri.import_report(path, dest)

    def test_tampered_report_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'in.json'; path.write_text(json.dumps(source()))
            dest = Path(tmp) / 'archive'; ri.import_report(path, dest)
            (dest / 'report.md').write_text('replacement')
            with self.assertRaisesRegex(ValueError, 'hash'): ri.verify_archive(dest)

    def test_unresolved_reference_is_not_erased(self):
        doc = source(); token = '\ue200cite\ue202missing\ue201'
        doc['widget_state']['report_message']['content']['parts'][0] += token
        result = ri.extract(doc)
        self.assertIn(token, result['linked_markdown'])
        self.assertIn(token, result['unresolved_references'])

    def test_incomplete_or_non_text_report_refused(self):
        for status in ('running', None):
            doc = source(); doc['widget_state']['status'] = status
            with self.assertRaises(ValueError): ri.extract(doc)
        doc = source(); doc['widget_state']['report_message']['content']['parts'] = []
        with self.assertRaises(ValueError): ri.extract(doc)

    def test_unsafe_reference_not_promoted_to_link(self):
        doc = source()
        doc['widget_state']['report_message']['metadata']['content_references'][0]['items'][0]['url'] = 'javascript:bad'
        result = ri.extract(doc)
        self.assertNotIn('(javascript:', result['linked_markdown'])
        self.assertTrue(result['unresolved_references'])

    def test_duplicate_and_nonfinite_json_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'in.json'
            for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
                p.write_text(raw)
                with self.assertRaises(ValueError): ri.import_report(p, Path(tmp) / 'out')
                self.assertFalse((Path(tmp) / 'out').exists())

    def test_archive_member_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'in.json'; p.write_text(json.dumps(source()))
            dest = Path(tmp) / 'out'; ri.import_report(p, dest)
            m = json.loads((dest / 'manifest.json').read_text())
            m['files']['../in.json'] = m['files']['source.json']
            (dest / 'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError): ri.verify_archive(dest)

    def test_original_report_must_be_single_part_text(self):
        doc = source(); doc['widget_state']['report_message']['content']['parts'].append('second')
        with self.assertRaises(ValueError): ri.extract(doc)


    def test_manifest_cannot_promote_imported_claims_to_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'in.json'; p.write_text(json.dumps(source()))
            dest = Path(tmp) / 'out'; ri.import_report(p, dest)
            m = json.loads((dest / 'manifest.json').read_text())
            m['claims_independently_verified'] = True
            (dest / 'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError): ri.verify_archive(dest)
