"""Owned, deterministic synthetic evidence corpus. Not Blender or an art benchmark."""
from __future__ import annotations

import copy
from pathlib import Path
import platform
from PIL import Image, ImageDraw, __version__ as pillow_version

from .core import canonical, digest
from .dcc_evidence import compare_bundles
from .research_intake import sha


def _write(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')


def _fixture(root, change):
    root.mkdir()
    scene = {'format': 'studio.dcc-scene/v1', 'complete': True,
             'runtime': {'producer': 'synthetic_fixture_not_blender'},
             'content': {'objects': {
                 'Body': {'vertices': 8, 'topology_sha256': digest([[0, 1, 2, 3], [4, 5, 6, 7]]),
                          'weights_sha256': digest([[0, 0, 1.0]])},
                 'Attachment': {'vertices': 4, 'topology_sha256': digest([[0, 1, 2, 3]])}},
                         'images': {}, 'actions': {}},
             'findings': [], 'limitations': ['Synthetic protocol fixture, not observed 3D geometry.']}
    if change == 'same-count-topology':
        scene['content']['objects']['Body']['topology_sha256'] = digest([[0, 2, 1, 3], [4, 5, 6, 7]])
    elif change == 'weight-drift':
        scene['content']['objects']['Body']['weights_sha256'] = digest([[0, 0, 0.5]])
    elif change == 'omitted-part':
        del scene['content']['objects']['Attachment']
    _write(root / 'scene.json', scene)
    views = {}
    for view in ('front', 'profile'):
        if change == 'missing-holdout' and view == 'profile':
            continue
        image = Image.new('RGBA', (128, 128), (24, 24, 24, 255))
        draw = ImageDraw.Draw(image)
        box = (28, 32, 100, 108) if view == 'front' else (48, 32, 80, 108)
        draw.rectangle(box, fill=(90, 125, 155, 255))
        draw.rectangle((59, 16, 69, 32), fill=(190, 190, 190, 255))
        if change == 'pixel-change' and view == 'front':
            image.putpixel((64, 64), (255, 0, 0, 255))
        path = root / (view + '.png'); image.save(path); image.close()
        views[view] = {'path': path.name, 'sha256': sha(path.read_bytes())}
    contract = {'view_ids': ['front', 'profile'], 'resolution': [128, 128],
                'camera_rig_sha256': digest({'synthetic_camera': change == 'camera-shift'}),
                'render_settings': {'producer': 'pillow-owned-fixture', 'frame': 1}}
    _write(root / 'evidence.json', {'format': 'studio.dcc-evidence/v1', 'scope': 'synthetic_fixture',
                                   'capture_contract': contract, 'views': views,
                                   'scene': {'path': 'scene.json', 'sha256': sha((root / 'scene.json').read_bytes())}})
    if change == 'tampered-file':
        (root / 'front.png').write_bytes(b'intentionally corrupted after manifest hashing')


def run_study(destination: Path):
    destination.mkdir(exist_ok=False)
    _fixture(destination / 'baseline', 'baseline')
    cases = {'unchanged': 'within_declared_tolerance', 'pixel-change': 'different',
             'same-count-topology': 'different', 'weight-drift': 'different', 'omitted-part': 'different',
             'missing-holdout': 'incomplete', 'camera-shift': 'incomparable', 'tampered-file': 'refused'}
    results = {}
    for case, expected in cases.items():
        _fixture(destination / case, case)
        try:
            report = compare_bundles(destination / 'baseline', destination / case,
                                     ['front', 'profile'], ['profile'])
            observed = report['status']
        except ValueError as exc:
            observed = 'refused'
            report = {'status': observed, 'reason': str(exc), 'baseline_promoted': False}
        _write(destination / (case + '-comparison.json'), report)
        results[case] = {'expected': expected, 'observed': observed, 'matched': observed == expected}
    root = Path(__file__).resolve().parent
    result = {'format': 'studio.dcc-fixture-study/v1', 'native_execution': False,
              'expectations_met': all(row['matched'] for row in results.values()), 'cases': results,
              'environment': {'python': platform.python_version(), 'pillow': pillow_version},
              'implementation_sha256': {name: sha((root / name).read_bytes())
                                        for name in ('dcc_fixture.py', 'dcc_evidence.py', 'research_intake.py')},
              'notice': 'Synthetic regressions exercise evidence mechanics, not Blender, AMD, '
                        'visual quality, temporal correctness or licensing.'}
    _write(destination / 'study.json', result)
    return result
