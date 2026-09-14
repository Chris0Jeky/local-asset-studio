"""Actual existing-plan -> prepared-packet -> scope-handoff integration.

The partial development checkout cannot import the full character-edit fixture;
normal hosted repository CI must run every case without this environment skip.
"""
import copy
from io import BytesIO
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import repair_scope_review as review


@unittest.skipUnless((ROOT/'scripts/character_edit_demo.py').is_file(), 'full character-edit fixture unavailable in partial checkout')
class ScopePacketTests(unittest.TestCase):
    def setUp(self):
        from test_repair_transform_packets import TransformPackets
        from scripts import repair_pixel_transforms as rp, repair_source as rs
        from scripts.character_study import file_sha
        self.rp, self.rs, self.file_sha = rp, rs, file_sha
        self.fixture = TransformPackets(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root, self.plan, self.request = self.fixture.root, self.fixture.plan, self.fixture.request
        self.bundle = self.fixture.prepare()

    def preview(self, out='scope-review'):
        return review.create_review(self.root, self.plan, self.request, 'transformed', out)

    def verify(self, out='scope-review'):
        return review.verify_review(self.root, self.plan, self.request, 'transformed', out)

    def test_public_read_only_verifier_reuses_external_transform_contract(self):
        artifacts, receipt, inputs, raw = self.rp.verify_prepared(self.root, self.plan, self.request, 'transformed')
        self.assertEqual(receipt, self.bundle)
        self.assertEqual(raw, (self.root/'transformed/receipt.json').read_bytes())
        self.assertEqual(artifacts['context.png'], (self.root/'transformed/context.png').read_bytes())
        self.assertEqual(inputs[0].mode, 'RGBA')
        self.assertFalse((self.root/'scope-review').exists())

    def test_complete_handoff_verifies_and_exports_exact_sampler_alpha(self):
        report = self.preview()
        self.assertEqual(self.verify(), report)
        self.assertEqual(report['schema'], review.SCHEMA)
        self.assertEqual(report['expected_effective_write_sha256'], self.fixture.expected_effective)
        self.assertFalse(report['semantic_approval']); self.assertFalse(report['neural_inference'])
        self.assertEqual(report['review_state'], 'unreviewed')
        with Image.open(self.root/'scope-review/comfy-mask.png') as exported, Image.open(self.root/'transformed/work-write.png') as work:
            self.assertEqual(ImageChops.invert(exported.getchannel('A')).tobytes(), work.tobytes())
            self.assertEqual(exported.getpixel((0, 0)), (0, 0, 0, 255))
        for name in self.rp.PREPARED_FILES.values():
            self.assertEqual((self.root/'scope-review'/name).read_bytes(), (self.root/'transformed'/name).read_bytes())

    def test_preview_does_not_mutate_source_bundle_or_external_inputs(self):
        original_plan, original_request = copy.deepcopy(self.plan), copy.deepcopy(self.request)
        before = {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.object(socket, 'socket', side_effect=AssertionError('network request')):
            self.preview(); self.verify()
        for name, raw in before.items(): self.assertEqual((self.root/name).read_bytes(), raw)
        self.assertEqual(self.plan, original_plan); self.assertEqual(self.request, original_request)

    def test_stale_source_and_reference_refused_without_output(self):
        for name in ('source-packet/normalized.png', 'violet-reference.png'):
            path = self.root/name; original = path.read_bytes(); path.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaises(ValueError): self.preview()
            self.assertFalse((self.root/'scope-review').exists()); path.write_bytes(original)

    def test_changed_prepared_packet_cannot_supply_its_own_authority(self):
        for name in ('work-write.png', 'effective-write.png', 'context.png'):
            path = self.root/'transformed'/name; old = path.read_bytes()
            with Image.open(BytesIO(old)) as im:
                im.putpixel((0, 0), (1, 2, 3, 4) if im.mode == 'RGBA' else 255); im.save(path)
            with self.subTest(name=name), self.assertRaises(ValueError): self.preview()
            self.assertFalse((self.root/'scope-review').exists()); path.write_bytes(old)

    def test_new_scale_request_does_not_reinterpret_old_bundle(self):
        self.request['transform']['scale'] = [1, 1]
        with self.assertRaises(ValueError): self.preview()
        self.assertFalse((self.root/'scope-review').exists())

    def test_rehashed_exported_mask_is_rejected_by_reconstruction(self):
        report = self.preview(); name = 'comfy-mask.png'; path = self.root/'scope-review'/name
        with Image.open(path) as im: im.putpixel((0,0),(0,0,0,0)); im.save(path)
        report['files'][name]['sha256'] = self.file_sha(path); report['files'][name]['bytes'] = path.stat().st_size
        (self.root/'scope-review/receipt.json').write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaises(ValueError): self.verify()

    def test_extra_member_and_symlink_refused_without_deletion(self):
        self.preview(); extra = self.root/'scope-review/extra'; extra.write_text('retain me')
        with self.assertRaises(ValueError): self.verify()
        self.assertEqual(extra.read_text(), 'retain me'); extra.unlink()
        mask = self.root/'scope-review/comfy-mask.png'; raw = mask.read_bytes(); mask.unlink()
        external = self.root/'other-mask.png'; external.write_bytes(raw)
        try: mask.symlink_to(external)
        except OSError: self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError): self.verify()

    def test_reconstruction_cannot_grant_approval_by_changing_receipt(self):
        report = self.preview(); report['semantic_approval'] = True
        (self.root/'scope-review/receipt.json').write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaises(ValueError): self.verify()

    def test_known_destination_and_workspace_escape_refused(self):
        self.preview(); before = (self.root/'scope-review/receipt.json').read_bytes()
        with self.assertRaises((OSError,ValueError)): self.preview()
        self.assertEqual(before, (self.root/'scope-review/receipt.json').read_bytes())
        with self.assertRaises(ValueError): self.preview('../escape')

    def test_post_verify_replacement_is_not_read_into_review(self):
        real = self.rp.verify_prepared
        def replace_after_capture(*args, **kwargs):
            result = real(*args, **kwargs)
            (self.root/'transformed/work-write.png').write_bytes(b'replaced later')
            return result
        expected = (self.root/'transformed/work-write.png').read_bytes()
        with patch.object(self.rp, 'verify_prepared', side_effect=replace_after_capture): self.preview()
        self.assertEqual((self.root/'scope-review/work-write.png').read_bytes(), expected)
        with self.assertRaises(ValueError): self.verify()

    def test_aggregate_output_limit_prevents_partial_publication(self):
        with patch.object(self.rs, 'MAX_OUTPUT_BYTES', 100):
            with self.assertRaises(ValueError): self.preview()
        self.assertFalse((self.root/'scope-review').exists())

    def test_complete_existing_demo_can_be_reviewed_and_reverified(self):
        from scripts.repair_scope_demo import create
        destination = self.root.parent/'scope-demo'
        proof = create(destination)
        self.assertTrue(proof['scope_packet_verified'])
        self.assertEqual(proof['review_state'], 'unreviewed')
        self.assertFalse(proof['neural_inference']); self.assertFalse(proof['semantic_approval'])
        self.assertTrue((destination/'scope-review/scope-review.html').is_file())

    def test_cli_preview_verify_and_stale_request_pin(self):
        plan = self.root/'scope-plan.json'; request = self.root/'scope-request.json'
        plan.write_text(json.dumps(self.plan), encoding='utf-8'); request.write_text(json.dumps(self.request), encoding='utf-8')
        arguments = ['--workspace', str(self.root), '--plan', str(plan), '--request', str(request),
                     '--request-sha256', self.file_sha(request), '--bundle', 'transformed']
        for command in [['preview', '--out', 'cli-review'], ['verify', '--review', 'cli-review']]:
            run = subprocess.run([sys.executable, str(ROOT/'scripts/repair_scope_review.py'), *command, *arguments],
                                 cwd=self.root, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            self.assertFalse(json.loads(run.stdout)['semantic_approval'])
        request.write_text(request.read_text()+'\n', encoding='utf-8')
        run = subprocess.run([sys.executable, str(ROOT/'scripts/repair_scope_review.py'), 'preview', '--out', 'stale', *arguments],
                             cwd=self.root, text=True, capture_output=True)
        self.assertEqual(run.returncode, 2, run.stderr + run.stdout)
        self.assertIn('error', json.loads(run.stdout)); self.assertFalse((self.root/'stale').exists())

if __name__ == '__main__': unittest.main()
