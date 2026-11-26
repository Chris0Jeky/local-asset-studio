"""Real Studio SQLite API fixtures, exclusively synthetic software-test records."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import sys

import fixtures
import pipeline as p


def make_workspace(root, through='unreal'):
    """Create isolated synthetic Workspace via the shipped API, with stable IDs/times."""
    app = p.REPO_ROOT / 'app'
    if str(app) not in sys.path: sys.path.insert(0, str(app))
    from workspace import AssetWorkspace
    root = Path(root); media = root / 'artifacts'; experiments = root / 'experiments'
    workspace = AssetWorkspace(experiments)
    with workspace.connection() as db:
        db.execute('UPDATE workspace_identity SET id=?', ('a' * 32,))
    family = p.create_family('p36-fixture', 'a' * 32, 'p36-fixture', fixtures.policy(), mode='synthetic')
    binding = {'schema': 'las.p36-workspace-binding/1', 'family_id': family['family_id'],
               'workspace_id': family['workspace_id'], 'character_card_id': 'p36-fixture',
               'card_revision': 0, 'concept_asset_id': None, 'stages': {}}
    for stage in p.STAGES:
        receipt = fixtures.stage_receipt(family, stage, media)
        artifacts = receipt['payload']['artifacts']
        job_id = 'p36-' + stage
        outputs = [{'filename': Path(a['path']).name, 'media_type': 'image' if a['media_type'].startswith('image/') else 'model',
                    'type': 'output', 'subfolder': stage} for a in artifacts]
        job = {'id': job_id, 'status': 'completed', 'operation': 'asset.import', 'privacy': 'regular',
               'created_at': 1, 'preset_id': 'fixture-import', 'preset_name': 'Synthetic fixture import',
               'controls': {}, 'batch_count': len(outputs), 'graph_path': 'fixture:import',
               'prompt_ids': [], 'submissions': [], 'outputs': outputs, 'parent_assets': []}
        directory = experiments / 'runs' / job_id; directory.mkdir(parents=True)
        state = p.canonical_bytes(job); workflow = p.canonical_bytes({'fixture': 'no-generation'})
        (directory / 'state.json').write_bytes(state); (directory / 'workflow.json').write_bytes(workflow)
        mapped = {}
        for index, artifact in enumerate(artifacts):
            asset_id = workspace.register(job, index, media / artifact['path'])
            artifact['asset_id'] = asset_id
            use = 'P36 fixture ' + stage
            acceptance = workspace.accept(asset_id, {'reviewer': 'local-user', 'use': use,
                                                    'sha256': artifact['sha256'], 'workspace_id': 'a' * 32,
                                                    'note': 'Synthetic test declaration; no owner art acceptance.'})
            acceptance_id = 'test-' + stage + '-' + artifact['key']
            with workspace.connection() as db:
                db.execute('UPDATE asset_acceptances SET id=?,accepted_at=1 WHERE id=?',
                           (acceptance_id, acceptance['acceptances'][0]['id']))
            mapped[artifact['key']] = {'asset_id': asset_id, 'sha256': artifact['sha256'],
                                       'acceptance_id': acceptance_id, 'use': use}
        receipt = p.seal(receipt)
        for dimension, state_name, actor in [('generation', 'completed', 'fixture'),
                                              ('inspection', 'inspected', 'fixture'),
                                              ('acceptance', 'accepted', 'owner')]:
            receipt = p.attest(receipt, dimension, state_name, actor, 'fixture:actual-workspace-test')
        family = p.record_receipt(family, receipt)
        binding['stages'][stage] = {'receipt_id': receipt['id'], 'artifacts': mapped,
                                   'jobs': {job_id: {'state_sha256': hashlib.sha256(state).hexdigest(),
                                                     'workflow_sha256': hashlib.sha256(workflow).hexdigest()}}}
        if stage == 'concept':
            canon = artifacts[0]; binding['concept_asset_id'] = canon['asset_id']
            workspace.card_command({'action': 'create', 'kind': 'character', 'id': 'p36-fixture',
                                    'name': 'Synthetic P36 fixture',
                                    'body': {'who': 'Synthetic swatches, no real character'},
                                    'lineage': [{'role': 'canon', 'asset_id': canon['asset_id'],
                                                 'sha256': canon['sha256']}]})
        if stage == through: break
    with workspace.connection() as db:
        db.execute('UPDATE cards SET created_at=1,updated_at=1')
    return {'workspace': workspace, 'experiments': experiments, 'asset_root': media,
            'family': family, 'binding': binding}


def set_job(context, stage, **changes):
    job_id = next(iter(context['binding']['stages'][stage]['jobs']))
    path = context['experiments'] / 'runs' / job_id / 'state.json'
    job = p.load_json(path); job.update(copy.deepcopy(changes)); path.write_bytes(p.canonical_bytes(job))
    return path
