"""Cross-module regressions for the canonical corrected-pose route contract."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import struct
import unittest
import zlib

from PIL import Image

from studio_workflow import pose_artifact, pose_raster
from studio_workflow import pose_route_binding as binding
from studio_workflow import pose_screening


def digest(character):
    return character * 64


def artifact(width=256, height=256):
    points = []
    for index in range(18):
        points.extend([
            20 + (index % 6) * 35,
            20 + (index // 6) * 90,
            .9,
        ])
    raw = json.dumps({'people': [{'pose_keypoints_2d': points}]}).encode()
    return pose_artifact.import_openpose(
        raw, width=width, height=height, coordinate_space='pixels')


def common_pins():
    return {
        'model': digest('1'),
        'encoder': digest('2'),
        'vae': digest('3'),
        'graph': digest('4'),
        'nodes': digest('5'),
        'runtime': digest('6'),
        'reference_transform': digest('7'),
        'prompt_dialect': digest('8'),
    }


def skeleton_request(pose, data, *, renderer_id=None, renderer_pin=None,
                     backend_id='primary'):
    canvas = pose['canvas']
    threshold = .3
    renderer_id = renderer_id or pose_raster.RENDERER
    renderer_pin = renderer_pin or pose_raster.renderer_sha256()
    pins = common_pins()
    pins.update(controlnet=digest('9'), renderer=renderer_pin)
    filtered = [
        name for name in pose_artifact.JOINTS
        if pose['joints'][name] is None or (
            pose['joints'][name]['origin'] == 'estimated' and
            pose['joints'][name]['confidence'] < threshold)
    ]
    return {
        'schema': binding.REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': 'canonical-skeleton-binding',
        'route': {
            'id': 'sdxl-corrected-skeleton',
            'mechanism': 'sdxl-precomputed-skeleton',
            'source_kind': 'precomputed-skeleton',
            'detector_behavior': 'bypass-precomputed-guide',
            'native_slot': 'control-image',
            'backend_id': backend_id,
            'target_canvas': canvas,
            'pins': pins,
        },
        'source': {
            'kind': 'precomputed-skeleton',
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'format': 'PNG',
            'canvas': canvas,
            'artifact_id': pose['id'],
            'renderer_id': renderer_id,
            'renderer_sha256': renderer_pin,
            'threshold': threshold,
            'expected_filtered_joints': filtered,
        },
        'transform': binding.expected_transform('identity', canvas, canvas),
    }


def donor_request(data, image_format, canvas, *, backend_id='primary'):
    pins = common_pins(); pins['lora'] = digest('a')
    return {
        'schema': binding.REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': 'canonical-copy-pose-binding',
        'route': {
            'id': 'copy-pose',
            'mechanism': 'copy-pose-rgb',
            'source_kind': 'rgb-pose-donor',
            'detector_behavior': 'not-applicable',
            'native_slot': 'pose-donor-image-2',
            'backend_id': backend_id,
            'target_canvas': canvas,
            'pins': pins,
        },
        'source': {
            'kind': 'rgb-pose-donor',
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'format': image_format,
            'canvas': canvas,
        },
        'transform': binding.expected_transform('identity', canvas, canvas),
    }


def oriented_png_after_idat(width=40, height=20):
    image = Image.new('RGB', (width, height), (90, 120, 150))
    stream = io.BytesIO(); image.save(stream, format='PNG'); image.close()
    raw = stream.getvalue()
    exif = Image.Exif(); exif[274] = 6
    payload = exif.tobytes()
    if payload.startswith(b'Exif\x00\x00'):
        payload = payload[6:]
    kind = b'eXIf'
    chunk = (struct.pack('>I', len(payload)) + kind + payload +
             struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff))
    iend = raw.rfind(b'\x00\x00\x00\x00IEND')
    if iend < 0:
        raise AssertionError('synthetic PNG has no IEND')
    return raw[:iend] + chunk + raw[iend:]


class PoseRouteContractHardeningTests(unittest.TestCase):
    def test_local_renderer_identity_covers_encoder_versions(self):
        identity = pose_raster.renderer_identity()
        self.assertEqual(identity['renderer_id'], pose_raster.RENDERER)
        self.assertIn('pillow_version', identity)
        self.assertIn('zlib_runtime_version', identity)
        self.assertEqual(len(pose_raster.renderer_sha256()), 64)
        self.assertEqual(pose_raster.renderer_sha256(), pose_raster.renderer_sha256())

    def test_local_renderer_requires_its_current_identity_pin(self):
        pose = artifact(); data = pose_raster.render_png(pose)
        good = skeleton_request(pose, data)
        self.assertEqual(
            binding.compile_binding(good, data, artifact=pose)['diagnostics']['renderer_validation'],
            'recomputed-exact')
        bad = skeleton_request(pose, data, renderer_pin=digest('f'))
        with self.assertRaisesRegex(ValueError, 'renderer identity'):
            binding.compile_binding(bad, data, artifact=pose)

    def test_external_renderer_remains_receipt_bound(self):
        pose = artifact(); data = pose_raster.render_png(pose)
        request = skeleton_request(
            pose, data, renderer_id='installed-aux-renderer',
            renderer_pin=digest('e'))
        result = binding.compile_binding(request, data, artifact=pose)
        self.assertEqual(
            result['diagnostics']['renderer_validation'],
            'receipt-bound-not-recomputed')

    def test_backend_typo_is_not_hash_sealed(self):
        image = Image.new('RGB', (16, 16), (1, 2, 3))
        stream = io.BytesIO(); image.save(stream, format='PNG'); image.close()
        data = stream.getvalue(); canvas = {'width': 16, 'height': 16}
        with self.assertRaisesRegex(ValueError, 'backend'):
            binding.compile_binding(
                donor_request(data, 'PNG', canvas, backend_id='primry'), data)

    def test_webp_donor_and_tall_contain_pad_branch(self):
        image = Image.new('RGB', (100, 300), (1, 2, 3))
        stream = io.BytesIO(); image.save(stream, format='WEBP'); image.close()
        data = stream.getvalue(); canvas = {'width': 100, 'height': 300}
        result = binding.compile_binding(donor_request(data, 'WEBP', canvas), data)
        self.assertEqual(result['source']['kind'], 'rgb-pose-donor')
        self.assertEqual(result['source']['format'], 'WEBP')
        self.assertEqual(
            binding.expected_transform(
                'contain-pad', canvas, {'width': 512, 'height': 256}),
            {
                'kind': 'contain-pad',
                'source_canvas': canvas,
                'target_canvas': {'width': 512, 'height': 256},
                'scaled_canvas': {'width': 85, 'height': 256},
                'pad': {'left': 213, 'top': 0, 'right': 214, 'bottom': 0},
            })

    def test_png_exif_after_idat_is_refused(self):
        data = oriented_png_after_idat()
        canvas = {'width': 40, 'height': 20}
        request = donor_request(data, 'PNG', canvas)
        with self.assertRaisesRegex(ValueError, 'orientation'):
            binding.compile_binding(request, data)

    def test_screening_v1_is_explicitly_retired(self):
        with self.assertRaisesRegex(ValueError, 'regenerate.*v2'):
            pose_screening.validate_manifest({
                'schema': pose_screening.LEGACY_MANIFEST_SCHEMA,
                'authority': 'none',
                'execution_authorized': False,
                'generation_submitted': False,
                'campaign_id': 'legacy',
                'candidate_cap': 48,
                'additional_image_attempt_cap': 0,
                'same_defect_repeat_limit': 2,
                'routes': [],
                'cases': [],
                'review_axes': list(pose_screening.REVIEW_AXES),
                'stop_conditions': list(pose_screening.STOP_CONDITIONS),
            })


if __name__ == '__main__':
    unittest.main()
