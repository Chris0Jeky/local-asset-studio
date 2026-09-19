from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import spoken_brief
import spoken_brief_runtime
from spoken_brief_fixture import Fixture, wav_bytes


class SpokenBriefFinalizationTests(unittest.TestCase):
    def test_source_change_during_local_assembly_blocks_receipt_and_output(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir()
            source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source)
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256'])
            assemble = spoken_brief_runtime.assemble_wav

            def change_source(entries, output):
                result = assemble(entries, output)
                source.write_text('Changed while the local master was assembled.', encoding='utf-8')
                return result

            with patch.object(spoken_brief_runtime, 'assemble_wav', side_effect=change_source):
                with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'source changed'):
                    spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse((run_dir / 'receipt.json').exists())
            self.assertFalse((run_dir / 'COMPRESSED.spoken.wav').exists())

    def test_cached_segment_change_before_assembly_blocks_publication(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir()
            source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source)
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256'])
            assemble = spoken_brief_runtime.assemble_wav

            def replace_cached_segment(entries, output):
                Path(entries[0]['path']).write_bytes(wav_bytes(480, 7))
                return assemble(entries, output)

            with patch.object(spoken_brief_runtime, 'assemble_wav', side_effect=replace_cached_segment):
                with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'artifact changed before assembly'):
                    spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse((run_dir / 'receipt.json').exists())
            self.assertFalse((run_dir / 'COMPRESSED.spoken.wav').exists())


if __name__ == '__main__': unittest.main()
