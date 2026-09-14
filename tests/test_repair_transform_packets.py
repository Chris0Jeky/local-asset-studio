"""Real packet reconstruction and CLI tests with synthetic character pixels."""
import copy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from scripts import character_edit as ed, character_edit_pixels as legacy
from scripts import repair_pixel_transforms as rp, repair_source as rs
from scripts.character_edit_demo import create
from scripts.character_study import file_sha, read_json, sha

ROOT = Path(__file__).resolve().parents[1]


class TransformPackets(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'work'; create(self.root)
        self.plan = read_json(self.root / 'plan.json')
        with Image.open(self.root / 'source.png') as im:
            im.putpixel((0, 0), (123, 45, 67, 0)); im.save(self.root / 'input.png')
        self.source_receipt = rs.capture(self.root / 'input.png', self.root / 'source-packet')
        self.plan['document']['source'] = self.ref('source-packet/normalized.png')
        self.rebuild()
        self.request = {
            'schema': 'studio.repair-transform-request/v1', 'plan_sha256': self.plan['plan_sha256'],
            'source_packet': {'path': 'source-packet',
                'receipt_sha256': file_sha(self.root / 'source-packet/receipt.json'),
                'normalized_sha256': self.plan['document']['source']['sha256']},
            'authored_write': copy.deepcopy(self.plan['intent']['edit_mask']),
            'protection': copy.deepcopy(self.plan['intent']['protect_mask']),
            'transform': {'version': 'straight-rgba-bilinear-v1',
                'box': self.plan['intent']['context_box'][:], 'scale': [1, 2],
                'padding': [1, 2, 3, 4], 'alignment': 1}}

    def ref(self, name): return {'path': name, 'sha256': file_sha(self.root / name)}

    def rebuild(self):
        self.plan['intent']['document_sha256'] = sha(self.plan['document'])
        self.plan = ed.make_plan(self.plan['document'], self.plan['intent'], self.plan['catalog'])

    def prepare(self): return rp.prepare(self.root, self.plan, self.request, 'transformed')

    def candidate(self, receipt):
        Image.new('RGBA', tuple(receipt['geometry']['work_size']), (211, 35, 79, 127)).save(self.root / 'repair.png')
        return self.ref('repair.png')

    def apply(self, candidate, output='composite'):
        return rp.apply(self.root, self.plan, self.request, 'transformed', candidate, output)

    def test_prepare_apply_prove_actual_pixels_and_retain_identity(self):
        before = file_sha(self.root / 'source-packet/normalized.png')
        bundle = self.prepare(); result = self.apply(self.candidate(bundle))
        self.assertEqual('studio.repair-transform-bundle/v1', bundle['schema'])
        self.assertEqual('studio.repair-transform-result/v1', result['schema'])
        self.assertEqual(sha(self.request), bundle['request_sha256'])
        self.assertEqual(self.request, bundle['request'])
        self.assertEqual(self.source_receipt['normalization'], bundle['source_normalization'])
        self.assertGreater(result['changed_pixels'], 0)
        self.assertEqual(0, result['outside_mask_changed_pixels'])
        self.assertEqual(0, result['protected_changed_pixels'])
        self.assertFalse(result['neural_inference']); self.assertFalse(result['semantic_approval'])
        self.assertEqual('unreviewed', result['review_state'])
        with Image.open(self.root / 'source-packet/normalized.png') as original, \
                Image.open(self.root / 'composite/result.png') as actual, \
                Image.open(self.root / 'transformed/effective-write.png') as coverage:
            for y in range(original.height):
                for x in range(original.width):
                    if coverage.getpixel((x, y)) == 0:
                        self.assertEqual(original.getpixel((x, y)), actual.getpixel((x, y)))
            self.assertEqual((123, 45, 67, 0), actual.getpixel((0, 0)))
        self.assertEqual(before, file_sha(self.root / 'source-packet/normalized.png'))

    def test_same_captured_normalized_bytes_supply_the_pixels(self):
        real_load = rs.load_packet
        def captured(folder):
            result = real_load(folder)
            (folder / 'normalized.png').write_bytes(b'subsequent unrelated replacement')
            return result
        with patch.object(rs, 'load_packet', side_effect=captured): bundle = self.prepare()
        self.assertEqual(self.request['source_packet']['normalized_sha256'],
                         bundle['source_normalization']['normalized']['sha256'])
        with Image.open(self.root / 'transformed/context.png') as im:
            self.assertEqual(tuple(bundle['geometry']['work_size']), im.size)

    def test_rehashed_prepared_images_do_not_replace_reconstructed_scope(self):
        bundle = self.prepare(); candidate = self.candidate(bundle)
        for name in ('context.png', 'work-write.png', 'effective-write.png', 'source-protect.png'):
            with self.subTest(name=name):
                path = self.root / 'transformed' / name; old = path.read_bytes()
                receipt_path = self.root / 'transformed/receipt.json'; old_receipt = receipt_path.read_bytes()
                with Image.open(BytesIO(old)) as im:
                    im.putpixel((0, 0), (1, 2, 3, 4) if im.mode == 'RGBA' else 255); im.save(path)
                changed = copy.deepcopy(bundle); changed['files'][name]['sha256'] = file_sha(path)
                changed['files'][name]['bytes'] = path.stat().st_size
                receipt_path.write_text(json.dumps(changed), encoding='utf-8')
                with self.assertRaises(ValueError): self.apply(candidate)
                self.assertFalse((self.root / 'composite').exists())
                path.write_bytes(old); receipt_path.write_bytes(old_receipt)

    def test_bundle_cannot_appoint_another_transform_request(self):
        bundle = self.prepare(); candidate = self.candidate(bundle)
        bundle['request']['transform']['scale'] = [1, 1]
        bundle['request_sha256'] = sha(bundle['request'])
        (self.root / 'transformed/receipt.json').write_text(json.dumps(bundle), encoding='utf-8')
        with self.assertRaises(ValueError): self.apply(candidate)
        self.assertFalse((self.root / 'composite').exists())

    def test_effective_mask_cannot_expand_into_another_actor(self):
        self.plan['intent']['context_box'] = [0, 0, 384, 256]
        self.plan['intent']['protect_mask'] = None
        write = Image.new('L', (384, 256)); write.putpixel((219, 100), 255)
        write.save(self.root / 'edge-write.png'); self.plan['intent']['edit_mask'] = self.ref('edge-write.png')
        self.rebuild(); self.request.update(plan_sha256=self.plan['plan_sha256'],
            authored_write=self.ref('edge-write.png'), protection=None)
        self.request['transform']['box'] = [0, 0, 384, 256]
        with self.assertRaisesRegex(ValueError, 'non-target actor'): self.prepare()
        self.assertFalse((self.root / 'transformed').exists())

    def test_request_source_and_plan_bindings_are_external_and_strict(self):
        for key in ('plan_sha256', 'authored_write', 'transform'):
            with self.subTest(key=key):
                before = copy.deepcopy(self.request)
                if key == 'plan_sha256': self.request[key] = '0' * 64
                elif key == 'authored_write': self.request[key] = self.ref('protect-mask.png')
                else: self.request[key]['box'] = [0, 0, 384, 256]
                with self.assertRaises(ValueError): self.prepare()
                self.request = before
        self.request['source_packet']['receipt_sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.prepare()

    def test_changed_canon_and_mask_are_refused_before_publication(self):
        for name in ('amber-design.json', 'violet-reference.png', 'edit-mask.png'):
            path = self.root / name; old = path.read_bytes(); path.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaises(ValueError): self.prepare()
            path.write_bytes(old)
        self.assertFalse((self.root / 'transformed').exists())

    def test_mask_colour_metadata_and_candidate_metadata_cannot_change_meaning(self):
        with Image.open(self.root / 'edit-mask.png') as im:
            im.save(self.root / 'mask-profile.png', icc_profile=b'ambiguous-mask-profile')
        self.plan['intent']['edit_mask'] = self.ref('mask-profile.png'); self.rebuild()
        self.request.update(plan_sha256=self.plan['plan_sha256'], authored_write=self.ref('mask-profile.png'))
        with self.assertRaises(ValueError): self.prepare()

    def test_candidate_colours_hash_and_canvas_are_checked_from_capture(self):
        bundle = self.prepare(); self.candidate(bundle)
        for change in ('digest', 'icc', 'size', 'mode', 'exif', 'trailing'):
            with self.subTest(change=change):
                candidate = self.candidate(bundle)
                if change == 'digest': candidate['sha256'] = '0' * 64
                elif change == 'trailing':
                    with (self.root / 'repair.png').open('ab') as stream: stream.write(b'trailer')
                    candidate = self.ref('repair.png')
                else:
                    size = (1, 1) if change == 'size' else tuple(bundle['geometry']['work_size'])
                    mode = 'RGB' if change == 'mode' else 'RGBA'
                    options = {'icc_profile': b'different'} if change == 'icc' else {}
                    if change == 'exif':
                        exif = Image.Exif(); exif[274] = 1; options['exif'] = exif
                    Image.new(mode, size).save(self.root / 'repair.png', **options)
                    candidate = self.ref('repair.png')
                with self.assertRaises(ValueError): self.apply(candidate)
                self.assertFalse((self.root / 'composite').exists())

    def test_candidate_capture_is_not_reopened_after_hashing(self):
        bundle = self.prepare(); candidate = self.candidate(bundle)
        real_read = rs.read_bounded
        def captured(path, *args, **kwargs):
            result = real_read(path, *args, **kwargs)
            if path.name == 'repair.png': path.write_bytes(b'later replacement')
            return result
        with patch.object(rs, 'read_bounded', side_effect=captured): result = self.apply(candidate)
        self.assertEqual(candidate['sha256'], result['candidate']['sha256'])
        self.assertGreater(result['changed_pixels'], 0)

    def test_colour_chunks_survive_and_candidate_must_match_exactly(self):
        colour = rs.png_chunk(b'gAMA', (45455).to_bytes(4, 'big'))
        path = self.root / 'input.png'; data = path.read_bytes()
        path.write_bytes(data[:33] + colour + data[33:])
        receipt = rs.capture(path, self.root / 'coloured-source')
        self.plan['document']['source'] = self.ref('coloured-source/normalized.png'); self.rebuild()
        self.request.update(plan_sha256=self.plan['plan_sha256'])
        self.request['source_packet'] = {'path': 'coloured-source',
            'receipt_sha256': file_sha(self.root / 'coloured-source/receipt.json'),
            'normalized_sha256': receipt['normalization']['normalized']['sha256']}
        bundle = self.prepare(); candidate = self.candidate(bundle)
        with self.assertRaisesRegex(ValueError, 'colour'): self.apply(candidate)
        path = self.root / 'repair.png'; data = path.read_bytes()
        path.write_bytes(data[:33] + colour + data[33:]); self.apply(self.ref('repair.png'))
        for name in ('transformed/context.png', 'composite/result.png'):
            chunks = rs.scan_png((self.root / name).read_bytes())
            self.assertEqual([(b'gAMA', (45455).to_bytes(4, 'big'))], [(k,v) for k,v in chunks if k in rs.COLOUR])

    def test_grayscale_scanner_option_does_not_widen_source_intake(self):
        raw = (self.root / 'edit-mask.png').read_bytes()
        with self.assertRaises(ValueError): rs.scan_png(raw)
        with self.assertRaises(ValueError): rs.normalize_repair_png(raw)
        self.assertEqual(b'IHDR', rs.scan_png(raw, grayscale=True)[0][0])

    def test_noop_and_existing_or_partial_outputs_remain_honest(self):
        self.prepare(); result = self.apply(self.ref('transformed/context.png'))
        self.assertEqual(0, result['changed_pixels']); self.assertTrue(result['no_op']); self.assertTrue(result['warnings'])
        original = (self.root / 'composite/receipt.json').read_bytes()
        with self.assertRaises(FileExistsError): self.apply(self.ref('transformed/context.png'))
        self.assertEqual(original, (self.root / 'composite/receipt.json').read_bytes())
        (self.root / 'partial').mkdir(); (self.root / 'partial/receipt.pending').write_bytes(b'preserve')
        with self.assertRaises(FileExistsError): self.apply(self.ref('transformed/context.png'), 'partial')
        self.assertEqual(b'preserve', (self.root / 'partial/receipt.pending').read_bytes())

    def test_extra_packet_members_and_workspace_escape_are_refused(self):
        bundle = self.prepare(); candidate = self.candidate(bundle)
        (self.root / 'transformed/unlisted.png').write_bytes(b'keep this')
        with self.assertRaises(ValueError): self.apply(candidate)
        self.assertEqual(b'keep this', (self.root / 'transformed/unlisted.png').read_bytes())
        with self.assertRaises(ValueError): rp.prepare(self.root, self.plan, self.request, '../outside')

    def test_legacy_bundle_validator_does_not_admit_the_new_schema(self):
        bundle = self.prepare()
        (self.root / 'transformed/bundle.json').write_text(json.dumps(bundle), encoding='utf-8')
        with self.assertRaises(ValueError):
            legacy.render(self.root, self.plan, 'transformed', self.candidate(bundle))

    def test_cli_runs_from_another_directory_with_a_hash_bound_request(self):
        plan_path = self.root / 'new-plan.json'; plan_path.write_text(json.dumps(self.plan), encoding='utf-8')
        request_path = self.root / 'transform.json'; request_path.write_text(json.dumps(self.request), encoding='utf-8')
        common = ['--workspace', str(self.root), '--plan', str(plan_path), '--request', str(request_path),
                  '--request-sha256', file_sha(request_path)]
        def run(command, extra):
            return subprocess.run([sys.executable, str(ROOT / 'scripts/repair_pixel_transforms.py'),
                command, *common, *extra], cwd=self.temp.name, capture_output=True, text=True)
        proc = run('prepare', ['--out', 'transformed'])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        bundle = json.loads(proc.stdout); candidate = self.candidate(bundle)
        proc = run('apply', ['--bundle', 'transformed', '--candidate', candidate['path'],
                            '--candidate-sha256', candidate['sha256'], '--out', 'cli-result'])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertGreater(json.loads(proc.stdout)['changed_pixels'], 0)
        request_path.write_text('{}', encoding='utf-8')
        proc = run('prepare', ['--out', 'stale-request'])
        self.assertEqual(2, proc.returncode); self.assertFalse((self.root / 'stale-request').exists())


if __name__ == '__main__': unittest.main()
