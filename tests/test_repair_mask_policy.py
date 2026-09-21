"""Versioned mask processing through the real raster, packet and CLI owners."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageChops
from scripts import character_edit as ce, repair_pixel_transforms as rp, repair_source as rs
from scripts.character_study import sha

ROOT = Path(__file__).resolve().parents[1]


def spec(size=(32, 32), **changes):
    value = {'version': 'straight-rgba-bilinear-v2', 'box': [0, 0, *size],
             'scale': [1, 1], 'padding': [1, 2, 3, 4], 'alignment': 1,
             'coverage': {'dilate_px': 1, 'feather_px': 1}}
    value.update(changes)
    return value


def pixels(size=(32, 32)):
    image = Image.new('RGBA', size)
    image.putdata([((x * 37 + y) % 256, (y * 13 + x) % 256,
                    (x * 17 + y * 29) % 256, (0, 1, 127, 255)[(x+y) % 4])
                   for y in range(size[1]) for x in range(size[0])])
    write = Image.new('L', size)
    write.paste(255, (12, 12, 16, 16))
    return image, write, Image.new('L', size)


def candidate_for(prepared):
    images = prepared['images']
    candidate = images['context'].copy()
    support = images['work_write'].point(lambda x: 255 if x else 0)
    candidate.paste((251, 239, 227, 199), (0, 0, *candidate.size), support)
    return candidate


def mask_oracle(mask, dilation, feather):
    # Scalar independent oracle: zero-extended square max, then separable integer
    # box averaging with nearest-integer rounding at each pass, as declared.
    width, height = mask.size
    radius = dilation + feather
    values = [[mask.getpixel((x, y)) if 0 <= x < width and 0 <= y < height else 0
               for x in range(-radius, width+radius)]
              for y in range(-radius, height+radius)]
    w, h = width + 2*radius, height + 2*radius
    def at(a, x, y): return a[y][x] if 0 <= x < w and 0 <= y < h else 0
    if dilation:
        values = [[max(at(values, x+dx, y+dy)
                       for dy in range(-dilation, dilation+1)
                       for dx in range(-dilation, dilation+1))
                   for x in range(w)] for y in range(h)]
    if feather:
        size = 2*feather + 1
        values = [[(sum(at(values, x+dx, y) for dx in range(-feather, feather+1)) + feather)//size
                   for x in range(w)] for y in range(h)]
        values = [[(sum(at(values, x, y+dy) for dy in range(-feather, feather+1)) + feather)//size
                   for x in range(w)] for y in range(h)]
    return bytes(values[y+radius][x+radius] for y in range(height) for x in range(width))


class MaskPolicy(unittest.TestCase):
    def test_square_dilation_then_finite_feather_matches_independent_oracle(self):
        image = Image.new('RGBA', (17, 15), (1, 2, 3, 0))
        for location in ((0, 0), (8, 7), (16, 14)):
            for dilation, feather in ((0, 0), (1, 0), (0, 1), (2, 2), (1, 3)):
                with self.subTest(location=location, dilation=dilation, feather=feather):
                    write = Image.new('L', image.size); write.putpixel(location, 233)
                    before = write.tobytes()
                    prepared = rp.prepare_pixels(image, write, Image.new('L', image.size),
                        spec(image.size, coverage={'dilate_px': dilation, 'feather_px': feather}))
                    self.assertEqual(mask_oracle(write, dilation, feather),
                                     prepared['images']['processed_write'].tobytes())
                    self.assertEqual(before, write.tobytes())

    def test_final_support_and_all_channels_are_preserved_across_scale_matrix(self):
        image, write, protect = pixels(); protect.putpixel((31, 31), 255)
        before = [i.tobytes() for i in (image, write, protect)]
        for scale in ([1, 4], [2, 3], [1, 1], [3, 2], [4, 1]):
            with self.subTest(scale=scale):
                request = spec(scale=scale)
                prepared = rp.prepare_pixels(image, write, protect, request)
                result = rp.render_pixels(image, write, protect, request, candidate_for(prepared))
                self.assertGreater(result['delta'].histogram()[255], 0)
                self.assertEqual(0, result['outside_changes'])
                self.assertEqual(0, result['protected_changes'])
                for x, y in ((x, y) for y in range(32) for x in range(32)):
                    if not result['effective_write'].getpixel((x, y)):
                        self.assertEqual(image.getpixel((x, y)), result['result'].getpixel((x, y)))
                self.assertTrue(any(a == 0 and b > 0 for a, b in
                    zip(write.tobytes(), result['effective_write'].tobytes())))
        self.assertEqual(before, [i.tobytes() for i in (image, write, protect)])

    def test_context_guard_detects_shift_padding_hidden_rgb_and_alpha_changes(self):
        image, write, protect = pixels(); request = spec()
        prepared = rp.prepare_pixels(image, write, protect, request)
        context = prepared['images']['context']
        candidates = [ImageChops.offset(context, 1, 0)]
        for channel in range(4):
            candidate = candidate_for(prepared)
            value = list(candidate.getpixel((0, 0))); value[channel] = 19
            candidate.putpixel((0, 0), tuple(value)); candidates.append(candidate)
        candidate = candidate_for(prepared)
        value = list(candidate.getpixel((1, 2))); value[0] ^= 1
        candidate.putpixel((1, 2), tuple(value)); candidates.append(candidate)
        for candidate in candidates:
            with self.subTest(), self.assertRaisesRegex(ValueError, 'context'):
                rp.render_pixels(image, write, protect, request, candidate)

    def test_noop_remains_exact_and_receipt_does_not_claim_interior_registration(self):
        image, write, protect = pixels(); request = spec(scale=[2, 3])
        prepared = rp.prepare_pixels(image, write, protect, request)
        result = rp.render_pixels(image, write, protect, request, prepared['images']['context'])
        self.assertEqual(image.tobytes(), result['result'].tobytes())
        self.assertTrue(result['no_op'])
        self.assertGreater(result['candidate_context']['interior_anchor_pixels'], 0)
        self.assertEqual(0, result['candidate_context']['changed_anchor_pixels'])
        self.assertFalse(result['candidate_context']['interior_registration_proven'])

    def test_empty_anchors_expanded_protection_and_crop_escapes_are_refused(self):
        image, write, protect = pixels()
        with self.assertRaisesRegex(ValueError, 'context'):
            rp.prepare_pixels(image, write, protect, spec(box=[12, 12, 16, 16]))
        protect.putpixel((10, 12), 255)
        with self.assertRaisesRegex(ValueError, '[Pp]rotect'):
            rp.prepare_pixels(image, write, protect, spec())
        protect.putpixel((10, 12), 0)
        with self.assertRaisesRegex(ValueError, 'anchor'):
            rp.prepare_pixels(image, write, protect, spec(box=[12, 12, 16, 16],
                             coverage={'dilate_px': 0, 'feather_px': 0}))

    def test_explicit_bounded_policy_is_required_and_legacy_never_accepts_it(self):
        for policy in (None, {}, {'dilate_px': 0}, {'dilate_px': 0, 'feather_px': 0, 'extra': 0},
                       {'dilate_px': True, 'feather_px': 0}, {'dilate_px': 0, 'feather_px': 1.0},
                       {'dilate_px': -1, 'feather_px': 0}, {'dilate_px': 9, 'feather_px': 0},
                       {'dilate_px': 0, 'feather_px': 17}):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                rp.compile_transform([32, 32], spec(coverage=policy))
        with self.assertRaises(ValueError):
            rp.compile_transform([32, 32], spec(version='straight-rgba-bilinear-v1'))
        with self.assertRaisesRegex(ValueError, 'pixel limit'):
            rp.compile_transform([1, 24_000_000], spec((1, 24_000_000), padding=[0]*4))


def fixture(root, *, trns=False):
    image, write, protect = pixels()
    if trns:
        image = image.convert('RGB'); image.info['transparency'] = image.getpixel((0, 0))
    image.save(root/'source.png'); write.save(root/'write.png'); protect.save(root/'protect.png')
    (root/'canon.json').write_text('{}', encoding='utf-8')
    rs.capture(root/'source.png', root/'source-packet')
    def artifact(name): return {'path': name, 'sha256': rs.digest((root/name).read_bytes())}
    doc = {'schema_version': 1, 'kind': 'character_edit_document', 'id': 'test-doc', 'revision': 1,
        'canvas': [32, 32], 'source': artifact('source-packet/normalized.png'),
        'actors': [{'id': 'test-actor', 'canon': artifact('canon.json'), 'bounds': [0, 0, 32, 32],
                    'references': [{'id': 'test-ref', 'role': 'identity', 'image': artifact('source.png'),
                                    'take': ['identity'], 'ignore': []}]}],
        'scene': {'description': 'test', 'camera': 'test', 'lighting': 'test'}, 'relations': []}
    intent = {'schema_version': 1, 'kind': 'character_edit_intent', 'id': 'test-intent',
        'document_sha256': sha(doc), 'operation': 'local-repaint',
        'changes': [{'actor': 'test-actor', 'facet': 'appearance', 'instruction': 'test only'}],
        'scene_change': None, 'context_box': [0, 0, 32, 32], 'edit_mask': artifact('write.png'),
        'protect_mask': artifact('protect.png'), 'patch_alignment': 1, 'layout': None,
        'budget': {'owner': 'test-budget', 'max_candidates': 1, 'max_repairs': 0},
        'policy_preference': {'local_only': True, 'exclude_known_filters': True,
                             'exclude_documented_weight_restrictions': True, 'unknown_policy': 'exclude'}}
    catalog = {'schema_version': 1, 'kind': 'character_edit_routes', 'as_of': '2026-09-19',
        'routes': [{'id': 'test-route', 'title': 'Offline fixture', 'operations': ['local-repaint'],
            'execution': 'local', 'status': 'implemented_offline', 'preset_ids': [],
            'content_policy': {'input_filter': 'none_in_adapter', 'output_filter': 'none_in_adapter',
                              'learned_restrictions': 'not_applicable', 'upstream_filters': 'not_applicable',
                              'evidence_scope': 'this_adapter_code', 'note': 'Synthetic nonexecuting fixture'},
            'capabilities': ['composite'], 'sources': ['test'], 'limitations': ['no inference']}]}
    plan = ce.make_plan(doc, intent, catalog)
    request = {'schema': rp.REQUEST_SCHEMA, 'plan_sha256': plan['plan_sha256'],
        'source_packet': {'path': 'source-packet', 'receipt_sha256': artifact('source-packet/receipt.json')['sha256'],
                          'normalized_sha256': doc['source']['sha256']},
        'authored_write': intent['edit_mask'], 'protection': intent['protect_mask'], 'transform': spec()}
    return plan, request


class PacketPolicy(unittest.TestCase):
    def test_real_prepare_apply_reconstructs_extra_mask_and_normalizes_trns(self):
        for trns in (False, True):
            with self.subTest(trns=trns), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); plan, request = fixture(root, trns=trns)
                receipt = rp.prepare(root, plan, request, 'prepared')
                self.assertIn('processed-write.png', receipt['files'])
                with Image.open(root/'prepared/context.png') as context:
                    candidate = context.copy()
                with Image.open(root/'prepared/work-write.png') as mask:
                    candidate.paste((251, 239, 227, 199), (0, 0, *candidate.size), mask.point(lambda x: 255 if x else 0))
                candidate.save(root/'candidate.png')
                record = {'path': 'candidate.png', 'sha256': rs.digest((root/'candidate.png').read_bytes())}
                pin = receipt['files']['effective-write.png']['sha256']
                result = rp.apply(root, plan, request, 'prepared', record, 'result',
                                  expected_effective_write_sha256=pin)
                self.assertEqual(0, result['outside_mask_changed_pixels'])
                self.assertFalse(result['candidate_context']['interior_registration_proven'])
                self.assertEqual(0, result['candidate_context']['changed_anchor_pixels'])
                with self.assertRaises(ValueError):
                    rp.apply(root, plan, request, 'prepared', record, 'wrong-pin', expected_effective_write_sha256='0'*64)
                self.assertFalse((root/'wrong-pin').exists())
                altered = copy.deepcopy(request); altered['transform']['coverage']['dilate_px'] = 0
                with self.assertRaises(ValueError):
                    rp.apply(root, plan, altered, 'prepared', record, 'stale-policy', expected_effective_write_sha256=pin)
                self.assertFalse((root/'stale-policy').exists())
                (root/'source-packet/normalized.png').write_bytes(b'stale source')
                with self.assertRaises(ValueError):
                    rp.apply(root, plan, request, 'prepared', record, 'stale-source', expected_effective_write_sha256=pin)
                self.assertFalse((root/'stale-source').exists())

    def test_review_retains_processed_mask_and_discloses_expansion_before_pin(self):
        from scripts import repair_scope_review as review
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, request = fixture(root)
            prepared = rp.prepare(root, plan, request, 'prepared')
            report = review.create_review(root, plan, request, 'prepared', 'review')
            self.assertEqual(report, review.verify_review(root, plan, request, 'prepared', 'review'))
            self.assertEqual(prepared['files']['effective-write.png']['sha256'],
                             report['expected_effective_write_sha256'])
            self.assertIn('processed-write.png', report['files'])
            self.assertEqual(1, report['scope']['coverage_policy']['dilate_px'])
            html = (root/'review/scope-review.html').read_text(encoding='utf-8')
            self.assertIn('mask processing and resampling', html)
            self.assertIn('Dilation: 1 source pixels; feather: 1 source pixels.', html)
            with Image.open(root/'review/comfy-mask.png') as carrier, Image.open(root/'review/work-write.png') as mask:
                self.assertEqual(bytes(255-v for v in mask.tobytes()), carrier.getchannel('A').tobytes())
            (root/'review/processed-write.png').write_bytes(b'tampered')
            with self.assertRaises(ValueError): review.verify_review(root, plan, request, 'prepared', 'review')

    def test_actual_cli_prepare_apply_and_refusal_never_publishes_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan, request = fixture(root)
            (root/'plan.json').write_text(json.dumps(plan), encoding='utf-8')
            (root/'request.json').write_text(json.dumps(request), encoding='utf-8')
            args = ['--workspace', str(root), '--plan', str(root/'plan.json'), '--request', str(root/'request.json'),
                    '--request-sha256', rs.digest((root/'request.json').read_bytes())]
            command = [sys.executable, str(ROOT/'scripts/repair_pixel_transforms.py')]
            completed = subprocess.run(command+['prepare', *args, '--out', 'prepared'],
                                       capture_output=True, text=True, timeout=20)
            self.assertEqual(0, completed.returncode, completed.stdout+completed.stderr)
            receipt = json.loads(completed.stdout)
            with Image.open(root/'prepared/context.png') as context:
                candidate = context.copy()
            candidate.putpixel((14, 15), (250, 251, 252, 253)); candidate.save(root/'candidate.png')
            pin = receipt['files']['effective-write.png']['sha256']
            def apply(out):
                return subprocess.run(command+['apply', *args, '--out', out, '--bundle', 'prepared',
                    '--candidate', 'candidate.png', '--candidate-sha256', rs.digest((root/'candidate.png').read_bytes()),
                    '--expected-effective-write-sha256', pin], capture_output=True, text=True, timeout=20)
            completed = apply('result')
            self.assertEqual(0, completed.returncode, completed.stdout+completed.stderr)
            self.assertGreater(json.loads(completed.stdout)['changed_pixels'], 0)
            candidate.putpixel((0, 0), (17, 0, 0, 0)); candidate.save(root/'candidate.png')
            failed = apply('rejected')
            self.assertEqual(2, failed.returncode, failed.stdout+failed.stderr)
            self.assertIn('context', json.loads(failed.stdout)['error'])
            self.assertFalse((root/'rejected').exists())


if __name__ == '__main__': unittest.main()
