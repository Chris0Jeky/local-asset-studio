import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import voice_profile


HEX_A = 'a' * 64
HEX_B = 'b' * 64
HEX_C = 'c' * 64


def profile_by_id(catalog, identifier):
    return next(item for item in catalog['profiles'] if item['id'] == identifier)


def accepted_ember(base, supersedes):
    value = copy.deepcopy(base)
    value['revision'] = base['revision'] + 1
    value['status'] = 'accepted'
    value['supersedes_profile_sha256'] = supersedes
    value['identity'].update(
        model_id='Qwen/Qwen3-TTS-12Hz-1.7B-Base',
        model_revision='1' * 40,
        voice='ember-brief-reference-v1',
        reference={
            'asset_id': 'asset-ember-brief-reference-v1',
            'sha256': HEX_A,
            'transcript_sha256': HEX_B,
            'permission_scope': 'owner-recorded-original',
        },
    )
    value['producer'] = {
        'adapter': 'qwen3-tts-profile',
        'runnable': True,
        'speaker_id': 'ember-brief',
    }
    for delivery in value['deliveries']:
        delivery['status'] = 'qualified'
    value['acceptance'] = {
        'state': 'accepted',
        'owner_review': 'accepted',
        'qualification_report_sha256': HEX_A,
        'long_form_manifest_sha256': HEX_B,
        'long_form_audio_sha256': HEX_C,
        'accepted_at': '2026-09-19T18:00:00Z',
    }
    return value


class VoiceProfileContractTests(unittest.TestCase):
    def test_checked_in_catalog_exposes_control_and_experimental_profiles(self):
        control = voice_profile.resolve_profile('kokoro-af-heart-control-v1', 'calm-brief')
        self.assertEqual((control['status'], control['adapter'], control['runnable']),
                         ('control', 'voice-baseline', True))
        self.assertEqual(control['speaker_id'], 'brief-narrator')
        self.assertEqual(control['speaker_id_source'], 'profile')
        self.assertEqual(control['delivery']['id'], 'calm-brief')
        self.assertRegex(control['profile_sha256'], r'^[0-9a-f]{64}$')
        voice_profile.require_executable(control)

        experimental = voice_profile.resolve_profile('ember-brief-v1', 'spark-recap')
        self.assertEqual((experimental['status'], experimental['adapter'], experimental['runnable']),
                         ('experimental', 'unbound', False))
        with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'experimental'):
            voice_profile.require_executable(experimental)

    def test_canonical_profile_hash_is_stable_and_delivery_is_separately_bound(self):
        catalog = voice_profile.load_catalog()
        profile = profile_by_id(catalog, 'kokoro-af-heart-control-v1')
        reordered = json.loads(json.dumps(profile, sort_keys=True))
        self.assertEqual(voice_profile.profile_digest(profile), voice_profile.profile_digest(reordered))
        calm = voice_profile.resolve_profile(profile['id'], 'calm-brief')
        spark = voice_profile.resolve_profile(profile['id'], 'spark-recap')
        self.assertEqual(calm['profile_sha256'], spark['profile_sha256'])
        self.assertNotEqual(calm['binding_sha256'], spark['binding_sha256'])
        self.assertNotEqual(calm['delivery']['sha256'], spark['delivery']['sha256'])

    def test_redundant_default_speaker_does_not_fork_manifest_identity(self):
        default = voice_profile.resolve_profile('kokoro-af-heart-control-v1', 'calm-brief')
        explicit = voice_profile.resolve_profile(
            'kokoro-af-heart-control-v1', 'calm-brief', speaker_id='brief-narrator')
        self.assertEqual(explicit['speaker_id_source'], 'profile')
        self.assertEqual(default, explicit)

    def test_speaker_override_is_metadata_only_and_changes_binding_identity(self):
        default = voice_profile.resolve_profile('kokoro-af-heart-control-v1', 'calm-brief')
        override = voice_profile.resolve_profile(
            'kokoro-af-heart-control-v1', 'calm-brief', speaker_id='project-narrator')
        self.assertEqual(override['speaker_id'], 'project-narrator')
        self.assertEqual(override['speaker_id_source'], 'cli-metadata-override')
        self.assertEqual(default['profile_sha256'], override['profile_sha256'])
        self.assertNotEqual(default['binding_sha256'], override['binding_sha256'])

    def test_local_overlay_requires_exact_catalogue_provenance(self):
        catalog = voice_profile.load_catalog()
        base = profile_by_id(catalog, 'ember-brief-v1')
        base_hash = voice_profile.profile_digest(base)
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / 'profiles.json'
            replacement = accepted_ember(base, '0' * 64)
            registry.write_text(json.dumps({'schema_version': 1, 'profiles': [replacement]}), encoding='utf-8')
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'supersedes'):
                voice_profile.resolve_profile('ember-brief-v1', 'calm-brief', registry_path=registry)

            replacement['supersedes_profile_sha256'] = base_hash
            registry.write_text(json.dumps({'schema_version': 1, 'profiles': [replacement]}), encoding='utf-8')
            resolved = voice_profile.resolve_profile('ember-brief-v1', 'calm-brief', registry_path=registry)
            self.assertEqual((resolved['revision'], resolved['status'], resolved['runnable']),
                             (base['revision'] + 1, 'accepted', True))
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'unsupported adapter'):
                voice_profile.require_executable(resolved)

            successor = copy.deepcopy(replacement)
            successor['revision'] += 1
            successor['supersedes_profile_sha256'] = voice_profile.profile_digest(replacement)
            registry.write_text(json.dumps({'schema_version': 1, 'profiles': [successor]}), encoding='utf-8')
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'supersedes'):
                voice_profile.resolve_profile('ember-brief-v1', 'calm-brief', registry_path=registry)

            successor['supersedes_profile_sha256'] = base_hash
            registry.write_text(json.dumps({'schema_version': 1, 'profiles': [successor]}), encoding='utf-8')
            resolved = voice_profile.resolve_profile('ember-brief-v1', 'calm-brief', registry_path=registry)
            self.assertEqual(resolved['revision'], base['revision'] + 2)

    def test_current_voice_baseline_cannot_masquerade_as_an_accepted_custom_profile(self):
        catalog = voice_profile.load_catalog()
        base = profile_by_id(catalog, 'ember-brief-v1')
        replacement = accepted_ember(base, voice_profile.profile_digest(base))
        replacement['producer']['adapter'] = 'voice-baseline'
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / 'profiles.json'
            registry.write_text(json.dumps({'schema_version': 1, 'profiles': [replacement]}), encoding='utf-8')
            resolved = voice_profile.resolve_profile('ember-brief-v1', 'calm-brief', registry_path=registry)
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'Kokoro af_heart control'):
                voice_profile.require_executable(resolved)

    def test_duplicate_local_identity_without_supersedes_is_rejected(self):
        catalog = voice_profile.load_catalog()
        duplicate = copy.deepcopy(profile_by_id(catalog, 'kokoro-af-heart-control-v1'))
        duplicate['revision'] += 1
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / 'profiles.json'
            registry.write_text(json.dumps({'schema_version': 1, 'profiles': [duplicate]}), encoding='utf-8')
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'supersedes'):
                voice_profile.resolve_profile(duplicate['id'], 'calm-brief', registry_path=registry)

    def test_profile_inputs_are_bounded_and_reject_path_like_reference_assets(self):
        catalog = voice_profile.load_catalog()
        base = profile_by_id(catalog, 'ember-brief-v1')
        replacement = accepted_ember(base, voice_profile.profile_digest(base))
        replacement['identity']['reference']['asset_id'] = r'C:\secret\voice.wav'
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / 'profiles.json'
            registry.write_text(json.dumps({'schema_version': 1, 'profiles': [replacement]}), encoding='utf-8')
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'asset'):
                voice_profile.load_registry(registry, voice_profile.load_catalog())

            oversized = Path(temporary) / 'oversized.json'
            oversized.write_bytes(b' ' * (voice_profile.MAX_PROFILE_JSON_BYTES + 1))
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'byte'):
                voice_profile.load_catalog(oversized)

    def test_unknown_fields_and_delivery_ids_are_rejected(self):
        catalog = voice_profile.load_catalog()
        catalog['profiles'][0]['unexpected'] = True
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'catalog.json'
            path.write_text(json.dumps(catalog), encoding='utf-8')
            with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'fields'):
                voice_profile.load_catalog(path)
        with self.assertRaisesRegex(voice_profile.VoiceProfileError, 'delivery'):
            voice_profile.resolve_profile('kokoro-af-heart-control-v1', 'missing-delivery')


if __name__ == '__main__':
    unittest.main()
