"""Read-only Library links to the source identities retained by native plans."""
import json
from pathlib import PurePosixPath
import re
from urllib.parse import quote, urlencode

import project_storage
from studio_workflow.privacy import is_regular

PAGE_SIZE = 20
FILE_LIMIT = 12


def source(studio, identifier, workspace_id, scope):
    if scope == 'private':raise ValueError('Native export history is available for Regular pictures only')
    if not isinstance(workspace_id, str):raise ValueError('Supply the current Workspace identity')
    studio.assets.metadata(identifier, workspace_id, privacy='regular')
    return studio.assets.get(identifier, privacy='regular')


def visible(studio, plan, identifier):
    if not isinstance(plan, dict) or not isinstance(plan.get('assets'), list):raise ValueError('Saved export source records unavailable')
    ids = plan.get('source_assets')
    if not is_regular(plan) or plan.get('kind') != 'native' or not isinstance(ids, list) or not 1 <= len(ids) <= 33 or identifier not in ids:return False
    if any(not is_regular(record.get('metadata', {})) for record in plan.get('assets', []) if isinstance(record, dict)):return False
    # A shared export can contain other pictures; every source must still be Regular.
    for key in ids:
        try:asset = studio.assets.get(key, privacy='regular')
        except ValueError:return False
        job = studio.jobs.get(asset['job_id'])
        if job is not None and not is_regular(job):return False
    return True


def artifact_path(production, identifier, record):
    relative = record.get('path')
    if (not isinstance(relative, str) or not relative or len(relative) > 2000 or '\\' in relative or ':' in relative
            or PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts):
        raise ValueError('Recorded file path unavailable')
    if not re.fullmatch('[a-f0-9]{64}', str(record.get('sha256', ''))) or type(record.get('bytes')) is not int:
        raise ValueError('Recorded file identity unavailable')
    base = project_storage.directory(production.root, identifier)
    path = production.file(identifier, relative)
    if not path.is_relative_to(base):raise ValueError('Recorded file path unavailable')
    part = base
    for name in PurePosixPath(relative).parts:
        part = part/name
        if project_storage._linked(part):raise ValueError('Recorded file path unavailable')
    if path.stat().st_size != record['bytes']:raise ValueError('Recorded file size changed')
    return path


def projection(studio, project, asset, workspace_id):
    plan, state, identifier = project['plan'], project['state'], project['id']
    if not isinstance(state, dict):raise ValueError('Saved export state unavailable')
    if not visible(studio, plan, asset['id']):return None
    snapshots = [s for s in plan.get('assets', []) if isinstance(s, dict) and s.get('id') == 'asset-'+asset['id']]
    digest = snapshots[0].get('sha256') if len(snapshots) == 1 else None
    available = bool(isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest))
    available = available and not project_storage.problem(studio.production.root, identifier, plan)
    result = {'id':identifier, 'name':str(plan.get('name', 'Native export'))[:200], 'kind':plan.get('export_kind'),
              'created_at':project['created_at'], 'status':str(state.get('status', 'unknown'))[:40],
              'plan_sha256':plan.get('sha256'), 'source_sha256':digest,
              'historical_source':digest != asset['sha256'], 'available':bool(available), 'artifacts':[]}
    records = state.get('artifacts', [])
    if not isinstance(records, list):records = []
    result['more_artifacts'] = len(records) > FILE_LIMIT
    if available:
        for index, record in enumerate(records[:FILE_LIMIT]):
            item = {'name':'Recorded file unavailable', 'available':False}
            if isinstance(record, dict):
                try:
                    artifact_path(studio.production, identifier, record)
                    item.update(name=record['path'], available=True, sha256=record['sha256'], bytes=record['bytes'],
                                url='/api/assets/'+quote(asset['id'], safe='')+'/native-exports/'+identifier+'/files/'+str(index)+'?'+urlencode({'workspace_id':workspace_id, 'sha256':record['sha256']}))
                except (OSError, ValueError, TypeError, KeyError):pass
            result['artifacts'].append(item)
    return result


def inspect(studio, identifier, workspace_id, scope='regular', offset='0'):
    asset = source(studio, identifier, workspace_id, scope)
    if not isinstance(offset, str) or not re.fullmatch('[0-9]{1,7}', offset):raise ValueError('Invalid export history page')
    offset = int(offset)
    # SQLite finds exact source IDs; only one bounded page of plan/state JSON enters Python.
    with studio.production.connect() as db:
        rows = db.execute('''SELECT id,created,
            CASE WHEN length(plan)<=? THEN plan END AS plan,
            CASE WHEN length(state)<=? THEN state END AS state
            FROM projects WHERE json_extract(CASE WHEN json_valid(plan) THEN plan ELSE '{}' END,'$.kind')='native'
            AND EXISTS(SELECT 1 FROM json_each(CASE WHEN json_valid(plan) THEN plan ELSE '{}' END,'$.source_assets') WHERE type='text' AND value=?)
            ORDER BY created DESC,id DESC LIMIT ? OFFSET ?''',
            (project_storage.PLAN_LIMIT, project_storage.PLAN_LIMIT, identifier, PAGE_SIZE+1, offset)).fetchall()
    result = {'workspace_id':workspace_id, 'asset_id':identifier, 'plans':[],
              'next_offset':str(offset+PAGE_SIZE) if len(rows)>PAGE_SIZE else None, 'unavailable':False}
    for row in rows[:PAGE_SIZE]:
        try:
            project = {'id':row['id'], 'created_at':row['created'], 'plan':json.loads(row['plan']), 'state':json.loads(row['state'])}
            entry = projection(studio, project, asset, workspace_id)
            if entry:result['plans'].append(entry)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):result['unavailable'] = True
    return result


def file(studio, asset_id, identifier, index, workspace_id, digest, scope='regular'):
    asset = source(studio, asset_id, workspace_id, scope)
    if not re.fullmatch('[0-9]{1,2}', index) or int(index) >= FILE_LIMIT:raise ValueError('Unknown recorded file')
    project = studio.production._get(identifier)
    entry = projection(studio, project, asset, workspace_id)
    if not entry or not entry['available'] or int(index) >= len(entry['artifacts']) or not entry['artifacts'][int(index)]['available']:
        raise ValueError('Recorded export unavailable')
    record = project['state']['artifacts'][int(index)]
    if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest) or record.get('sha256') != digest:
        raise ValueError('Recorded file receipt changed; refresh the export list')
    path = artifact_path(studio.production, identifier, record)
    if studio.production._file_hash(path) != record['sha256']:raise ValueError('Recorded file changed; historical receipt is preserved')
    return path
