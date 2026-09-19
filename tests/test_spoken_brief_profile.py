import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import spoken_brief
import spoken_brief_runtime
from spoken_brief_fixture import Fixture


class SpokenBriefProfileTests(unittest.TestCase):
    def make_pack(self, root, text='A concise handoff for narration.'):
        pack = Path(root) / 'handoff'
        pack.mkdir()
        (pack / 'COMPRESSED.md').write_text(text, encoding='utf-8')
        return pack

    def test_default_plan_binds_the_kokoro_control_and_delivery(self):
        with tempfile.TemporaryDirectory() as temporary:
            pack = self.make_pack(temporary)
            result = spoken_brief.plan(pack)
            manifest = json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
            binding = manifest['voice_profile']
            self.assertEqual((binding['id'], binding['status'], binding['delivery']['id']),
                             ('kokoro-af-heart-control-v1', 'control', 'calm-brief'))
            self.assertEqual(result['voice_profile'], binding)
            self.assertFalse(result['generation_submitted'])

    def test_profile_delivery_and_speaker_metadata_change_manifest_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            pack = self.make_pack(temporary)
            calm = spoken_brief.plan(pack, delivery_id='calm-brief')
            spark = spoken_brief.plan(pack, delivery_id='spark-recap')
            experimental = spoken_brief.plan(pack, profile_id='ember-brief-v1', delivery_id='calm-brief')
            override = spoken_brief.plan(pack, speaker_id='project-narrator')
            manifests = [json.loads(Path(item['manifest']).read_text(encoding='utf-8'))
                         for item in (calm, spark, experimental, override)]
            self.assertEqual(len({item['manifest_sha256'] for item in manifests}), 4)
            self.assertEqual(experimental['voice_profile']['status'], 'experimental')
            self.assertEqual(override['voice_profile']['speaker_id_source'], 'cli-metadata-override')
            self.assertEqual(override['voice_profile']['speaker_id'], 'project-narrator')

    def test_experimental_run_refuses_before_state_or_network_side_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            pack = self.make_pack(temporary)
            with patch.object(spoken_brief_runtime, 'StudioClient') as client:
                with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'experimental'):
                    spoken_brief.run(pack, profile_id='ember-brief-v1')
            client.assert_not_called()
            self.assertFalse((pack / '_spoken').exists())

    def test_completed_receipt_retains_the_exact_profile_binding(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = self.make_pack(temporary)
            result = spoken_brief.run(
                pack,
                base_url=fixture.base_url,
                delivery_id='dense-technical',
                speaker_id='technical-narrator',
                poll_seconds=0.01,
                deadline_seconds=5,
            )
            receipt = json.loads(Path(result['receipt']).read_text(encoding='utf-8'))
            manifest = json.loads((Path(result['receipt']).parent / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt['voice_profile'], manifest['voice_profile'])
            self.assertEqual(result['voice_profile'], manifest['voice_profile'])
            self.assertEqual(receipt['voice_profile']['delivery']['id'], 'dense-technical')
            self.assertEqual(receipt['voice_profile']['speaker_id_source'], 'cli-metadata-override')

    def test_python_cli_exposes_profile_delivery_and_registry_arguments(self):
        arguments = spoken_brief.parser().parse_args([
            'plan', 'handoff',
            '--profile-id', 'ember-brief-v1',
            '--delivery-id', 'spark-recap',
            '--profile-registry', 'local-profiles.json',
            '--speaker-id', 'preview-narrator',
        ])
        self.assertEqual(arguments.profile_id, 'ember-brief-v1')
        self.assertEqual(arguments.delivery_id, 'spark-recap')
        self.assertEqual(arguments.profile_registry, 'local-profiles.json')
        self.assertEqual(arguments.speaker_id, 'preview-narrator')

    def test_powershell_wrapper_forwards_profile_arguments_without_evaluation(self):
        wrapper = Path(__file__).parents[1] / 'scripts' / 'speak-handoff.ps1'
        text = wrapper.read_text(encoding='utf-8')
        for name in ('$ProfileId', '$DeliveryId', '$ProfileRegistry'):
            self.assertIn(name, text)
        self.assertIn("'--profile-id'", text)
        self.assertIn("'--delivery-id'", text)
        self.assertIn("'--profile-registry'", text)
        self.assertIn('& $python @arguments', text)
        self.assertNotIn('Invoke-Expression', text)


if __name__ == '__main__':
    unittest.main()
