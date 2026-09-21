"""Regression tests for reviewed pose route-binding boundary failures."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_artifact, pose_route_binding as binding

SCRIPT = ROOT / 'scripts' / 'pose_route_binding.py'


def digest(char):
    return char * 64


def artifact():
    points = []
    for index in range(18):
        points.extend([
            20 + (index % 6) * 35,
            20 + (index // 6) * 90,
            .9,
        ])
    raw = json.dumps({'people': [{'pose_keypoints_2d': points}]}).encode()
    return pose_artifact.import_openpose(
        raw, width=256, height=256, coordinate_space='pixels')


def skeleton_request(pose, data):
    canvas = pose['canvas']
    threshold = .3
    filtered = []
    for name in pose_artifact.JOINTS:
        point = pose['joints'][name]
        if point is None or (
                point['origin'] == 'estimated' and
                point['confidence'] < threshold):
            filtered.append(name)
    pins = {
        'model': digest('1'),
        'encoder': digest('2'),
        'vae': digest('3'),
        'graph': digest('4'),
        'nodes': digest('5'),
        'runtime': digest('6'),
        'reference_transform': digest('7'),
        'prompt_dialect': digest('8'),
        'controlnet': digest('9'),
        'renderer': digest('a'),
    }
    return {
        'schema': binding.REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': 'transparent-skeleton-regression',
        'route': {
            'id': 'sdxl-corrected-skeleton',
            'mechanism': 'sdxl-precomputed-skeleton',
            'source_kind': 'precomputed-skeleton',
            'detector_behavior': 'bypass-precomputed-guide',
            'native_slot': 'control-image',
            'backend_id': 'primary',
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
            'renderer_id': 'external-renderer-v1',
            'renderer_sha256': pins['renderer'],
            'threshold': threshold,
            'expected_filtered_joints': filtered,
        },
        'transform': binding.expected_transform('identity', canvas, canvas),
    }


def donor_request(data, canvas, image_format='JPEG'):
    pins = {
        'model': digest('1'),
        'encoder': digest('2'),
        'vae': digest('3'),
        'graph': digest('4'),
        'nodes': digest('5'),
        'runtime': digest('6'),
        'reference_transform': digest('7'),
        'prompt_dialect': digest('8'),
        'lora': digest('9'),
    }
    return {
        'schema': binding.REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': 'oriented-donor-regression',
        'route': {
            'id': 'copy-pose',
            'mechanism': 'copy-pose-rgb',
            'source_kind': 'rgb-pose-donor',
            'detector_behavior': 'not-applicable',
            'native_slot': 'pose-donor-image-2',
            'backend_id': 'primary',
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


class PoseRouteBindingRegressionTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=tempfile.gettempdir(),
            text=True,
            capture_output=True,
            timeout=15,
        )

    def test_subparser_errors_emit_non_executable_json_receipts(self):
        for args in (('compile',), ('validate-binding',)):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                receipt = json.loads(result.stderr)
                self.assertIn('error', receipt)
                self.assertFalse(receipt['ready_for_execution'])
                self.assertFalse(receipt['execution_authorized'])
                self.assertFalse(receipt['generation_submitted'])

    def test_fully_transparent_coloured_skeleton_is_not_visible_evidence(self):
        pose = artifact()
        image = Image.new('RGBA', (256, 256), (255, 0, 0, 0))
        output = io.BytesIO()
        image.save(output, format='PNG')
        image.close()
        data = output.getvalue()
        request = skeleton_request(pose, data)
        with self.assertRaisesRegex(ValueError, 'opaque RGB'):
            binding.compile_binding(request, data, artifact=pose)

    def test_exif_oriented_donor_is_rejected_before_transform_binding(self):
        canvas = {'width': 40, 'height': 20}
        image = Image.new('RGB', (canvas['width'], canvas['height']), (90, 120, 150))
        exif = Image.Exif()
        exif[274] = 6
        output = io.BytesIO()
        image.save(output, format='JPEG', exif=exif)
        image.close()
        data = output.getvalue()
        request = donor_request(data, canvas)
        with self.assertRaisesRegex(ValueError, 'orientation'):
            binding.compile_binding(request, data)


if __name__ == '__main__':
    unittest.main()
