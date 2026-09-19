import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import spoken_brief
from spoken_brief_fixture import Fixture, wav_bytes


class SpokenBriefTests(unittest.TestCase):
    def test_source_selection_prefers_compressed_then_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'INDEX.md').write_text('index', encoding='utf-8')
            (root / 'COMPRESSED.md').write_text('compressed', encoding='utf-8')
            self.assertEqual(spoken_brief.resolve_source(root), (root / 'COMPRESSED.md').resolve())
            (root / 'COMPRESSED.md').unlink()
            self.assertEqual(spoken_brief.resolve_source(root), (root / 'INDEX.md').resolve())
            self.assertEqual(spoken_brief.resolve_source(root / 'INDEX.md'), (root / 'INDEX.md').resolve())

    def test_markdown_compiler_keeps_brief_content_but_omits_noise(self):
        source = '''---\ntitle: hidden metadata\n---\n# Release brief\n\n- **Decision:** ship the local queue.\n- Read [the evidence](https://example.test/evidence), not https://example.test/raw.\n\n```python\nprint("do not narrate source code")\n```\n\n| Owner | Status |\n| --- | --- |\n| Chris | Ready |\n'''
        compiled = spoken_brief.compile_markdown(source, source_name='COMPRESSED.md')
        text = ' '.join(item['text'] for item in compiled['segments'])
        self.assertIn('Release brief', text)
        self.assertIn('Decision: ship the local queue.', text)
        self.assertIn('Read the evidence, not link omitted.', text)
        self.assertIn('Owner. Status.', text)
        self.assertIn('Chris. Ready.', text)
        self.assertNotIn('hidden metadata', text)
        self.assertNotIn('print', text)
        self.assertEqual(compiled['omissions']['code_blocks'], 1)
        self.assertEqual(compiled['omissions']['raw_urls'], 1)
        self.assertEqual([item['id'] for item in compiled['segments']], [f'segment-{index:04d}' for index in range(1, len(compiled['segments']) + 1)])

    def test_segments_and_batches_fit_the_existing_voice_contract(self):
        paragraph = ' '.join('Sentence number %d explains a concrete engineering decision.' % index for index in range(90))
        compiled = spoken_brief.compile_markdown('# Long brief\n\n' + paragraph, source_name='COMPRESSED.md')
        self.assertGreater(len(compiled['segments']), 6)
        self.assertTrue(all(1 <= len(item['text']) <= spoken_brief.MAX_LINE_CHARS for item in compiled['segments']))
        batches = spoken_brief.batch_segments(compiled['segments'])
        self.assertTrue(all(1 <= len(batch) <= 6 for batch in batches))
        self.assertTrue(all(sum(len(item['text']) for item in batch) <= spoken_brief.MAX_BATCH_CHARS for batch in batches))
        self.assertTrue(all(sum(len(item['text'].split()) for item in batch) <= spoken_brief.MAX_BATCH_WORDS for batch in batches))
        self.assertEqual([item['id'] for batch in batches for item in batch], [item['id'] for item in compiled['segments']])


    def test_short_word_paragraph_still_obeys_the_batch_word_ceiling(self):
        source = '# Dense brief\n\n' + ' '.join(['a'] * 100) + '. ' + ' '.join(['b'] * 125) + '.'
        compiled = spoken_brief.compile_markdown(source, source_name='COMPRESSED.md')
        batches = spoken_brief.batch_segments(compiled['segments'])
        self.assertGreater(len(compiled['segments']), 2)
        self.assertTrue(all(sum(len(item['text'].split()) for item in batch) <= spoken_brief.MAX_BATCH_WORDS for batch in batches))


    def test_nul_characters_are_rejected_before_voice_preparation(self):
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'NUL'):
            spoken_brief.compile_markdown('safe\0unsafe', source_name='COMPRESSED.md')

    def test_compiler_refuses_an_accidentally_unbounded_audio_book(self):
        source = '\n\n'.join(f'Paragraph {index}.' for index in range(spoken_brief.MAX_SEGMENTS + 1))
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'segments'):
            spoken_brief.compile_markdown(source, source_name='COMPRESSED.md')



if __name__ == '__main__': unittest.main()
