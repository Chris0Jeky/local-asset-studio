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

from studio_workflow import pose_artifact, pose_raster, pose_route_binding as binding


def digest(char):
    return char * 64


def artifact(width=256, height=256, missing=()):
    points = []
    for index, name in enumerate(pose_artifact.JOINTS):
        if name in missing:
            points.extend([0, 0, 0])
        else:
            points.extend([20 + (index % 6) * 35, 20 + (index // 6) * 90, .9])
    raw = json.dumps({'people': [{'pose_keypoints_2d': points}]}).encode()
    return pose_artifact.import_openpose(
        raw, width=width, height=height, coordinate_space='pixels')


def pins(route_id):
    values = {key: digest(char) for key, char in (
        ('model', '1'), ('encoder', '2'), ('vae', '3'), ('graph', '4'),
        ('nodes', '5'), ('runtime', '6'), ('reference_transform', '7'),
        ('prompt_dialect', '8'))}
    if route_id == 'copy-pose':
        values['lora'] = digest('9')
    elif route_id == 'klein-geometry':
        values['renderer'] = digest('a')
    else:
        values.update(controlnet=digest('b'), renderer=digest('c'))
    return values


def skeleton_request(pose, data):
    canvas = pose['canvas']
    threshold = .3
    filtered = []
    for name in pose_artifact.JOINTS:
        point = pose['joints'][name]
        if point is None or (point['origin'] == 'estimated' and point['confidence'] < threshold):
            filtered.append(name)
    return {
        'schema': binding.REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': 'synthetic-pose-binding',
        'route': {
            'id': 'sdxl-corrected-skeleton',
            'mechanism': 'sdxl-precomputed-skeleton',
            'source_kind': 'precomputed-skeleton',
            'detector_behavior': 'bypass-precomputed-guide',
            'native_slot': 'control-image',
            'backend_id': 'primary',
            'target_canvas': canvas,
            'pins': pins('sdxl-corrected-skeleton'),
        },
        'source': {
            'kind': 'precomputed-skeleton',
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'format': 'PNG',
            'canvas': canvas,
            'artifact_id': pose['id'],
            'renderer_id': pose_raster.RENDERER,
            'renderer_sha256': pins('sdxl-corrected-skeleton')['renderer'],
            'threshold': threshold,
            'expected_filtered_joints': filtered,
        },
        'transform': binding.expected_transform('identity', canvas, canvas),
    }


def rgb_bytes(width=320, height=240):
    image = Image.new('RGB', (width, height), (90, 100, 110))
    output = io.BytesIO()
    image.save(output, format='PNG')
    image.close()
    return output.getvalue()


def copy_request(data, width=320, height=240):
    canvas = {'width': width, 'height': height}
    return {
        'schema': binding.REQUEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'binding_name': 'synthetic-copy-pose-binding',
        'route': {
            'id': 'copy-pose',
            'mechanism': 'copy-pose-rgb',
            'source_kind': 'rgb-pose-donor',
            'detector_behavior': 'not-applicable',
            'native_slot': 'pose-donor-image-2',
            'backend_id': 'primary',
            'target_canvas': canvas,
            'pins': pins('copy-pose'),
        },
        'source': {
            'kind': 'rgb-pose-donor',
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'format': 'PNG',
            'canvas': canvas,
        },
        'transform': binding.expected_transform('identity', canvas, canvas),
    }


class PoseRouteBindingCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / 'scripts/pose_route_binding.py'), *map(str, args)],
            cwd=tempfile.gettempdir(), text=True, capture_output=True, timeout=20)

    def write_json(self, path, value):
        path.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')

    def test_compile_and_validate_skeleton_binding_from_another_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pose = artifact(missing=('right_ear',))
            guide = pose_raster.render_png(pose)
            request = skeleton_request(pose, guide)
            request_path = root / 'request.json'
            artifact_path = root / 'artifact.json'
            source_path = root / 'guide.png'
            output = root / 'binding.json'
            self.write_json(request_path, request)
            self.write_json(artifact_path, pose)
            source_path.write_bytes(guide)
            result = self.run_cli(
                'compile', request_path, '--source', source_path,
                '--artifact', artifact_path, '--out', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            saved = json.loads(output.read_text())
            self.assertEqual(receipt['binding_id'], saved['binding_id'])
            self.assertEqual(receipt['route_id'], 'sdxl-corrected-skeleton')
            self.assertFalse(receipt['ready_for_execution'])
            self.assertFalse(receipt['generation_submitted'])
            result = self.run_cli(
                'validate-binding', request_path, output, '--source', source_path,
                '--artifact', artifact_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['binding_id'], saved['binding_id'])

    def test_compile_refuses_overwrite_and_invalid_input_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = rgb_bytes()
            request = copy_request(data)
            request_path = root / 'request.json'
            source_path = root / 'donor.png'
            output = root / 'binding.json'
            self.write_json(request_path, request)
            source_path.write_bytes(data)
            result = self.run_cli('compile', request_path, '--source', source_path, '--out', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            before = output.read_bytes()
            result = self.run_cli('compile', request_path, '--source', source_path, '--out', output)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_bytes(), before)
            error = json.loads(result.stderr)
            self.assertFalse(error['generation_submitted'])
            request['execution_authorized'] = True
            bad = root / 'bad.json'
            self.write_json(bad, request)
            missing = root / 'never-created.json'
            result = self.run_cli('compile', bad, '--source', source_path, '--out', missing)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(missing.exists())

    def test_validate_binding_detects_tamper_and_artifact_argument_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pose = artifact()
            guide = pose_raster.render_png(pose)
            request = skeleton_request(pose, guide)
            request_path = root / 'request.json'
            artifact_path = root / 'artifact.json'
            source_path = root / 'guide.png'
            output = root / 'binding.json'
            self.write_json(request_path, request)
            self.write_json(artifact_path, pose)
            source_path.write_bytes(guide)
            result = self.run_cli(
                'compile', request_path, '--source', source_path,
                '--artifact', artifact_path, '--out', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(output.read_text())
            saved['diagnostics']['detector_invocations'] = 1
            self.write_json(output, saved)
            result = self.run_cli(
                'validate-binding', request_path, output, '--source', source_path,
                '--artifact', artifact_path)
            self.assertEqual(result.returncode, 2)
            self.assertIn('binding', json.loads(result.stderr)['error'])
            copy_data = rgb_bytes()
            copy_req = copy_request(copy_data)
            copy_request_path = root / 'copy.json'
            copy_source = root / 'copy.png'
            copy_out = root / 'copy-binding.json'
            self.write_json(copy_request_path, copy_req)
            copy_source.write_bytes(copy_data)
            result = self.run_cli(
                'compile', copy_request_path, '--source', copy_source,
                '--artifact', artifact_path, '--out', copy_out)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(copy_out.exists())


if __name__ == '__main__':
    unittest.main()
