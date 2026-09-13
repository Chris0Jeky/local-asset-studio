"""Intake preserves unknown files; role hints never certify identity or compatibility."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/intake-downloads.py'
spec = importlib.util.spec_from_file_location('intake_unknown_fixture', SCRIPT)
intake = importlib.util.module_from_spec(spec); spec.loader.exec_module(intake)
import model_intake

BACKBONE = {'blocks.0.attn.wk.weight': {}, 'img_in.weight': {}, 'final_layer.linear.weight': {}}
LORA = {'lora_unet_input_blocks_4_1_proj_in.lora_down.weight': {}}
UNKNOWN = {'unrecognised.component.weight': {}}


class UnknownIntakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.source = self.root/'downloads'; self.source.mkdir()
        self.comfy = self.root/'comfy'
        reserve = patch.object(model_intake, 'RESERVE_BYTES', 0); reserve.start(); self.addCleanup(reserve.stop)

    def write(self, name, header):
        body = json.dumps(header).encode('utf-8')
        path = self.source/name; path.write_bytes(len(body).to_bytes(8, 'little') + body + bytes(8))
        return path

    def run_cli(self, *args):
        output = io.StringIO()
        with patch.object(intake, 'ROOT', self.root), \
             patch.object(intake, 'load_config', return_value={'comfy_root': str(self.comfy)}), redirect_stdout(output):
            result = intake.main(['--from', str(self.source), *args])
        self.assertEqual(result, 0)
        return output.getvalue()

    def receipts(self):
        return [json.loads(p.read_text()) for p in (self.root/'.runtime/downloads/intake').glob('*.json')]

    def test_unknown_headers_have_no_default_folder(self):
        for header in ({}, UNKNOWN, {'__metadata__': {'modelspec.title': 'Diffusion model'}}):
            with self.subTest(header=header):self.assertIsNone(intake.classify(header))

    def test_incomplete_backbone_signature_stays_unknown(self):
        for missing in BACKBONE:
            with self.subTest(missing=missing):
                self.assertIsNone(intake.classify({key: value for key, value in BACKBONE.items() if key != missing}))

    def test_known_backbone_and_loader_prefixes_remain_hints(self):
        for prefix in ('', 'diffusion_model.', 'model.diffusion_model.'):
            with self.subTest(prefix=prefix):
                self.assertEqual(intake.classify({prefix+key: value for key, value in BACKBONE.items()}), 'diffusion_models')

    def test_lora_evidence_still_wins_over_backbone_keys(self):
        self.assertEqual(intake.classify({**BACKBONE, **LORA}), 'loras')

    def test_existing_component_roles_remain_supported(self):
        for header, folder in (({'decoder.conv_in.weight': {}, 'encoder.conv_in.weight': {}}, 'vae'),
                               ({'model.embed_tokens.weight': {}}, 'text_encoders'),
                               ({'first_stage_model.decoder.weight': {}, 'conditioner.text_model.weight': {}}, 'checkpoints')):
            with self.subTest(folder=folder):self.assertEqual(intake.classify(header), folder)

    def test_plan_explains_unknown_without_writing_or_guessing_from_filename(self):
        path = self.write('minimax_h3_fl2va_pruned_int8_convrot.safetensors', UNKNOWN)
        before = path.read_bytes(); item = intake.plan([path])[0]
        self.assertIsNone(item['folder']); self.assertEqual(item['folder_basis'], 'unknown')
        self.assertIn('Unknown model role', item['error']); self.assertIn('--dest-folder', item['error'])
        self.assertEqual(path.read_bytes(), before); self.assertFalse(self.comfy.exists())

    def test_renaming_cannot_change_an_unknown_role(self):
        first = self.write('unknown.safetensors', UNKNOWN)
        second = self.write('SDXL_LoRA_vae_checkpoint.safetensors', UNKNOWN)
        a, b = intake.plan([first, second])
        self.assertEqual((a['folder'], a['error']), (b['folder'], b['error']))
        self.assertIsNone(a['folder']); self.assertIsNotNone(a['error'])

    def test_cli_unknown_preserves_file_without_copy_or_receipt(self):
        path = self.write('unknown.safetensors', UNKNOWN); before = path.read_bytes()
        with patch.object(intake, 'import_candidate') as publish:
            output = self.run_cli()
        publish.assert_not_called()
        self.assertIn('SKIP unknown.safetensors', output); self.assertIn('Unknown model role', output)
        self.assertEqual(path.read_bytes(), before); self.assertFalse(self.comfy.exists())
        self.assertFalse((self.root/'.runtime').exists())

    def test_dry_run_preserves_known_and_unknown_files(self):
        known = self.write('known.safetensors', LORA); unknown = self.write('unknown.safetensors', UNKNOWN)
        with patch.object(intake, 'import_candidate') as publish:
            output = self.run_cli('--dry-run')
        publish.assert_not_called()
        self.assertTrue(known.exists()); self.assertTrue(unknown.exists()); self.assertFalse(self.comfy.exists())
        self.assertIn('Unknown model role', output); self.assertIn('header-hint', output)

    def test_explicit_folder_is_operator_choice_not_model_identification(self):
        path = self.write('unknown.safetensors', UNKNOWN); original = path.read_bytes()
        output = self.run_cli('--dest-folder', 'loras')
        target = self.comfy/'models/loras/unknown.safetensors'
        self.assertEqual(target.read_bytes(), original); self.assertEqual(path.read_bytes(), original)
        records = self.receipts()
        self.assertEqual(records[0]['folder_basis'], 'operator-selected')
        self.assertIs(records[0]['verified'], False); self.assertIsNone(records[0]['runtime_compatible'])
        self.assertIsNone(records[0]['expected_sha256']); self.assertEqual(records[0]['sha256'], hashlib.sha256(original).hexdigest())
        self.assertIn('operator-selected', output); self.assertIn('unverified', output)

    def test_explicit_override_preserves_existing_header_bypass_contract(self):
        path = self.source/'operator-reviewed.safetensors'; path.write_bytes(b'unreadable fixture')
        with patch.object(intake, 'read_header', side_effect=AssertionError('explicit override must not guess a header')):
            item = intake.plan([path], 'diffusion_models')[0]
        self.assertEqual(item['folder'], 'diffusion_models'); self.assertIsNone(item['error'])
        self.assertEqual(item['folder_basis'], 'operator-selected')

    def test_mixed_batch_copies_only_known_candidate_and_retains_both_originals(self):
        known = self.write('known.safetensors', LORA); unknown = self.write('unknown.safetensors', UNKNOWN)
        output = self.run_cli()
        self.assertTrue(known.exists()); self.assertTrue(unknown.exists())
        self.assertTrue((self.comfy/'models/loras/known.safetensors').exists())
        self.assertFalse((self.comfy/'models/diffusion_models/unknown.safetensors').exists())
        records = self.receipts()
        self.assertEqual(len(records), 1); self.assertEqual(records[0]['folder_basis'], 'header-hint')
        self.assertIs(records[0]['verified'], False); self.assertIsNone(records[0]['runtime_compatible'])
        self.assertIn('1 copied', output)

    def test_existing_destination_is_never_replaced_by_override(self):
        path = self.write('unknown.safetensors', UNKNOWN)
        target = self.comfy/'models/loras/unknown.safetensors'; target.parent.mkdir(parents=True); target.write_bytes(b'keep')
        output = self.run_cli('--dest-folder', 'loras')
        self.assertTrue(path.exists()); self.assertEqual(target.read_bytes(), b'keep')
        self.assertFalse((self.root/'.runtime').exists()); self.assertIn('nothing was overwritten', output)

    def test_unreadable_header_has_no_role(self):
        path = self.source/'bad.safetensors'; path.write_bytes(b'bad')
        item = intake.plan([path])[0]
        self.assertIsNone(item['folder']); self.assertEqual(item['folder_basis'], 'unreadable-header')
        self.assertIn('header length', item['error'])

    def test_folder_hint_does_not_invent_family_or_source(self):
        item = intake.plan([self.write('wrong_family_SDXL.safetensors', LORA)])[0]
        entry = intake.stub(item['folder'], 'wrong_family_SDXL.safetensors', 42, 'a'*64)
        self.assertEqual(item['folder_basis'], 'header-hint'); self.assertEqual(item['folder'], 'loras')
        for key in ('family', 'source', 'url', 'license'):self.assertEqual(entry[key], '')
        self.assertIn('TODO', entry['terms'])


if __name__ == '__main__':unittest.main()
