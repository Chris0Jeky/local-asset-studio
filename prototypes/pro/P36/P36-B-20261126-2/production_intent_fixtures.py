"""Disposable actual-Production API fixtures; no worker, socket or generation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pipeline as p


def make_production_case(root, *, experiments=None, family_id='p36-fixture', stage='turnaround'):
    """Prepare through actual Studio/Production APIs inside .runtime only.

    Runtime object-info/system/disk-capacity observations are synthetic. Real preparation,
    preflight file hashing, plan publication and SQLite APIs are exercised.
    Existing Workspace fixtures can be shared; startup job loading is suppressed
    so this fixture does not normalize their deliberately minimal retained jobs.
    """
    root = Path(root).absolute()
    experiments = Path(experiments).absolute() if experiments is not None else root / 'experiments'
    for path in (root, experiments):
        p.require(path.resolve().is_relative_to((p.REPO_ROOT / '.runtime').resolve()), 'Fixture must remain under .runtime')
        p.require(not any(p.linked(item) for item in (path, *path.parents)), 'Linked fixture root refused')
    for name in ('config', 'presets', 'models', 'workflows/api', 'comfy/input', 'comfy/models/diffusion_models'):
        (root / name).mkdir(parents=True, exist_ok=True)
    for path in (p.REPO_ROOT / 'tests', p.REPO_ROOT / 'app'):
        if str(path) not in sys.path: sys.path.insert(0, str(path))
    from test_server import FakeStudio, server
    from production_intent import capture_production_intent
    graph = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'fixture.safetensors', 'weight_dtype': 'default'}},
        '2': {'class_type': 'P36FixtureSampler', 'inputs': {'seed': 7, 'text': 'Synthetic preparation fixture'}},
        '3': {'class_type': 'LoadImage', 'inputs': {'image': 'fixture.png'}},
    }
    preset = {'id': 'p36-production-fixture', 'name': 'Synthetic prepared operation',
              'graph': 'workflows/api/p36-fixture.json', 'backend_id': 'primary',
              'seed': ['2', 'seed'], 'positive': ['2', 'text']}
    model = root / 'comfy/models/diffusion_models/fixture.safetensors'
    model.write_bytes(b'P36 synthetic model bytes; never loaded')
    source = root / 'comfy/input/fixture.png'
    source.write_bytes(b'P36 synthetic input bytes; never decoded')
    pin = {'id': 'p36-model-fixture', 'file': 'diffusion_models/fixture.safetensors',
           'bytes': model.stat().st_size, 'sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
           'source': 'Synthetic fixture; no model acquisition', 'url': 'https://huggingface.co/fixture/fixture/resolve/main/fixture.safetensors'}
    files = {'config/local.json': {'comfy_root': str(root / 'comfy'), 'experiments_root': str(experiments),
                                   'runtime_recovery_enabled': False},
             'presets/catalog.json': {'presets': [preset]}, 'models/library.json': {'assets': [pin], 'collections': []},
             preset['graph']: graph}
    for relative, value in files.items(): (root / relative).write_text(json.dumps(value), encoding='utf-8')
    schema = {
        'UNETLoader': {'input': {'required': {'unet_name': [['fixture.safetensors']], 'weight_dtype': [['default']]}}, 'output': ['MODEL']},
        'P36FixtureSampler': {'input': {'required': {'seed': ['INT', {'min': 0}], 'text': ['STRING']}}, 'output': []},
        'LoadImage': {'input': {'required': {'image': [['fixture.png']]}}, 'output': ['IMAGE']},
    }
    with patch.object(threading.Thread, 'start', lambda *_: None), patch.object(server.Studio, '_load_jobs', lambda *_: None):
        studio = FakeStudio(root, [])
    # No runtime socket: only the object-info and system_stats fixtures are read.
    with patch.object(studio, 'node_info', return_value=schema), \
         patch.object(studio, '_request', return_value={'system': {'fixture': True}, 'devices': []}), \
         patch.object(server.shutil, 'disk_usage', return_value=SimpleNamespace(total=32 * 1024**3, used=16 * 1024**3, free=16 * 1024**3)):
        project = studio.production.create({'name': 'P36 actual Production API fixture',
            'recipe': {'preset_id': preset['id'], 'controls': {}, 'batch_count': 1},
            'axis': 'seed', 'values': [7], 'max_generations': 1, 'max_seconds': 1800})
    result = capture_production_intent(experiments, project['id'], 0, family_id=family_id, stage=stage, studio_root=root)
    p.require(result['passed'], 'Production fixture capture failed: ' + str(result['blockers']))
    return {'studio_root': root, 'experiments': experiments, 'project_id': project['id'], 'stage_index': 0,
            'family_id': family_id, 'stage': stage, 'intent': result['intent'], 'studio': studio,
            'model_path': model, 'input_path': source}
